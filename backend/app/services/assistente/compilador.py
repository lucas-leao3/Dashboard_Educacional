"""ConsultaEstruturada -> SELECT do SQLAlchemy Core (spec, compilador).

Recebe só consulta já validada pelo catálogo. As regras da base moram aqui,
onde o LLM não as alcança:
- aluno se conta por matrícula distinta;
- sem a dimensão `periodo`, cada aluno entra uma vez, pela linha do período
  mais recente (o `vigente` do dashboard). O CRG de aluno_integrado é
  constante por aluno; contar por período daria peso a quem tem mais períodos;
- trajetória por semestre vem só de crg_semestre_vigente, e nulo é lacuna;
- resposta vazia é uma categoria explícita, nunca descartada.

As categorias são calculadas numa subconsulta e agrupadas por fora: agrupar
por um rótulo que tem o mesmo nome de uma coluna de entrada (polo, renda...)
faria o PostgreSQL agrupar pela coluna crua.
"""
from dataclasses import dataclass

from sqlalchemy import Integer, Select, String, asc, cast, desc, distinct, func, literal, or_, select
from sqlalchemy.orm import Session

from app.db.vigente import aluno_integrado as ai
from app.db.vigente import crg_semestre_vigente as csv
from app.schemas.assistente import ConsultaEstruturada, Filtro
from app.services.assistente.catalogo import DIMENSOES, RESPOSTAS, Dimensao
from app.services.assistente.execucao import executar_select

LIMITE_LISTA = 1000


@dataclass
class Resultado:
    colunas: list[str]
    linhas: list[dict]
    fontes: list[str]
    total: int | None = None
    #: itens operacionais: vazio porque não há lote (e não porque não há ocorrência)
    sem_lote: bool = False


def _condicao(coluna, dimensao: Dimensao, filtro: Filtro):
    valores = filtro.valor if isinstance(filtro.valor, list) else [filtro.valor]
    if dimensao.id == "matricula":
        return coluna.in_([int(v) for v in valores])
    if filtro.op == "entre":
        return coluna.between(valores[0], valores[1])
    presentes = [v for v in valores if v != dimensao.ausente]
    partes = [coluna.in_(presentes)] if presentes else []
    if len(presentes) < len(valores):
        partes.append(or_(coluna.is_(None), func.trim(cast(coluna, String)) == ""))
    return or_(*partes)


def _categoria(coluna, dimensao: Dimensao):
    return func.coalesce(func.nullif(func.trim(coluna), ""), literal(dimensao.ausente)).label(dimensao.id)


def _base(consulta: ConsultaEstruturada):
    """aluno_integrado já filtrada por período; uma linha por aluno, salvo
    quando a própria dimensão é o período."""
    por_periodo = [_condicao(ai.c.periodo, DIMENSOES["periodo"], f) for f in consulta.filtros if f.campo == "periodo"]
    if "periodo" in consulta.dimensoes:
        return select(ai).where(*por_periodo).subquery("base")
    ordem = func.row_number().over(partition_by=ai.c.matricula, order_by=ai.c.periodo.desc()).label("ordem_periodo")
    recente = select(ai, ordem).where(*por_periodo).subquery("recente")
    return select(recente).where(recente.c.ordem_periodo == 1).subquery("base")


def _filtros(base, consulta: ConsultaEstruturada) -> list:
    return [_condicao(base.c[DIMENSOES[f.campo].coluna], DIMENSOES[f.campo], f)
            for f in consulta.filtros if f.campo != "periodo"]


def _ordenar(q: Select, consulta: ConsultaEstruturada, grupos: list) -> Select:
    if consulta.ordem:
        direcao = desc if consulta.ordem.direcao == "desc" else asc
        q = q.order_by(direcao(consulta.ordem.campo).nulls_last())
    else:
        q = q.order_by(*grupos)
    return q.limit(consulta.limite) if consulta.limite else q


