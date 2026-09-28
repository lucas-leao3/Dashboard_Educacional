"""Importação de um lote (docs/governanca_simplificada.md): o usuário informa
o responsável e envia um .zip de históricos; o resto é inferido.

    importar()
      1. id do lote (AAAA-MM-Lnn) e pasta raw/lotes/<id>/historicos/
      2. extrai os PDFs do .zip
      3. passo 1 -- sincronizar(): congela o FasiTech em fasitech.json e grava
         uma linha em `usuarios` por registro válido
      4. passo 2 -- atualizar_crg(): lê cada histórico, grava `historico`
         (com o período) e `crg_semestre`, e atualiza o vigente do aluno
      5. período do lote = união dos períodos dos históricos
      6. fecha o lote: SHA256SUMS, lote.md, CSVs e fechado_em

Tudo numa transação só. Se qualquer etapa falhar, nada fica: rollback no
banco e a pasta do lote apagada. Não existe lote pela metade para retomar --
existe lote fechado ou lote nenhum. Lote fechado é imutável (triggers da
revisão c5e8a1f3d920); dado novo é importação nova.
"""
import shutil
from datetime import date

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.db.engine import CrgSemestre, Historico, Ingestao, Lote, Usuarios
from app.db.vigente import aluno_vigente
from app.schemas.alunos import AlunoCreate
from app.services import fechamento
from app.services import lotes as servico
from app.services.crg_historico import carregar_historico, semestre_da_data, ultimo_crg_apurado
from app.services.fasitech_client import buscar_paginas, congelar_envelope, registros_do_envelope

SEPARADOR_PERIODOS = ";"
TAMANHO_MAXIMO_RESPONSAVEL = 100


def _inserir_snapshot(session: Session, dados: dict, ingestao_id: int) -> Usuarios:
    """usuarios é append-only: toda escrita é uma linha nova ligada à ingestão."""
    aluno = Usuarios(**dados, ingestao_id=ingestao_id)
    session.add(aluno)
    return aluno


def sincronizar(session: Session, lote_id: str) -> dict:
    """Passo 1. Busca o FasiTech, congela a resposta em <lote>/fasitech.json e
    só então grava: uma linha nova por registro válido; inválido vira exceção."""
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

    congelado = congelar_envelope(envelope, servico.caminho_do_lote(lote_id) / "fasitech.json")
    arquivo = servico.registrar_arquivo(session, lote_id, congelado, "api_fasitech")
    ingestao = servico.abrir_ingestao(session, lote_id, Ingestao.PASSO_SINCRONIZAR, arquivo.sha256 if arquivo else None)

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
    return {"ingestao_id": ingestao.id, "importados": importados, "rejeitados": rejeitados}


def _copia_para_snapshot(linha) -> dict:
    """Campos de uma linha da view que viram a base de uma linha nova."""
    return {c: getattr(linha, c) for c in AlunoCreate.model_fields}


