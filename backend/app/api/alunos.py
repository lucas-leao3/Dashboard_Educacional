import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.db.engine import CrgSemestre, Ingestao, Polo, Usuarios, get_session
from app.db.matricula import codigo_de_polo, turma_da_matricula
from app.db.vigente import aluno_vigente
from app.schemas.alunos import AlunoCreate, AlunoOut
from app.services import lotes as servico
from app.services.crg_historico import carregar_historico, ultimo_crg_apurado
from app.services.fasitech_client import buscar_paginas, congelar_envelope, registros_do_envelope

router = APIRouter(prefix="/alunos", tags=["alunos"])

LoteParam = Query(..., description="Id do lote aberto com POST /lotes", examples=["2026-09-L01"])


def _inserir_snapshot(session: Session, dados: dict, ingestao_id: int) -> Usuarios:
    """usuarios é append-only: toda escrita é uma linha nova ligada à ingestão."""
    aluno = Usuarios(**dados, ingestao_id=ingestao_id)
    session.add(aluno)
    return aluno


def _saida_do_snapshot(session: Session, aluno: Usuarios) -> AlunoOut:
    """AlunoOut de uma linha recém-gravada em `usuarios`.

    Quem calcula turma e polo é a view `aluno_vigente` (§4.8), mas a linha
    criada aqui pode não ser a vigente daquele (matricula, periodo) -- se
    outra ingestão, mais recente, já gravou o mesmo par, ela é que manda. E um
    201 tem que descrever o que acabou de ser gravado, não outra linha. Então
    os derivados saem da mesma regra (app.db.matricula) e da mesma tabela
    `polo` que a view usa; nada de mapa paralelo."""
    saida = AlunoOut.model_validate(aluno)
    saida.turma = turma_da_matricula(aluno.matricula)
    saida.polo_cod = codigo_de_polo(aluno.matricula)
    polo = session.get(Polo, saida.polo_cod) if saida.polo_cod else None
    saida.polo_nome = polo.nome if polo else None
    return saida


@router.get("", response_model=list[AlunoOut])
def listar_alunos(session: Session = Depends(get_session)):
    """GET /alunos -> o valor vigente de cada (matricula, periodo)."""
    return session.execute(select(aluno_vigente).order_by(aluno_vigente.c.matricula, aluno_vigente.c.periodo)).all()


@router.get("/{matricula}", response_model=AlunoOut)
def buscar_aluno(matricula: int, session: Session = Depends(get_session)):
    """GET /alunos/{matricula} -> o vigente do período mais recente. 404 se não existir."""
    aluno = session.execute(
        select(aluno_vigente).where(aluno_vigente.c.matricula == matricula).order_by(aluno_vigente.c.periodo.desc())
    ).first()
    if aluno is None:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")
    return aluno


@router.post("", response_model=AlunoOut, status_code=201)
def criar_aluno(dados: AlunoCreate, lote: str = LoteParam, session: Session = Depends(get_session)):
    """POST /alunos?lote=<id> -> cadastro manual, gravado na ingestão de
    passo 0 do lote. Sempre insere; quem resolve o vigente é a view."""
    servico.exigir_lote(session, lote)
    ingestao = servico.abrir_ingestao(session, lote, Ingestao.PASSO_MANUAL)
    aluno = _inserir_snapshot(session, dados.model_dump(), ingestao.id)
    servico.fechar_ingestao(session, ingestao, lidos=1, aceitos=1, rejeitados=0)
    session.refresh(aluno)
    return _saida_do_snapshot(session, aluno)


@router.post("/sincronizar")
def sincronizar_com_fasitech(lote: str = LoteParam, session: Session = Depends(get_session)):
    """POST /alunos/sincronizar?lote=<id> -> passo 1 do lote. Busca o FasiTech,
    congela a resposta em <lote>/fasitech.json e só então grava: uma linha
    nova por registro válido; inválido vira exceção."""
    servico.exigir_lote(session, lote)
    # Recusa antes de buscar/congelar: senão uma retentativa depois do passo 1
    # já ter rodado sobrescreveria fasitech.json (a evidência do audit,
    # governança §3.2) com conteúdo novo, órfão do hash já gravado no banco.
    servico.exigir_passo_livre(session, lote, Ingestao.PASSO_SINCRONIZAR)
    try:
        envelope = buscar_paginas()
    except RuntimeError as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except httpx.HTTPError as erro:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar o FasiTech: {erro}") from erro
    try:
        registros = registros_do_envelope(envelope)
    except (ValueError, KeyError) as erro:
        raise HTTPException(status_code=502, detail=str(erro)) from erro

    congelado = congelar_envelope(envelope, servico.caminho_do_lote(lote) / "fasitech.json")
    arquivo = servico.registrar_arquivo(session, lote, congelado, "api_fasitech")
    ingestao = servico.abrir_ingestao(session, lote, Ingestao.PASSO_SINCRONIZAR, arquivo.sha256 if arquivo else None)

    importados = rejeitados = 0
    for registro in registros:
        try:
            aluno = AlunoCreate(**registro)
        except ValidationError as erro:
            rejeitados += 1
            erros = erro.errors()
            # loc de cada erro é uma tupla, ex.: ('periodo',) ou ('matricula',).
            tem_erro_periodo = any(e["loc"] and e["loc"][0] == "periodo" for e in erros)
            tem_erro_matricula = any(e["loc"] and e["loc"][0] == "matricula" for e in erros)
            motivo = "sem_periodo" if tem_erro_periodo and not tem_erro_matricula else "matricula_invalida"
            # LGPD: nunca usar str(erro) nem e["input"]/e["msg"] -- ambos podem
            # carregar o valor submetido (ex.: um nome ou nascimento
            # malformado). Só nome do campo e tipo do erro.
            detalhe = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in erros)[:500]
            servico.registrar_excecao(
                session, ingestao, motivo,
                matricula=registro.get("matricula") if isinstance(registro.get("matricula"), int) else None,
                periodo=registro.get("periodo"), detalhe=detalhe,
            )
            continue
        _inserir_snapshot(session, aluno.model_dump(), ingestao.id)
        importados += 1

    servico.fechar_ingestao(session, ingestao, lidos=len(registros), aceitos=importados, rejeitados=rejeitados)
    return {"lote": lote, "ingestao_id": ingestao.id, "importados": importados, "rejeitados": rejeitados}


