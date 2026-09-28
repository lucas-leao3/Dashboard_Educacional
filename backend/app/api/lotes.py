from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.engine import Excecao, Ingestao, Lote, get_session
from app.schemas.lotes import ExcecaoOut, ImportacaoOut, IngestaoOut, LoteOut, RelatorioOut
from app.services import importacao
from app.services.importacao import SEPARADOR_PERIODOS
from app.services.relatorio import relatorio_do_lote

router = APIRouter(prefix="/lotes", tags=["lotes"])


def _para_saida(session: Session, lote: Lote) -> LoteOut:
    ingestoes = session.execute(
        select(Ingestao).where(Ingestao.lote_id == lote.id).order_by(Ingestao.passo)
    ).scalars().all()
    contagem = session.execute(
        select(Excecao.motivo, func.count())
        .join(Ingestao, Ingestao.id == Excecao.ingestao_id)
        .where(Ingestao.lote_id == lote.id)
        .group_by(Excecao.motivo)
    ).all()
    return LoteOut(
        id=lote.id,
        executado_em=lote.executado_em,
        fechado_em=lote.fechado_em,
        periodos_cobertos=[p for p in lote.periodos_cobertos.split(SEPARADOR_PERIODOS) if p],
        executado_por=lote.executado_por,
        observacao=lote.observacao,
        ingestoes=[IngestaoOut.model_validate(i) for i in ingestoes],
        excecoes_por_motivo={motivo: n for motivo, n in contagem},
    )


def _exigir_lote(session: Session, lote_id: str) -> Lote:
    lote = session.get(Lote, lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return lote


@router.post("/importar", response_model=ImportacaoOut, status_code=201)
def importar_lote(
    responsavel: str = Form(..., description="Nome de quem está importando"),
    arquivo: UploadFile = File(..., description=".zip com os históricos do SIGAA em PDF"),
    session: Session = Depends(get_session),
):
    """POST /lotes/importar (multipart) -> a única entrada de dados.

    Cria o lote (id AAAA-MM-Lnn gerado), extrai os PDFs do .zip, sincroniza o
    FasiTech, lê os históricos, registra o período extraído deles e fecha o
    lote -- tudo numa transação. Qualquer erro desfaz tudo (banco e disco);
    não sobra lote pela metade. Lote fechado não se altera: dado novo é
    importação nova.

    Rota síncrona de propósito: a importação faz chamada HTTP e lê PDFs, e
    o FastAPI roda `def` num thread, sem travar o event loop."""
    lote, detalhes = importacao.importar(session, responsavel, arquivo.filename or "", arquivo.file.read())
    saida = _para_saida(session, lote)
    resumo = relatorio_do_lote(session, lote.id)["resumo"]
    return ImportacaoOut(**saida.model_dump(), **detalhes, resumo=resumo)


@router.get("", response_model=list[LoteOut])
def listar_lotes(session: Session = Depends(get_session)):
    lotes = session.execute(select(Lote).order_by(Lote.executado_em)).scalars().all()
    return [_para_saida(session, l) for l in lotes]


@router.get("/{lote_id}", response_model=LoteOut)
def buscar_lote(lote_id: str, session: Session = Depends(get_session)):
    return _para_saida(session, _exigir_lote(session, lote_id))


@router.get("/{lote_id}/excecoes", response_model=list[ExcecaoOut])
def listar_excecoes(lote_id: str, session: Session = Depends(get_session)):
    """GET /lotes/{id}/excecoes -> uma linha por exceção do lote, com o passo
    que a gerou. Trilha de auditoria bruta; o relatório é a leitura dela."""
    _exigir_lote(session, lote_id)
    excecoes = session.execute(
        select(Ingestao.passo, Excecao)
        .join(Ingestao, Ingestao.id == Excecao.ingestao_id)
        .where(Ingestao.lote_id == lote_id)
        .order_by(Ingestao.passo, Excecao.matricula, Excecao.periodo)
    ).all()
    return [
        ExcecaoOut(
            ingestao_id=excecao.ingestao_id,
            passo=passo,
            matricula=excecao.matricula,
            periodo=excecao.periodo,
            motivo=excecao.motivo,
            detalhe=excecao.detalhe,
        )
        for passo, excecao in excecoes
    ]


@router.get("/{lote_id}/relatorio", response_model=RelatorioOut)
def relatorio(lote_id: str, session: Session = Depends(get_session)):
    """GET /lotes/{id}/relatorio -> integrados e não integrados, com motivo e
    completude, sobre a base consolidada no fechamento do lote. É o mesmo
    conteúdo de integrados.csv e nao_integrados.csv."""
    _exigir_lote(session, lote_id)
    return RelatorioOut(lote=lote_id, **relatorio_do_lote(session, lote_id))
