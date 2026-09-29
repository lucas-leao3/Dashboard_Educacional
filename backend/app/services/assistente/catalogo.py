"""O que o assistente sabe consultar: a fonte única do prompt, da validação e
do planejamento. Quem não está aqui não existe para o assistente.

Respostas socioeconômicas = CAMPOS_SOCIOECONOMICOS do relatório: os campos que
o FasiTech de fato envia. Campo que a fonte não manda (escolaridade dos pais,
computador próprio...) viria nulo para 100% da base; oferecê-lo ao LLM só
geraria gráfico de "Sem resposta".
"""
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from app.db.vigente import aluno_integrado, crg_semestre_vigente
from app.schemas.assistente import ConsultaEstruturada, Filtro
from app.services.relatorio import CAMPOS_SOCIOECONOMICOS, MOTIVOS


class ConsultaInvalida(ValueError):
    """A consulta cita algo fora do catálogo. A mensagem volta ao LLM na nova
    tentativa, então diz o que é aceito."""


@dataclass(frozen=True)
class Dimensao:
    id: str
    rotulo: str
    coluna: str | None  # coluna de aluno_integrado; None = não vem dela
    ausente: str = "Sem resposta"
    temporal: bool = False
    ordinal: bool = False


ROTULOS_RESPOSTA = {
    "genero": "Gênero", "cor_etnia": "Cor/Etnia", "pcd": "PcD", "tipo_deficiencia": "Tipo de deficiência",
    "renda": "Renda familiar", "deslocamento": "Deslocamento", "trabalho": "Trabalho",
    "assistencia_estudantil": "Assistência estudantil", "gasto_internet": "Gasto com internet",
    "saude_mental": "Saúde mental", "estresse": "Estresse", "tipo_moradia": "Tipo de moradia",
    "acesso_internet": "Acesso à internet",
}
RESPOSTAS = tuple(CAMPOS_SOCIOECONOMICOS)

_DIMENSOES = [
    # Os rótulos de ausência de polo e turma são os mesmos do front (SEM_POLO, SEM_TURMA).
    Dimensao("polo", "Polo", "polo_nome", ausente="Sem polo informado"),
    Dimensao("turma", "Turma", "turma", ausente="Sem turma informada", ordinal=True),
    Dimensao("periodo", "Período de coleta", "periodo", temporal=True, ordinal=True),
    Dimensao("semestre", "Semestre letivo", None, temporal=True, ordinal=True),
    Dimensao("matricula", "Matrícula", "matricula"),
    Dimensao("motivo", "Motivo", None),
    *[Dimensao(c, ROTULOS_RESPOSTA[c], c, ordinal=(c == "renda")) for c in RESPOSTAS],
]
DIMENSOES = {d.id: d for d in _DIMENSOES}


@dataclass(frozen=True)
class Metrica:
    id: str
    rotulo: str
    tipo: str  # agregado | lista | operacional
    dimensoes: frozenset[str]
    filtros: frozenset[str]
    min_dimensoes: int = 0
    max_dimensoes: int = 2
    exige_dimensao: str | None = None


_AGRUPAVEIS = frozenset({"polo", "turma", "periodo", *RESPOSTAS})
_FILTRAVEIS = _AGRUPAVEIS | {"matricula"}
_NENHUMA = frozenset()

_METRICAS = [
    Metrica("contagem_alunos", "Contagem de alunos", "agregado", _AGRUPAVEIS, _FILTRAVEIS),
    Metrica("crg_medio", "CRG médio", "agregado", _AGRUPAVEIS, _FILTRAVEIS),
    Metrica("distribuicao_crg", "Distribuição do CRG", "agregado", _NENHUMA, _FILTRAVEIS, max_dimensoes=0),
    Metrica("crg_medio_semestre", "CRG médio por semestre letivo", "agregado",
            frozenset({"semestre", "polo", "turma"}), frozenset({"semestre", "polo", "turma", "matricula"}),
            min_dimensoes=1, exige_dimensao="semestre"),
    Metrica("alunos", "Lista de alunos", "lista", _NENHUMA, _FILTRAVEIS, max_dimensoes=0),
    Metrica("alunos_incompletos", "Alunos integrados com campos sem resposta", "lista", _NENHUMA,
            frozenset({"polo", "turma"}), max_dimensoes=0),
    Metrica("nao_integrados", "Alunos não integrados", "lista", _NENHUMA, frozenset({"motivo"}), max_dimensoes=0),
    Metrica("resumo_ultimo_lote", "Resumo do último lote", "operacional", _NENHUMA, _NENHUMA, max_dimensoes=0),
    Metrica("campos_sem_resposta", "Campos com mais respostas ausentes", "operacional", _NENHUMA, _NENHUMA,
            max_dimensoes=0),
]
METRICAS = {m.id: m for m in _METRICAS}

