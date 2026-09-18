import shutil

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.alunos import atualizar_crg_do_historico, sincronizar_com_fasitech
from app.db.engine import Excecao, Ingestao, Lote, get_session
from app.schemas.lotes import CorrespondenciaOut, ExcecaoOut, FechamentoOut, HistoricosOut, IngestaoOut, LoteCreate, LoteOut
from app.services import fechamento
from app.services import lotes as servico

router = APIRouter(prefix="/lotes", tags=["lotes"])

SEPARADOR_PERIODOS = ";"


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
        periodos_cobertos=lote.periodos_cobertos.split(SEPARADOR_PERIODOS),
        executado_por=lote.executado_por,
        observacao=lote.observacao,
        ingestoes=[IngestaoOut.model_validate(i) for i in ingestoes],
        excecoes_por_motivo={motivo: n for motivo, n in contagem},
    )


@router.post("", response_model=LoteOut, status_code=201)
def criar_lote(dados: LoteCreate, session: Session = Depends(get_session)):
    """POST /lotes -> abre um lote: cria raw/lotes/<id>/historicos/ e a
    linha em `lote`. É pré-requisito das rotas de dados (?lote=<id>)."""
    if session.get(Lote, dados.id) is not None:
        raise HTTPException(status_code=409, detail=f"Lote '{dados.id}' já existe")
    try:
        servico.criar_diretorio(dados.id)
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"Pasta do lote '{dados.id}' já existe em disco")

    lote = Lote(
        id=dados.id,
        periodos_cobertos=SEPARADOR_PERIODOS.join(dados.periodos_cobertos),
        executado_por=dados.executado_por,
        observacao=dados.observacao,
    )
    try:
        session.add(lote)
        session.commit()
        session.refresh(lote)
    except Exception:
        # Diretório e registro têm que nascer juntos: se o commit falhar
        # depois que a pasta já foi criada, desfaz a pasta pra não deixar o
        # id preso num limbo (pasta em disco, sem linha em `lote`).
        shutil.rmtree(servico.caminho_do_lote(dados.id), ignore_errors=True)
        raise
    return _para_saida(session, lote)


@router.get("", response_model=list[LoteOut])
def listar_lotes(session: Session = Depends(get_session)):
    lotes = session.execute(select(Lote).order_by(Lote.executado_em)).scalars().all()
    return [_para_saida(session, l) for l in lotes]


@router.get("/{lote_id}", response_model=LoteOut)
def buscar_lote(lote_id: str, session: Session = Depends(get_session)):
    lote = session.get(Lote, lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return _para_saida(session, lote)


@router.get("/{lote_id}/excecoes", response_model=list[ExcecaoOut])
def listar_excecoes(lote_id: str, session: Session = Depends(get_session)):
    """GET /lotes/{id}/excecoes -> uma linha por exceção do lote, com o passo
    que a gerou. É a base do relatório de correspondência (governança, 3.1)."""
    if session.get(Lote, lote_id) is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
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


@router.post("/{lote_id}/historicos", response_model=HistoricosOut)
async def enviar_historicos(
    lote_id: str,
    arquivos: list[UploadFile] = File(...),
    executar: bool = Query(False, description="Depois de gravar, roda os passos 1 e 2 que ainda não rodaram"),
    session: Session = Depends(get_session),
):
    """POST /lotes/{id}/historicos (multipart) -> grava PDFs de histórico em
    raw/lotes/<id>/historicos/, substituindo a cópia manual. Recusa 409
    depois que o passo 2 leu a pasta: insumo não muda depois de lido.

    Com ?executar=true, encadeia /alunos/sincronizar e /alunos/atualizar-crg,
    pulando o que já rodou. Se um passo falhar, os PDFs ficam gravados e o
    erro do passo é a resposta -- reenviar os mesmos arquivos retoma de onde
    parou (reenvio é idempotente)."""
    lote = servico.exigir_lote(session, lote_id)
    fechamento.exigir_aberto(lote)
    servico.exigir_passo_livre(session, lote_id, Ingestao.PASSO_CRG)
    recebidos = [(a.filename, await a.read()) for a in arquivos]
    resultado = servico.gravar_historicos(lote_id, recebidos)
    saida = HistoricosOut(lote=lote_id, **resultado)
    if not executar:
        return saida

    feitos = {i.passo for i in session.execute(select(Ingestao).where(Ingestao.lote_id == lote_id)).scalars()}
    saida.sincronizar = "ja_executado" if Ingestao.PASSO_SINCRONIZAR in feitos else sincronizar_com_fasitech(lote_id, session)
    saida.atualizar_crg = "ja_executado" if Ingestao.PASSO_CRG in feitos else atualizar_crg_do_historico(lote_id, session)
    return saida


@router.post("/{lote_id}/fechar", response_model=FechamentoOut)
def fechar_lote(lote_id: str, session: Session = Depends(get_session)):
    """POST /lotes/{id}/fechar -> sela o lote: SHA256SUMS e lote.md em
    raw/lotes/<id>/, vigente.csv e correspondencia.csv em processed/<id>/,
    e lote.fechado_em. Exige os passos 1 e 2; lote fechado não se reabre."""
    lote = session.get(Lote, lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    gerados = fechamento.fechar_lote(session, lote)
    saida = _para_saida(session, lote)
    return FechamentoOut(**saida.model_dump(), arquivos_gerados=[str(c) for c in gerados])


@router.get("/{lote_id}/correspondencia", response_model=list[CorrespondenciaOut])
def listar_correspondencia(lote_id: str, session: Session = Depends(get_session)):
    """GET /lotes/{id}/correspondencia -> uma linha por matrícula: tem acadêmico?
    tem socioeconômico? o que falta? O mesmo conteúdo do correspondencia.csv."""
    if session.get(Lote, lote_id) is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return fechamento.correspondencia_do_lote(session, lote_id)
