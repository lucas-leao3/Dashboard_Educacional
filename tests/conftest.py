"""Configuração compartilhada dos testes.

O fixture `client` sobe a aplicação FastAPI real (as mesmas rotas de
produção), mas trocando o banco por um **PostgreSQL** descartável -- criado do
zero em cada teste, apagado no final -- e a raiz dos lotes por uma pasta
temporária. Rodar os testes NUNCA toca no banco nem no data/ de verdade.

O schema sai das migrações do Alembic -- as mesmas que rodam em produção.
Modelo alterado sem revisão correspondente quebra a suíte inteira.

**Por que PostgreSQL e não SQLite.** A suíte já rodou em SQLite temporário, e
isso escondeu um defeito que só apareceu em produção: as colunas
socioeconômicas eram estreitas demais para as respostas do FasiTech, e o passo
1 do lote 2026-09-L01 quebrou com `StringDataRightTruncation`. O SQLite ignora
largura de VARCHAR, então os testes passavam. Ver docs/migracoes.md. Testar no
mesmo banco da produção é o que torna a suíte uma evidência de verdade.

**Custo:** rodar os testes passa a exigir Docker. O contêiner sobe uma vez por
sessão; cada teste ganha um banco novo clonado de um modelo com as migrações
já aplicadas (`CREATE DATABASE ... TEMPLATE`), que no PostgreSQL é cópia de
arquivo -- barato. Aplicar as migrações uma vez por teste custaria caro.
"""
import io
import os
import uuid
import zipfile
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from testcontainers.community.postgres import PostgresContainer

from app.core import config
from app.db.engine import get_session
from app.db.migracoes import aplicar_migracoes
from app.main import app

IMAGEM_POSTGRES = "postgres:17-alpine"   # a mesma do docker-compose.yml
BANCO_MODELO = "modelo"


@pytest.fixture(scope="session")
def postgres():
    """URL de admin de um PostgreSQL por sessão de teste.

    Padrão: contêiner descartável, encerrado no fim com o volume. Sem Docker na
    máquina, TEST_POSTGRES_URL aponta para um PostgreSQL já de pé (ex.:
    postgresql+psycopg://postgres@localhost:55432/postgres) -- continua sendo
    PostgreSQL, só muda quem o sobe."""
    externo = os.getenv("TEST_POSTGRES_URL")
    if externo:
        yield externo
        return
    with PostgresContainer(IMAGEM_POSTGRES, driver="psycopg") as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def modelo(postgres):
    """Cria UMA vez o banco `modelo`, com todas as migrações aplicadas, e
    devolve (url_de_admin, prefixo_de_url). Cada teste clona daqui."""
    url_admin = postgres
    base = url_admin.rsplit("/", 1)[0]

    admin = create_engine(url_admin, isolation_level="AUTOCOMMIT")
    with admin.connect() as conexao:
        # Só sobra modelo de sessão anterior em servidor externo, que não morre com a suíte.
        conexao.execute(text(f'DROP DATABASE IF EXISTS "{BANCO_MODELO}"'))
        conexao.execute(text(f'CREATE DATABASE "{BANCO_MODELO}"'))
    admin.dispose()

    engine_modelo = create_engine(f"{base}/{BANCO_MODELO}")
    aplicar_migracoes(engine_modelo)
    # Solta a conexão: CREATE DATABASE ... TEMPLATE recusa se alguém estiver
    # ligado no modelo.
    engine_modelo.dispose()
    return url_admin, base


@pytest_asyncio.fixture()
async def db_engine(modelo):
    """Um banco vazio e migrado por teste -- exposto à parte para testes que
    precisam checar o banco diretamente (ex.: campos que a API não devolve,
    como `excecao.detalhe`)."""
    url_admin, base = modelo
    nome = f"teste_{uuid.uuid4().hex[:12]}"
    admin = create_engine(url_admin, isolation_level="AUTOCOMMIT")
    with admin.connect() as conexao:
        conexao.execute(text(f'CREATE DATABASE "{nome}" TEMPLATE "{BANCO_MODELO}"'))

    engine_teste = create_engine(f"{base}/{nome}")
    try:
        yield engine_teste
    finally:
        engine_teste.dispose()
        with admin.connect() as conexao:
            conexao.execute(text(f'DROP DATABASE IF EXISTS "{nome}"'))
        admin.dispose()


@pytest_asyncio.fixture()
async def client(monkeypatch, tmp_path, db_engine):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.orm import sessionmaker

    SessionTeste = sessionmaker(bind=db_engine, expire_on_commit=False)

    def sessao_de_teste():
        with SessionTeste() as session:
            yield session

    app.dependency_overrides[get_session] = sessao_de_teste
    monkeypatch.setattr(config, "RAIZ_LOTES", tmp_path / "lotes")
    monkeypatch.setattr(config, "RAIZ_PROCESSADA", tmp_path / "processed")

    transporte = ASGITransport(app=app)
    async with AsyncClient(transport=transporte, base_url="http://test") as cliente:
        yield cliente

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def lote(client, db_engine):
    """Um lote ABERTO, criado direto no banco, com a pasta de históricos.

    A API não deixa lote aberto para trás (a importação cria e fecha na mesma
    transação); este estado só existe para testes que montam o banco à mão --
    view, triggers, relatório. Devolve o id."""
    from sqlalchemy.orm import Session

    from app.db.engine import Lote

    with Session(db_engine) as session:
        session.add(Lote(id="2026-09-L01", periodos_cobertos="2025.2", executado_por="Teste"))
        session.commit()
    (config.RAIZ_LOTES / "2026-09-L01" / "historicos").mkdir(parents=True)
    return "2026-09-L01"