_ENTRE = frozenset({"turma", "periodo", "semestre"})
_MARCADOR = re.compile(r"⟨A\d+⟩")
# Matrícula real tem 12 dígitos; 18 é o teto que cabe no bigint da coluna.
# Mais que isso é engano (duas matrículas coladas) e viraria erro no banco.
_DIGITOS_MATRICULA = re.compile(r"\d{9,18}")


def matricula_valida(valor: str) -> bool:
    return bool(_DIGITOS_MATRICULA.fullmatch(valor))


def normalizar(texto: str) -> str:
    """Sem acento, sem caixa, espaços simples: para casar grafias diferentes."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def valores_validos(session: Session) -> dict[str, list[str]]:
    """Valores que cada dimensão tem hoje na base dos dashboards. Lido a cada
    pergunta: a base é pequena e muda a cada lote."""
    valores: dict[str, list[str]] = {}
    for d in _DIMENSOES:
        if d.coluna is None or d.id == "matricula":
            continue
        coluna = aluno_integrado.c[d.coluna]
        brutos = session.execute(select(distinct(coluna)).where(coluna.is_not(None))).scalars()
        valores[d.id] = sorted({str(v) for v in brutos if str(v).strip()}) + [d.ausente]
    valores["semestre"] = sorted(session.execute(select(distinct(crg_semestre_vigente.c.semestre))).scalars())
    valores["motivo"] = sorted(MOTIVOS)
    return valores


def validar(consulta: ConsultaEstruturada, valores: dict[str, list[str]],
            aceita_marcador: bool = True) -> ConsultaEstruturada:
    """Confere a consulta contra o catálogo e devolve uma cópia com os valores de
    filtro na grafia canônica ("cameta" -> "Cametá"). Levanta ConsultaInvalida.

    `aceita_marcador=False` para consulta que não veio de uma pergunta
    (/executar): lá não há mapa de marcadores para resolver ⟨An⟩."""
    if consulta.tipo == "fora_do_catalogo":
        # Nada dela é executado nem descrito além da interpretação: o resto,
        # que pode citar campo inexistente ("evasao"), é descartado.
        return ConsultaEstruturada(tipo="fora_do_catalogo", interpretacao=consulta.interpretacao)
    metrica = METRICAS.get(consulta.metrica or "")
    if metrica is None or metrica.tipo != consulta.tipo:
        aceitas = ", ".join(m.id for m in _METRICAS if m.tipo == consulta.tipo)
        raise ConsultaInvalida(f"metrica {consulta.metrica!r} não existe para tipo {consulta.tipo!r}; use: {aceitas}")
    if len(set(consulta.dimensoes)) != len(consulta.dimensoes):
        raise ConsultaInvalida("dimensão repetida")
    fora = [d for d in consulta.dimensoes if d not in metrica.dimensoes]
    if fora:
        raise ConsultaInvalida(f"dimensões {fora} não se aplicam a {metrica.id}; aceitas: {sorted(metrica.dimensoes)}")
    if not metrica.min_dimensoes <= len(consulta.dimensoes) <= metrica.max_dimensoes:
        raise ConsultaInvalida(f"{metrica.id} aceita de {metrica.min_dimensoes} a {metrica.max_dimensoes} dimensões")
    if metrica.exige_dimensao and metrica.exige_dimensao not in consulta.dimensoes:
        raise ConsultaInvalida(f"{metrica.id} exige a dimensão {metrica.exige_dimensao!r}")
    if consulta.ordem and consulta.ordem.campo not in {"valor", *consulta.dimensoes}:
        raise ConsultaInvalida("ordem.campo deve ser 'valor' ou uma dimensão da consulta")
    filtros = [_validar_filtro(f, metrica, valores, aceita_marcador) for f in consulta.filtros]
    return consulta.model_copy(update={"filtros": filtros})


def _validar_filtro(filtro: Filtro, metrica: Metrica, valores: dict[str, list[str]],
                    aceita_marcador: bool) -> Filtro:
    if filtro.campo not in metrica.filtros:
        raise ConsultaInvalida(f"filtro {filtro.campo!r} não se aplica a {metrica.id}; aceitos: {sorted(metrica.filtros)}")
    brutos = filtro.valor if isinstance(filtro.valor, list) else [filtro.valor]
    if filtro.op == "=" and len(brutos) != 1:
        raise ConsultaInvalida("op '=' recebe um valor só")
    if filtro.op == "in" and not brutos:
        raise ConsultaInvalida("op 'in' recebe uma lista com ao menos um valor")
    if filtro.op == "entre" and (filtro.campo not in _ENTRE or len(brutos) != 2):
        raise ConsultaInvalida(f"op 'entre' só vale para {sorted(_ENTRE)} e recebe [início, fim]")
    if filtro.campo == "matricula":
        canonicos = [str(v) for v in brutos]
        if not all(matricula_valida(v) or (aceita_marcador and _MARCADOR.fullmatch(v)) for v in canonicos):
            raise ConsultaInvalida("matricula aceita só marcadores ⟨An⟩ presentes na pergunta")
    else:
        canonicos = [_canonico(filtro.campo, str(v), valores) for v in brutos]
    return Filtro(campo=filtro.campo, op=filtro.op, valor=canonicos[0] if filtro.op == "=" else canonicos)


def _canonico(campo: str, valor: str, valores: dict[str, list[str]]) -> str:
    por_forma = {normalizar(v): v for v in valores.get(campo, [])}
    try:
        return por_forma[normalizar(valor)]
    except KeyError:
        raise ConsultaInvalida(f"valor {valor!r} não existe em {campo}; valores: {valores.get(campo, [])}") from None


@dataclass(frozen=True)
class Dashboard:
    """Um dashboard existente e as consultas que ele já responde. A rota fica no
    front (domain/catalogoDashboards.ts): aqui só o id e os parâmetros."""
    id: str
    rotulo: str
    tipo: str
    metricas: frozenset[str]
    dimensoes: tuple[frozenset[str], ...]  # conjuntos de dimensões aceitos
    obrigatorios: frozenset[str] = frozenset()
    opcionais: frozenset[str] = frozenset()
    param_dimensao: str | None = None  # parâmetro de URL que recebe a dimensão


_CONTAGEM_OU_CRG = frozenset({"contagem_alunos", "crg_medio"})
_PERIODO = frozenset({"periodo"})
_SEM_DIMENSAO = (frozenset(),)

# A ordem importa: o primeiro que casa ganha (contagem por polo -> Polos, não Bidimensional).
DASHBOARDS = (
    Dashboard("polos", "Visão Geral dos Polos", "agregado", _CONTAGEM_OU_CRG, (frozenset({"polo"}),), opcionais=_PERIODO),
    Dashboard("turmas", "Turmas do polo", "agregado", _CONTAGEM_OU_CRG, (frozenset({"turma"}),),
              obrigatorios=frozenset({"polo"}), opcionais=_PERIODO),
    Dashboard("turmas", "Turmas do polo", "lista", frozenset({"alunos"}), _SEM_DIMENSAO,
              obrigatorios=frozenset({"polo"}), opcionais=_PERIODO),
    Dashboard("alunos_turma", "Alunos da turma", "lista", frozenset({"alunos"}), _SEM_DIMENSAO,
              obrigatorios=frozenset({"polo", "turma"}), opcionais=_PERIODO),
    Dashboard("perfil", "Perfil do aluno", "lista", frozenset({"alunos"}), _SEM_DIMENSAO,
              obrigatorios=frozenset({"matricula"})),
    # Os eixos que a tela Bidimensional oferece (domain/analises.ts, EIXOS_X).
    Dashboard("bidimensional", "Análise Bidimensional", "agregado", frozenset({"crg_medio"}),
              tuple(frozenset({e}) for e in ("cor_etnia", "genero", "renda", "trabalho", "polo", "turma")),
              opcionais=frozenset({"polo", "periodo"}), param_dimensao="dimensao"),
    Dashboard("distribuicao", "Distribuição do CRG", "agregado", frozenset({"distribuicao_crg"}), _SEM_DIMENSAO,
              opcionais=frozenset({"polo", "periodo"})),
    # O longitudinal não segue o filtro de período: o eixo é o semestre letivo.
    Dashboard("longitudinal", "Análise Longitudinal", "agregado", frozenset({"crg_medio_semestre"}),
              (frozenset({"semestre"}), frozenset({"semestre", "turma"})), opcionais=frozenset({"polo", "turma"})),
)
