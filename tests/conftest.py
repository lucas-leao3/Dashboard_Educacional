"""Configuração compartilhada dos testes.

O fixture `client` sobe a aplicação FastAPI real (as mesmas rotas de
produção), mas trocando o banco de dados por um SQLite temporário e vazio
-- criado do zero em cada teste, apagado no final. Isso garante que rodar
os testes NUNCA toca no BancoDeDados.sqlite de verdade do projeto, e que
um teste não vê dados deixados por outro.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

import app.api.alunos as rotas_alunos
from app.db.engine import Base
from app.main import app


@pytest_asyncio.fixture()
async def client(monkeypatch, tmp_path):
    caminho_db_teste = tmp_path / "teste.sqlite"
    engine_teste = create_engine(f"sqlite:///{caminho_db_teste}")
    Base.metadata.create_all(bind=engine_teste)

    # api/alunos.py importou `engine` com "from ... import engine", então o
    # patch tem que ser feito no módulo que USA o nome, não em db/engine.py.
    monkeypatch.setattr(rotas_alunos, "engine", engine_teste)

    transporte = ASGITransport(app=app)
    async with AsyncClient(transport=transporte, base_url="http://test") as cliente:
        yield cliente