def _agregado(consulta: ConsultaEstruturada) -> Select:
    if consulta.metrica == "crg_medio_semestre":
        return _por_semestre(consulta)
    base = _base(consulta)
    dims = [DIMENSOES[d] for d in consulta.dimensoes]
    cats = (select(base.c.matricula, base.c.CRG.label("crg"), *[_categoria(base.c[d.coluna], d) for d in dims])
            .where(*_filtros(base, consulta)).subquery("cats"))
    if consulta.metrica == "distribuicao_crg":
        faixa = cast(func.floor(cats.c.crg), Integer)
        return (select(faixa.label("faixa"), func.count().label("valor"), func.count().label("n"))
                .where(cats.c.crg.is_not(None)).group_by(faixa).order_by(faixa))
    grupos = [cats.c[d.id] for d in dims]
    if consulta.metrica == "contagem_alunos":
        valor = n = func.count(distinct(cats.c.matricula))
    else:  # crg_medio
        valor, n = func.avg(cats.c.crg), func.count(cats.c.crg)
    q = select(*grupos, valor.label("valor"), n.label("n"))
    return _ordenar(q.group_by(*grupos) if grupos else q, consulta, grupos)


def _por_semestre(consulta: ConsultaEstruturada) -> Select:
    alunos = select(ai.c.matricula, ai.c.turma, ai.c.polo_nome).distinct().subquery("alunos")
    dims = [DIMENSOES[d] for d in consulta.dimensoes if d != "semestre"]

    def coluna(campo: str):
        if campo == "semestre":
            return csv.c.semestre
        if campo == "matricula":
            return csv.c.matricula
        return alunos.c[DIMENSOES[campo].coluna]  # polo, turma

    cats = (select(csv.c.semestre, csv.c.crg, *[_categoria(alunos.c[d.coluna], d) for d in dims])
            .select_from(csv.join(alunos, alunos.c.matricula == csv.c.matricula))
            .where(*[_condicao(coluna(f.campo), DIMENSOES[f.campo], f) for f in consulta.filtros])
            .subquery("cats"))
    grupos = [cats.c.semestre, *[cats.c[d.id] for d in dims]]
    q = select(*grupos, func.avg(cats.c.crg).label("valor"), func.count(cats.c.crg).label("n")).group_by(*grupos)
    return _ordenar(q, consulta, grupos)


def _lista(consulta: ConsultaEstruturada) -> Select:
    base = _base(consulta)
    extras = list(dict.fromkeys(f.campo for f in consulta.filtros if f.campo in RESPOSTAS))
    limite = min(consulta.limite or LIMITE_LISTA, LIMITE_LISTA)
    return (select(base.c.matricula, base.c.nome, base.c.polo_nome.label("polo"), base.c.turma, base.c.periodo,
                   base.c.CRG.label("crg"), *[base.c[c] for c in extras], func.count().over().label("total"))
            .where(*_filtros(base, consulta))
            .order_by(base.c.nome.asc().nulls_last(), base.c.matricula)
            .limit(limite))


def compilar(consulta: ConsultaEstruturada) -> Select:
    if consulta.tipo == "agregado":
        return _agregado(consulta)
    if consulta.tipo == "lista" and consulta.metrica == "alunos":
        return _lista(consulta)
    raise ValueError(f"{consulta.tipo}/{consulta.metrica} não é compilado para SQL")


def fontes(consulta: ConsultaEstruturada) -> list[str]:
    if consulta.metrica == "crg_medio_semestre":
        return ["crg_semestre_vigente", "aluno_integrado"]
    return ["aluno_integrado"]


def resolver_sql(session: Session, consulta: ConsultaEstruturada) -> Resultado:
    linhas = executar_select(session, compilar(consulta))
    total = None
    if consulta.tipo == "lista":
        total = linhas[0]["total"] if linhas else 0
        for linha in linhas:
            linha.pop("total")
    for linha in linhas:
        if isinstance(linha.get("valor"), float):
            linha["valor"] = round(linha["valor"], 2)
    return Resultado(list(linhas[0]) if linhas else [], linhas, fontes(consulta), total)