@pytest.fixture()
def semear(db_engine, lote):
    """semear(matricula, periodo=..., academico=True, passo=1, **campos) grava
    direto no banco uma linha de `usuarios` (socioeconômico) e, se
    `academico`, um semestre em `crg_semestre` -- o que torna o aluno
    integrado. `passo` escolhe a ingestão (1 ou 2) da linha de usuarios."""
    from sqlalchemy.orm import Session

    from app.db.engine import CrgSemestre, Ingestao, Usuarios

    with Session(db_engine) as session:
        ingestoes = {passo: Ingestao(lote_id=lote, passo=passo) for passo in (1, 2)}
        session.add_all(ingestoes.values())
        session.commit()
        ids = {passo: i.id for passo, i in ingestoes.items()}

    def _semear(matricula: int, periodo: str = "2026.1", academico: bool = True, passo: int = 1, **campos):
        with Session(db_engine) as session:
            session.add(Usuarios(matricula=matricula, periodo=periodo, ingestao_id=ids[passo], **campos))
            if academico:
                session.merge(CrgSemestre(matricula=matricula, semestre="2025.1", crg=7.0, ingestao_id=ids[2]))
            session.commit()
    _semear.ingestoes = ids
    return _semear


# ---------------------------------------------------------------------------
# Importação: as duas fontes externas falsificadas. Nenhum teste chama o
# FasiTech de verdade nem lê PDF real -- carregar_historico devolve o que o
# teste registrou para o nome do arquivo.
# ---------------------------------------------------------------------------

def envelope(*registros):
    return {"url": "http://fasitech", "params": {}, "coletado_em": "2026-09-12T00:00:00+00:00",
            "paginas": [{"dados": list(registros), "pagina": 1, "total_paginas": 1}]}


def historico(matricula: int, crg: dict, emitido_em=date(2025, 12, 10), nome="ALUNO TESTE", nascimento="01/01/2000"):
    return {"matricula": matricula, "nome": nome, "data_de_nascimento": nascimento,
            "emitido_em": emitido_em, "crg_por_semestre": crg}


class Fontes:
    """`fasitech`: registros que a API devolve. `historicos`: nome do PDF sem
    extensão -> dict de carregar_historico, ou uma exceção para levantar."""

    def __init__(self):
        self.fasitech: list[dict] = []
        self.historicos: dict[str, dict | Exception] = {}
        self.erro_fasitech: Exception | None = None

    def buscar_paginas(self):
        if self.erro_fasitech is not None:
            raise self.erro_fasitech
        return envelope(*self.fasitech)

    def carregar_historico(self, caminho):
        lido = self.historicos[caminho.stem]
        if isinstance(lido, Exception):
            raise lido
        return lido


@pytest.fixture()
def fontes(monkeypatch):
    from app.services import importacao

    falsas = Fontes()
    monkeypatch.setattr(importacao, "buscar_paginas", falsas.buscar_paginas)
    monkeypatch.setattr(importacao, "carregar_historico", falsas.carregar_historico)
    return falsas


def zip_de(entradas: dict[str, bytes] | list[str]) -> bytes:
    """Lista de nomes -> cada PDF com conteúdo próprio (hash distinto)."""
    if isinstance(entradas, list):
        entradas = {nome: f"pdf {nome}".encode() for nome in entradas}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nome, conteudo in entradas.items():
            z.writestr(nome, conteudo)
    return buffer.getvalue()


@pytest.fixture()
def importar(client):
    """await importar(zip_bytes) -> resposta de POST /lotes/importar."""
    async def _importar(conteudo: bytes, responsavel: str | None = "Edinaldo", nome: str = "historicos.zip"):
        dados = {} if responsavel is None else {"responsavel": responsavel}
        return await client.post(
            "/lotes/importar", data=dados, files={"arquivo": (nome, conteudo, "application/zip")},
        )
    return _importar


# ---------------------------------------------------------------------------
# Assistente: LLM falsificado. Nenhum teste da suíte padrão chama o Groq.
# ---------------------------------------------------------------------------

class ProvedorFalso:
    """Devolve `respostas` em ordem (texto, ou exceção a levantar) e guarda em
    `chamadas` cada lista de mensagens recebida -- é por ela que os testes
    conferem o que sairia da máquina."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas: list[list[dict]] = []

    def completar(self, mensagens):
        self.chamadas.append(mensagens)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


@pytest.fixture()
def llm(client):
    """O provedor falso no lugar do Groq; `llm.respostas.append(...)` define o que ele diz."""
    from app.api.assistente import obter_provedor

    falso = ProvedorFalso()
    app.dependency_overrides[obter_provedor] = lambda: falso
    return falso