def atualizar_crg(session: Session, lote_id: str) -> tuple[dict, set[str]]:
    """Passo 2. Lê os PDFs de <lote>/historicos/, grava cada histórico (com o
    período extraído da data de emissão) e o CRG por semestre (regra do zero
    aplicada), e insere, para cada (matricula, periodo) vigente do aluno, uma
    linha nova com CRG do último semestre apurado, nome e nascimento.

    Devolve os contadores e o conjunto de períodos dos históricos legíveis."""
    pdfs = sorted((servico.caminho_do_lote(lote_id) / "historicos").glob("*.pdf"))
    ingestao = servico.abrir_ingestao(session, lote_id, Ingestao.PASSO_CRG)
    contadores = {"pdfs_lidos": 0, "semestres_gravados": 0, "alunos_atualizados": 0,
                  "sem_academico": 0, "sem_socioeconomico": 0, "duplicados": 0, "ilegiveis": 0}
    matriculas_com_pdf: set[int] = set()
    periodos: set[str] = set()

    for pdf in pdfs:
        arquivo = servico.registrar_arquivo(session, lote_id, pdf, "pdf_historico")
        try:
            historico = carregar_historico(pdf)
        except ValueError as erro:
            # PDF ilegível não é 'sem acadêmico': vira exceção própria e segue.
            contadores["ilegiveis"] += 1
            servico.registrar_excecao(session, ingestao, "falha_identificacao", detalhe=f"{pdf.name}: {erro}")
            continue
        matricula = historico["matricula"]
        matriculas_com_pdf.add(matricula)
        periodo = semestre_da_data(historico["emitido_em"])
        periodos.add(periodo)
        if arquivo is None:
            # O mesmo PDF já entrou noutro lote: seus semestres já estão no
            # banco. Conta para o período e para a matrícula (senão o aluno
            # cairia em 'sem_academico'), mas não grava de novo.
            contadores["duplicados"] += 1
            servico.registrar_excecao(session, ingestao, "duplicado", matricula=matricula, detalhe=pdf.name)
            continue
        contadores["pdfs_lidos"] += 1
        session.add(Historico(
            ingestao_id=ingestao.id, arquivo_sha256=arquivo.sha256, matricula=matricula,
            nome=historico["nome"], data_de_nascimento=historico["data_de_nascimento"],
            emitido_em=historico["emitido_em"], periodo=periodo,
        ))

        for semestre, crg in historico["crg_por_semestre"].items():
            session.add(CrgSemestre(matricula=matricula, semestre=semestre, crg=crg, ingestao_id=ingestao.id))
            contadores["semestres_gravados"] += 1

        vigentes = session.execute(select(aluno_vigente).where(aluno_vigente.c.matricula == matricula)).all()
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

    # Quem está no banco e não tem PDF neste lote.
    session.flush()
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
    return {"ingestao_id": ingestao.id, **contadores}, periodos


def _validar_entrada(responsavel: str, nome_arquivo: str) -> str:
    responsavel = (responsavel or "").strip()
    if not responsavel:
        raise HTTPException(status_code=422, detail="Informe o nome do responsável pela importação.")
    if len(responsavel) > TAMANHO_MAXIMO_RESPONSAVEL:
        raise HTTPException(status_code=422, detail=f"Nome do responsável passa de {TAMANHO_MAXIMO_RESPONSAVEL} caracteres.")
    if not nome_arquivo.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .zip com os históricos em PDF.")
    return responsavel


def importar(session: Session, responsavel: str, nome_arquivo: str, conteudo: bytes,
             hoje: date | None = None) -> tuple[Lote, dict]:
    """Cria, processa e fecha um lote. Devolve o lote fechado e os detalhes
    da execução (arquivos, contadores dos passos, arquivos gerados)."""
    responsavel = _validar_entrada(responsavel, nome_arquivo)
    lote_id = servico.proximo_id(session, hoje or date.today())
    raiz = servico.criar_diretorio(lote_id)
    try:
        arquivos = servico.gravar_historicos(lote_id, [(nome_arquivo, conteudo)])
        if not arquivos["gravados"]:
            raise HTTPException(status_code=400, detail="O .zip não contém nenhum histórico em PDF.")

        lote = Lote(id=lote_id, periodos_cobertos="", executado_por=responsavel)
        session.add(lote)
        session.flush()
        passo1 = sincronizar(session, lote_id)
        passo2, periodos = atualizar_crg(session, lote_id)
        if not periodos:
            raise HTTPException(
                status_code=422,
                detail="Nenhum histórico legível no .zip: o período do lote não pôde ser identificado. Nada foi gravado.",
            )
        lote.periodos_cobertos = SEPARADOR_PERIODOS.join(sorted(periodos))
        gerados = fechamento.fechar_lote(session, lote)
    except BaseException:
        session.rollback()
        shutil.rmtree(raiz, ignore_errors=True)
        shutil.rmtree(fechamento.caminho_processado(lote_id), ignore_errors=True)
        raise
    return lote, {
        "arquivos": arquivos,
        "sincronizar": passo1,
        "atualizar_crg": passo2,
        "arquivos_gerados": [str(c) for c in gerados],
    }
