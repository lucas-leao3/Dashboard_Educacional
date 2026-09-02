import httpx
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import Usuarios, engine
from app.schemas.alunos import AlunoCreate, AlunoOut
from app.services.crg_historico import carregar_dados_do_historico
from app.services.dados_legado import carregar_dados_legado
from app.services.fasitech_client import buscar_dados_socioeconomicos

router = APIRouter(prefix="/alunos", tags=["alunos"])


@router.get("", response_model=list[AlunoOut])
def listar_alunos():
    """GET /alunos -> lista todos os alunos (acadêmico + socioeconômico) salvos no banco."""
    with Session(engine) as session:
        alunos = session.execute(select(Usuarios)).scalars().all()
        return alunos


@router.get("/{matricula}", response_model=AlunoOut)
def buscar_aluno(matricula: int):
    """GET /alunos/{matricula} -> busca um aluno específico. 404 se não existir."""
    with Session(engine) as session:
        aluno = session.execute(
            select(Usuarios).where(Usuarios.matricula == matricula)
        ).scalars().first()

        if aluno is None:
            raise HTTPException(status_code=404, detail="Aluno não encontrado")

        return aluno


@router.post("", response_model=AlunoOut, status_code=201)
def criar_aluno(dados: AlunoCreate):
    """POST /alunos -> cadastra um aluno consolidado (dados acadêmicos + socioeconômicos).

    A correspondência entre os dois tipos de dado é feita pela matrícula: o
    Pydantic já exige matricula/periodo no payload (CRG é opcional -- nem
    toda fonte de dado tem nota). Aqui checamos se já existe registro para
    essa matrícula nesse período, evitando duplicar o mesmo snapshot.
    """
    with Session(engine) as session:
        ja_existe = session.execute(
            select(Usuarios).where(
                Usuarios.matricula == dados.matricula,
                Usuarios.periodo == dados.periodo,
            )
        ).scalars().first()

        if ja_existe is not None:
            raise HTTPException(
                status_code=409,
                detail="Já existe um registro para essa matrícula nesse período",
            )

        aluno = Usuarios(**dados.model_dump())
        session.add(aluno)
        session.commit()
        session.refresh(aluno)
        return aluno


@router.post("/sincronizar")
def sincronizar_com_fasitech():
    """POST /alunos/sincronizar -> busca os alunos na API do FasiTech e
    salva no banco os que ainda não existem.

    Cada registro passa pela mesma validação do AlunoCreate: falta matricula
    ou periodo -> ignorado. CRG não é exigido (o FasiTech não manda esse
    campo) -- a correspondência entre acadêmico e socioeconômico é feita
    pela matrícula, não pela nota.
    """
    try:
        dados_brutos = buscar_dados_socioeconomicos()
    except RuntimeError as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except httpx.HTTPError as erro:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar o FasiTech: {erro}") from erro

    if not isinstance(dados_brutos, list):
        raise HTTPException(
            status_code=502,
            detail="Resposta do FasiTech não é uma lista de alunos (formato inesperado)",
        )

    importados = 0
    ignorados = 0

    with Session(engine) as session:
        for registro in dados_brutos:
            try:
                aluno_validado = AlunoCreate(**registro)
            except ValidationError:
                ignorados += 1
                continue

            ja_existe = session.execute(
                select(Usuarios).where(
                    Usuarios.matricula == aluno_validado.matricula,
                    Usuarios.periodo == aluno_validado.periodo,
                )
            ).scalars().first()

            if ja_existe is not None:
                ignorados += 1
                continue

            session.add(Usuarios(**aluno_validado.model_dump()))
            importados += 1

        session.commit()

    return {"importados": importados, "ignorados": ignorados}


@router.post("/atualizar-crg")
def atualizar_crg_do_historico():
    """POST /alunos/atualizar-crg -> lê o CSV de históricos acadêmicos
    (crg_historico.csv) e preenche CRG, nome e data de nascimento dos alunos
    já cadastrados, casando por matrícula -- são os três dados que o
    histórico tem e o FasiTech não manda. Alunos com matrícula fora do CSV
    não são alterados.
    """
    try:
        dados_do_historico = carregar_dados_do_historico()
    except FileNotFoundError as erro:
        raise HTTPException(status_code=503, detail=f"CSV de históricos não encontrado: {erro}") from erro

    atualizados = 0
    nao_encontrados = 0

    with Session(engine) as session:
        for matricula, dados in dados_do_historico.items():
            alunos = session.execute(
                select(Usuarios).where(Usuarios.matricula == matricula)
            ).scalars().all()

            if not alunos:
                nao_encontrados += 1
                continue

            for aluno in alunos:
                aluno.CRG = dados["CRG"]
                aluno.nome = dados["nome"]
                aluno.data_de_nascimento = dados["data_de_nascimento"]
            atualizados += len(alunos)

        session.commit()

    return {"atualizados": atualizados, "nao_encontrados": nao_encontrados}


@router.post("/preencher-legado")
def preencher_dados_legado():
    """POST /alunos/preencher-legado -> lê o DadosAgrupados.csv (a planilha
    manual usada antes da integração com o FasiTech) e preenche só os
    campos que ainda estão vazios no banco, casando por matrícula + período.

    Nunca mexe no CRG: o CRG desse CSV antigo está errado pra quase todo
    mundo (comparado ao histórico oficial) -- a fonte confiável é o
    histórico acadêmico, em /atualizar-crg.
    """
    try:
        dados_legado = carregar_dados_legado()
    except FileNotFoundError as erro:
        raise HTTPException(status_code=503, detail=f"CSV legado não encontrado: {erro}") from erro

    atualizados = 0
    campos_preenchidos = 0

    with Session(engine) as session:
        alunos = session.execute(select(Usuarios)).scalars().all()

        for aluno in alunos:
            dados = dados_legado.get((aluno.matricula, aluno.periodo))
            if not dados:
                continue

            mudou = False
            for campo, valor in dados.items():
                if valor is None:
                    continue
                if getattr(aluno, campo) is None:
                    setattr(aluno, campo, valor)
                    campos_preenchidos += 1
                    mudou = True

            if mudou:
                atualizados += 1

        session.commit()

    return {"atualizados": atualizados, "campos_preenchidos": campos_preenchidos}
