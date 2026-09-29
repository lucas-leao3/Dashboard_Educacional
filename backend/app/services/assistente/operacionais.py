"""Itens operacionais e listas de relatório. Reaproveitam relatorio_do_lote
para os números saírem iguais aos da tela /dados. Rodam como o dono, não como
leitor_assistente: é código fixo, sem SQL derivado da pergunta."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.engine import Ingestao, Lote
from app.db.matricula import polo_da_matricula, turma_da_matricula
from app.schemas.assistente import ConsultaEstruturada, Filtro
from app.services.assistente.catalogo import DIMENSOES, ROTULOS_RESPOSTA
from app.services.assistente.compilador import Resultado
from app.services.relatorio import relatorio_do_lote

FONTES_RELATORIO = ["usuarios", "crg_semestre", "historico", "excecao", "lote", "ingestao"]


def ultimo_lote(session: Session) -> str | None:
    """O lote da ingestão mais recente: o que a tela /dados mostra como vigente."""
    return session.execute(select(Ingestao.lote_id).order_by(Ingestao.id.desc()).limit(1)).scalar()


def _passa(filtros: list[Filtro], campo: str, valor) -> bool:
    for f in filtros:
        if f.campo != campo:
            continue
        valores = f.valor if isinstance(f.valor, list) else [f.valor]
        ok = valores[0] <= valor <= valores[1] if f.op == "entre" else valor in valores
        if not ok:
            return False
    return True


def _resultado(linhas: list[dict]) -> Resultado:
    return Resultado(list(linhas[0]) if linhas else [], linhas, FONTES_RELATORIO, len(linhas))


def resolver_operacional(session: Session, consulta: ConsultaEstruturada) -> Resultado:
    lote_id = ultimo_lote(session)
    if lote_id is None:
        return Resultado([], [], FONTES_RELATORIO, 0, sem_lote=True)
    relatorio = relatorio_do_lote(session, lote_id)
    metrica = consulta.metrica
    if metrica == "resumo_ultimo_lote":
        return _resumo(session, lote_id, relatorio)
    if metrica == "campos_sem_resposta":
        return _campos(relatorio)
    if metrica == "alunos_incompletos":
        return _incompletos(relatorio, consulta)
    if metrica == "nao_integrados":
        return _resultado([
            {"matricula": l["matricula"], "nome": l["nome"], "motivo": l["motivo_descricao"], "detalhe": l["detalhe"]}
            for l in relatorio["nao_integrados"] if _passa(consulta.filtros, "motivo", l["motivo"])
        ])
    raise ValueError(f"{metrica} não é operacional")


def _resumo(session: Session, lote_id: str, relatorio: dict) -> Resultado:
    lote = session.get(Lote, lote_id)
    lidos, aceitos = session.execute(
        select(func.coalesce(func.sum(Ingestao.registros_lidos), 0), func.coalesce(func.sum(Ingestao.registros_aceitos), 0))
        .where(Ingestao.lote_id == lote_id)
    ).one()
    resumo = relatorio["resumo"]
    return _resultado([{
        "lote": lote_id, "fechado_em": lote.fechado_em.isoformat() if lote.fechado_em else None,
        "registros_lidos": lidos, "registros_aceitos": aceitos,
        "integrados": resumo["integrados"], "nao_integrados": resumo["nao_integrados"],
    }])


def _campos(relatorio: dict) -> Resultado:
    integrados = relatorio["integrados"]
    contagem: dict[str, int] = {}
    for linha in integrados:
        for campo in linha["campos_sem_resposta"]:
            contagem[campo] = contagem.get(campo, 0) + 1
    ordem = sorted(contagem.items(), key=lambda item: (-item[1], item[0]))
    return _resultado([{"campo": ROTULOS_RESPOSTA.get(c, c), "valor": q, "n": len(integrados)} for c, q in ordem])


def _incompletos(relatorio: dict, consulta: ConsultaEstruturada) -> Resultado:
    linhas = []
    for l in relatorio["integrados"]:
        if not l["qtd_campos_sem_resposta"]:
            continue
        polo = polo_da_matricula(l["matricula"]) or DIMENSOES["polo"].ausente
        turma = turma_da_matricula(l["matricula"]) or DIMENSOES["turma"].ausente
        if not (_passa(consulta.filtros, "polo", polo) and _passa(consulta.filtros, "turma", turma)):
            continue
        linhas.append({
            "matricula": l["matricula"], "nome": l["nome"], "polo": polo, "turma": turma,
            "campos_sem_resposta": ", ".join(ROTULOS_RESPOSTA.get(c, c) for c in l["campos_sem_resposta"]),
            "preenchimento": l["percentual_preenchimento"],
        })
    return _resultado(linhas)
