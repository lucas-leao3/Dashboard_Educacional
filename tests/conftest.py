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
import uuid

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
    """Um PostgreSQL por sessão de teste. Encerrado no fim, com o volume."""
    with PostgresContainer(IMAGEM_POSTGRES, driver="psycopg") as container:
        yield container


@pytest.fixture(scope="session")
def modelo(postgres):
    """Cria UMA vez o banco `modelo`, com todas as migrações aplicadas, e
    devolve (url_de_admin, prefixo_de_url). Cada teste clona daqui."""
    url_admin = postgres.get_connection_url()
    base = url_admin.rsplit("/", 1)[0]

    admin = create_engine(url_admin, isolation_level="AUTOCOMMIT")
    with admin.connect() as conexao:
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
async def lote(client):
    """Um lote aberto, pronto pra receber as rotas de dados. Devolve o id."""
    resposta = await client.post("/lotes", json={"id": "2026-09-L01", "periodos_cobertos": ["2025.2", "2026.1"]})
    assert resposta.status_code == 201, resposta.json()
    return "2026-09-L01"
