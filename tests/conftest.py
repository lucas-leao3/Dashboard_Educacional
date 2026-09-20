"""Configuração compartilhada dos testes.

O fixture `client` sobe a aplicação FastAPI real (as mesmas rotas de
produção), mas trocando o banco por um SQLite temporário e vazio -- criado
do zero em cada teste, apagado no final -- e a raiz dos lotes por uma pasta
temporária. Rodar os testes NUNCA toca no banco nem no data/ de verdade.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import config
from app.db.engine import criar_schema, get_session
from app.main import app


@pytest_asyncio.fixture()
async def db_engine(tmp_path):
    """A mesma engine usada pelo fixture `client` -- exposta à parte para
    testes que precisam checar o banco diretamente (ex.: campos que a API
    não devolve, como `excecao.detalhe`)."""
    engine_teste = create_engine(f"sqlite:///{tmp_path / 'teste.sqlite'}")
    criar_schema(engine_teste)
    return engine_teste


@pytest_asyncio.fixture()
async def client(monkeypatch, tmp_path, db_engine):
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