def _vigentes_da_matricula(session: Session, matricula: int) -> list:
    return session.execute(select(aluno_vigente).where(aluno_vigente.c.matricula == matricula)).all()


def _copia_para_snapshot(linha) -> dict:
    """Campos de uma linha da view que viram a base de uma linha nova."""
    return {c: getattr(linha, c) for c in AlunoCreate.model_fields}


@router.post("/atualizar-crg")
def atualizar_crg_do_historico(lote: str = LoteParam, session: Session = Depends(get_session)):
    """POST /alunos/atualizar-crg?lote=<id> -> passo 2 do lote. Lê os PDFs de
    <lote>/historicos/, grava o CRG por semestre em crg_semestre (regra do
    zero aplicada) e insere, para cada (matricula, periodo) vigente do aluno,
    uma linha nova com CRG do último semestre apurado, nome e nascimento."""
    servico.exigir_lote(session, lote)
    servico.exigir_passo_livre(session, lote, Ingestao.PASSO_CRG)
    pdfs = sorted((servico.caminho_do_lote(lote) / "historicos").glob("*.pdf"))
    if not pdfs:
        raise HTTPException(status_code=503, detail=f"Nenhum PDF em {servico.caminho_do_lote(lote) / 'historicos'}")

    ingestao = servico.abrir_ingestao(session, lote, Ingestao.PASSO_CRG)
    contadores = {"pdfs_lidos": 0, "semestres_gravados": 0, "alunos_atualizados": 0,
                  "sem_academico": 0, "sem_socioeconomico": 0, "duplicados": 0, "ilegiveis": 0}
    matriculas_com_pdf: set[int] = set()

    for pdf in pdfs:
        arquivo = servico.registrar_arquivo(session, lote, pdf, "pdf_historico")
        if arquivo is None:
            contadores["duplicados"] += 1
            servico.registrar_excecao(session, ingestao, "duplicado", detalhe=pdf.name)
            # O PDF já foi lido noutro lote, mas a matrícula ainda é a dele:
            # sem isto o aluno cai em 'sem_academico' apesar de ter PDF.
            try:
                matriculas_com_pdf.add(carregar_historico(pdf)["matricula"])
            except ValueError:
                pass
            continue
        try:
            historico = carregar_historico(pdf)
        except ValueError as erro:
            # PDF ilegível não é 'sem acadêmico': vira exceção própria e segue.
            contadores["ilegiveis"] += 1
            servico.registrar_excecao(session, ingestao, "matricula_invalida", detalhe=f"{pdf.name}: {erro}")
            continue
        contadores["pdfs_lidos"] += 1
        matricula = historico["matricula"]
        matriculas_com_pdf.add(matricula)

        for semestre, crg in historico["crg_por_semestre"].items():
            session.add(CrgSemestre(matricula=matricula, semestre=semestre, crg=crg, ingestao_id=ingestao.id))
            contadores["semestres_gravados"] += 1

        vigentes = _vigentes_da_matricula(session, matricula)
        if not vigentes:
            contadores["sem_socioeconomico"] += 1
            servico.registrar_excecao(session, ingestao, "sem_socioeconomico", matricula=matricula)
            continue
        crg_vigente = ultimo_crg_apurado(historico["crg_por_semestre"])
        for linha in vigentes:
            dados = _copia_para_snapshot(linha)
            dados.update(CRG=crg_vigente, nome=historico["nome"], data_de_nascimento=historico["data_de_nascimento"])
            _inserir_snapshot(session, dados, ingestao.id)
            contadores["alunos_atualizados"] += 1

    # Quem está no banco e não tem PDF neste lote: os 47 da governança.
    sem_pdf = session.execute(
        select(aluno_vigente.c.matricula, aluno_vigente.c.periodo).distinct()
        .where(aluno_vigente.c.matricula.not_in(matriculas_com_pdf) if matriculas_com_pdf else true())
    ).all()
    for matricula, periodo in sem_pdf:
        contadores["sem_academico"] += 1
        servico.registrar_excecao(session, ingestao, "sem_academico", matricula=matricula, periodo=periodo)

    servico.fechar_ingestao(
        session, ingestao, lidos=len(pdfs),
        aceitos=contadores["pdfs_lidos"],
        rejeitados=contadores["duplicados"] + contadores["sem_socioeconomico"] + contadores["ilegiveis"],
    )
    return {"lote": lote, "ingestao_id": ingestao.id, **contadores}
