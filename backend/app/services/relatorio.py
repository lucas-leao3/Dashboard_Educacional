"""Relatórios de integração de um lote (docs/governanca_simplificada.md):
quem passou pelo cruzamento acadêmico × socioeconômico e quem não passou,
com o motivo e a completude de cada registro.

**Base do relatório: a base consolidada no fechamento do lote.** Tudo o que
as ingestões deste lote e das anteriores gravaram (ingestao_id <= a última do
lote). Para o lote mais recente isso é exatamente o que o dashboard mostra --
a lista de integrados tem as mesmas matrículas da view `aluno_integrado`. Para
um lote antigo é o retrato de quando ele fechou, e não muda depois: lote
seguinte não reescreve relatório de lote fechado.

Critério do cruzamento, o mesmo da view:
- socioeconômico = linha em `usuarios` (resposta do FasiTech) para a matrícula;
- acadêmico = CRG por semestre em `crg_semestre` (lido de um histórico).
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.engine import CrgSemestre, Excecao, Historico, Ingestao, Usuarios
from app.services.crg_historico import ultimo_crg_apurado

STATUS_INTEGRADO = "Integrado com sucesso"

MOTIVOS = {
    "sem_academico": "Possui socioeconômico e não possui acadêmico",
    "sem_socioeconomico": "Possui acadêmico e não possui socioeconômico",
    "falha_identificacao": "Falha de identificação",
    "matricula_nao_encontrada": "Matrícula não encontrada",
}

# Campos que o questionário socioeconômico coleta HOJE (as chaves que o
# FasiTech manda, fora matrícula, período e polo -- polo nunca vem preenchido
# e é derivado da matrícula). Campos que a fonte não envia (escolaridade dos
# pais, qtd_computador...) ficam de fora: contar como "sem resposta" algo que
# ninguém perguntou mediria a fonte, não o aluno (limitação declarada no lote.md).
CAMPOS_SOCIOECONOMICOS = (
    "genero", "cor_etnia", "pcd", "tipo_deficiencia", "renda", "deslocamento", "trabalho",
    "assistencia_estudantil", "gasto_internet", "saude_mental", "estresse", "tipo_moradia",
    "acesso_internet",
)


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _declarou_deficiencia(pcd: str | None) -> bool:
    """tipo_deficiencia só é pergunta para quem respondeu 'Sim' em pcd."""
    return isinstance(pcd, str) and pcd.strip().lower() == "sim"


def completude(socio: Usuarios | None, tem_academico: bool, crg: float | None) -> dict:
    """Completude do registro sobre os campos das fontes que ele TEM: do lado
    acadêmico, o CRG do último semestre apurado (o que alimenta o dashboard);
    do socioeconômico, CAMPOS_SOCIOECONOMICOS. A ausência de uma fonte inteira
    já é o motivo da não integração; listar os campos dela como "sem
    resposta" só repetiria isso."""
    avaliados = 0
    sem_resposta: list[str] = []
    if tem_academico:
        avaliados += 1
        if crg is None:
            sem_resposta.append("CRG")
    if socio is not None:
        for campo in CAMPOS_SOCIOECONOMICOS:
            if campo == "tipo_deficiencia" and not _declarou_deficiencia(socio.pcd):
                continue
            avaliados += 1
            if _vazio(getattr(socio, campo)):
                sem_resposta.append(campo)
    percentual = round(100 * (avaliados - len(sem_resposta)) / avaliados, 1) if avaliados else None
    return {
        "campos_avaliados": avaliados,
        "qtd_campos_sem_resposta": len(sem_resposta),
        "campos_sem_resposta": sem_resposta,
        "percentual_preenchimento": percentual,
    }


def limite_do_lote(session: Session, lote_id: str) -> int | None:
    """A última ingestão do lote: o relatório considera ela e as anteriores."""
    return session.execute(select(func.max(Ingestao.id)).where(Ingestao.lote_id == lote_id)).scalar()


# As três leituras abaixo pegam "a primeira linha por chave" numa consulta
# já ordenada da mais recente para a mais antiga -- a mesma regra das views
# (ingestão mais recente vence), com o limite de ingestão que a view não tem.
# O volume é de centenas de linhas; resolver em Python evita DISTINCT ON.

def _socioeconomico(session: Session, limite: int) -> dict[int, Usuarios]:
    """Por matrícula, a linha vigente do período mais recente -- o mesmo
    `vigente` que o dashboard usa para classificar o aluno."""
    linhas = session.execute(
        select(Usuarios)
        .where(Usuarios.ingestao_id <= limite)
        .order_by(Usuarios.matricula, Usuarios.periodo.desc(), Usuarios.ingestao_id.desc(), Usuarios.id.desc())
    ).scalars()
    por_matricula: dict[int, Usuarios] = {}
    for u in linhas:
        por_matricula.setdefault(u.matricula, u)
    return por_matricula


def _academico(session: Session, limite: int) -> dict[int, float | None]:
    """Por matrícula com histórico: o CRG do último semestre apurado."""
    linhas = session.execute(
        select(CrgSemestre.matricula, CrgSemestre.semestre, CrgSemestre.crg)
        .where(CrgSemestre.ingestao_id <= limite)
        .order_by(CrgSemestre.matricula, CrgSemestre.semestre, CrgSemestre.ingestao_id.desc())
    ).all()
    por_matricula: dict[int, dict[str, float | None]] = {}
    for matricula, semestre, crg in linhas:
        por_matricula.setdefault(matricula, {}).setdefault(semestre, crg)
    return {m: ultimo_crg_apurado(semestres) for m, semestres in por_matricula.items()}


def _nomes_dos_historicos(session: Session, limite: int) -> dict[int, str | None]:
    linhas = session.execute(
        select(Historico.matricula, Historico.nome)
        .where(Historico.ingestao_id <= limite)
        .order_by(Historico.matricula, Historico.ingestao_id.desc(), Historico.id.desc())
    ).all()
    nomes: dict[int, str | None] = {}
    for matricula, nome in linhas:
        nomes.setdefault(matricula, nome)
    return nomes


def _motivo_de_excecao(passo: int, motivo: str) -> str | None:
    """Exceção do lote que vira linha de não integrado (registro que nem
    chegou a ter matrícula utilizável). As outras exceções já estão
    representadas pela própria matrícula, ou não são falta de cruzamento."""
    if motivo == "matricula_invalida":
        # Passo 1: registro do FasiTech sem matrícula válida. Passo 2 (lotes
        # anteriores à importação simplificada): PDF ilegível.
        return "matricula_nao_encontrada" if passo == Ingestao.PASSO_SINCRONIZAR else "falha_identificacao"
    if motivo in ("falha_identificacao", "sem_periodo"):
        return "falha_identificacao"
    return None


def relatorio_do_lote(session: Session, lote_id: str) -> dict:
    """{'integrados': [...], 'nao_integrados': [...], 'resumo': {...}}."""
    limite = limite_do_lote(session, lote_id)
    if limite is None:
        return {"integrados": [], "nao_integrados": [], "resumo": _resumo([], [])}

    socio = _socioeconomico(session, limite)
    academico = _academico(session, limite)
    nomes_pdf = _nomes_dos_historicos(session, limite)

    integrados, nao_integrados = [], []
    for matricula in sorted(socio.keys() | academico.keys()):
        linha_socio = socio.get(matricula)
        tem_academico = matricula in academico
        crg = academico.get(matricula)
        linha = {
            "matricula": matricula,
            "nome": nomes_pdf.get(matricula) or (linha_socio.nome if linha_socio else None),
            "academico": tem_academico,
            "socioeconomico": linha_socio is not None,
            **completude(linha_socio, tem_academico, crg),
        }
        if tem_academico and linha_socio is not None:
            integrados.append({**linha, "status": STATUS_INTEGRADO})
        else:
            codigo = "sem_academico" if linha_socio is not None else "sem_socioeconomico"
            nao_integrados.append({**linha, "motivo": codigo, "motivo_descricao": MOTIVOS[codigo], "detalhe": None})

    conhecidas = socio.keys() | academico.keys()
    excecoes = session.execute(
        select(Ingestao.passo, Excecao)
        .join(Ingestao, Ingestao.id == Excecao.ingestao_id)
        .where(Ingestao.lote_id == lote_id)
        .order_by(Excecao.id)
    ).all()
    for passo, excecao in excecoes:
        codigo = _motivo_de_excecao(passo, excecao.motivo)
        if codigo is None or excecao.matricula in conhecidas:
            continue
        nao_integrados.append({
            "matricula": excecao.matricula, "nome": None, "academico": False, "socioeconomico": False,
            "motivo": codigo, "motivo_descricao": MOTIVOS[codigo], "detalhe": excecao.detalhe,
            **completude(None, False, None),
        })

    return {"integrados": integrados, "nao_integrados": nao_integrados, "resumo": _resumo(integrados, nao_integrados)}


def _resumo(integrados: list[dict], nao_integrados: list[dict]) -> dict:
    por_motivo: dict[str, int] = {}
    for linha in nao_integrados:
        por_motivo[linha["motivo"]] = por_motivo.get(linha["motivo"], 0) + 1
    percentuais = [l["percentual_preenchimento"] for l in integrados if l["percentual_preenchimento"] is not None]
    return {
        "total": len(integrados) + len(nao_integrados),
        "integrados": len(integrados),
        "nao_integrados": len(nao_integrados),
        "por_motivo": por_motivo,
        "preenchimento_medio_integrados": round(sum(percentuais) / len(percentuais), 1) if percentuais else None,
    }
