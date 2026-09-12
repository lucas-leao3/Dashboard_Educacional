# Governança por Lote — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o backend gravar cada rodada como lote rastreável (insumos congelados em disco, `usuarios` append-only, CRG por semestre, exceções registradas), rodando em PostgreSQL dentro de Docker.

**Architecture:** Cinco tabelas novas (`lote`, `arquivo_fonte`, `ingestao`, `excecao`, `crg_semestre`) e a view `aluno_vigente` em SQLAlchemy portável (SQLite nos testes, PostgreSQL em produção). Um serviço `lotes.py` centraliza diretório, hash, ingestão e exceção; as três rotas existentes passam a exigir `?lote=` e a escrever linhas novas em vez de alterar. Sessão de banco vira dependência FastAPI (`get_session`) para os testes trocarem o banco sem `monkeypatch` de módulo.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic 2, psycopg 3, pypdf, PostgreSQL 17, Docker Compose, pytest + pytest-asyncio + httpx.

**Spec:** `docs/superpowers/specs/2026-09-12-implementacao-governanca-design.md` (implementa `docs/governanca_dados.md`).

## Global Constraints

- Todo DDL na forma portável: nada que só funcione em PostgreSQL (sem `GENERATED`, `JSONB`, `SERIAL` explícito). Testes rodam em SQLite temporário.
- `usuarios` é append-only: nenhuma rota faz `UPDATE` em `usuarios`. Sempre `INSERT` com `ingestao_id`.
- Toda rota de dados exige `?lote=<id>` e devolve `400` se o lote não existe.
- `/sincronizar` grava `fasitech.json` **antes** de abrir sessão no banco.
- Nenhum PDF real, CSV real ou dado pessoal entra em `tests/`. Fixtures são sintéticas.
- Comandos: `.venv/bin/python -m pytest -q` da raiz do repo. Todos os testes existentes devem continuar passando ao fim de cada task, exceto os explicitamente reescritos.
- Commits em português, prefixo `feat:`/`test:`/`refactor:`/`docs:`/`chore:`, terminando com `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Timestamps em UTC: `datetime.now(timezone.utc)`.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/core/config.py` (modificar) | `DATABASE_URL`, `RAIZ_LOTES` além do FasiTech |
| `backend/app/db/engine.py` (reescrever) | `engine`, `SessionLocal`, `get_session`, modelos ORM, `criar_schema(engine)` |
| `backend/app/db/vigente.py` (criar) | SQL da view `aluno_vigente` e `Table` para consultá-la |
| `backend/app/services/lotes.py` (criar) | diretório do lote, sha256, `registrar_arquivo`, `abrir_ingestao`, `fechar_ingestao`, `registrar_excecao`, `exigir_lote` |
| `backend/app/services/fasitech_client.py` (modificar) | `buscar_paginas() -> dict` (envelope), `registros_do_envelope`, `congelar_envelope` |
| `backend/app/services/crg_historico.py` (reescrever) | `extrair_texto`, `interpretar_historico`, `semestre_da_data`, `aplicar_regra_do_zero` |
| `backend/app/services/dados_legado.py` (manter) | já recebe `caminho`; rota passa o do lote |
| `backend/app/schemas/lotes.py` (criar) | `LoteCreate`, `IngestaoOut`, `LoteOut` |
| `backend/app/schemas/alunos.py` (modificar) | `AlunoOut` ganha `ingestao_id` |
| `backend/app/api/lotes.py` (criar) | `POST /lotes`, `GET /lotes`, `GET /lotes/{id}` |
| `backend/app/api/alunos.py` (reescrever) | rotas com `?lote=`, leitura pela view |
| `backend/app/main.py` (modificar) | lifespan com `criar_schema`, router de lotes |
| `tests/conftest.py` (modificar) | `dependency_overrides[get_session]`, `RAIZ_LOTES` em `tmp_path`, fixture `lote` |
| `tests/test_lotes.py`, `tests/test_crg_historico.py`, `tests/test_servico_lotes.py` (criar), `tests/test_alunos.py` (modificar) | |
| `backend/Dockerfile`, `docker-compose.yml`, `backend/.env.example`, `backend/.dockerignore` (criar) | |
| `pyproject.toml` (modificar) | `psycopg[binary]`, `pypdf` |
| `API_README.md`, `docs/governanca_dados.md` §7 (modificar) | |

---

### Task 1: Configuração, engine por env e sessão como dependência

**Files:**
- Modify: `pyproject.toml`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/db/engine.py` (só a parte de engine/sessão; modelos novos ficam na Task 2)
- Modify: `backend/app/api/alunos.py` (trocar `Session(engine)` por `Depends(get_session)`)
- Modify: `backend/app/main.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Produces: `app.core.config.DATABASE_URL: str`, `app.core.config.RAIZ_LOTES: Path`; `app.db.engine.engine`, `app.db.engine.SessionLocal`, `app.db.engine.get_session()` (generator dependency), `app.db.engine.criar_schema(engine) -> None`.

- [ ] **Step 1: Dependências**

Em `pyproject.toml`, na lista `dependencies`, acrescente:

```toml
    "psycopg[binary]>=3.2",
    "pypdf>=5.0",
```

Rode `.venv/bin/pip install -e ".[dev]" -q` e confirme com `.venv/bin/python -c "import psycopg, pypdf; print('ok')"`.

- [ ] **Step 2: Config**

Substitua `backend/app/core/config.py` por:

```python
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# URL (base) da API do FasiTech que devolve os dados socioeconômicos por aluno,
# paginada -- ver backend/.env pro histórico das URLs testadas até chegar nela.
FASITECH_URL = os.getenv("FASITECH_URL", "")
FASITECH_TOKEN = os.getenv("FASITECH_TOKEN", "")

# Banco. Em produção (docker compose) é PostgreSQL; sem variável cai num
# SQLite local pra desenvolvimento rápido. Os testes trocam por um SQLite
# temporário via dependency_overrides -- ver tests/conftest.py.
_RAIZ_REPO = Path(__file__).resolve().parents[3]
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{_RAIZ_REPO / 'backend' / 'app' / 'db' / 'BancoDeDados.sqlite'}",
)

# Onde ficam os lotes de dados brutos (docs/governanca_dados.md, seção 3.2).
# No container é /data/raw/lotes (volume ./data). Os serviços leem este nome
# em tempo de chamada (config.RAIZ_LOTES), então os testes podem trocá-lo.
RAIZ_LOTES = Path(os.getenv("DADOS_RAW_DIR", _RAIZ_REPO / "data" / "raw" / "lotes"))
```

- [ ] **Step 3: Engine e sessão**

Em `backend/app/db/engine.py`, remova a função `criando_usuario` inteira (só o `legado/` a usava, e via um import que não existe mais), remova as linhas `pastal_atual`, `caminho_DB`, `engine = create_engine(...)` e `Base.metadata.create_all(bind=engine)`. Deixe a classe `Usuarios` como está por enquanto. Coloque no topo:

```python
from typing import Iterator

from sqlalchemy import create_engine, String, Integer, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker

from app.core.config import DATABASE_URL
```

e no final do arquivo:

```python
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dependência FastAPI: uma sessão por request. Os testes a substituem
    por uma sessão num SQLite temporário (app.dependency_overrides)."""
    with SessionLocal() as session:
        yield session


def criar_schema(engine) -> None:
    """Cria tabelas que faltam. Chamado no lifespan da aplicação, nunca no
    import -- importar um módulo não pode depender de banco de pé."""
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 4: Rotas usam a dependência**

Em `backend/app/api/alunos.py`, troque o import `from app.db.engine import Usuarios, engine` por:

```python
from fastapi import APIRouter, Depends, HTTPException
from app.db.engine import Usuarios, get_session
```

e em cada rota substitua `with Session(engine) as session:` por um parâmetro `session: Session = Depends(get_session)` na assinatura, desindentando o corpo. Exemplo para a primeira:

```python
@router.get("", response_model=list[AlunoOut])
def listar_alunos(session: Session = Depends(get_session)):
    """GET /alunos -> lista todos os alunos (acadêmico + socioeconômico) salvos no banco."""
    return session.execute(select(Usuarios)).scalars().all()
```

Faça o mesmo em `buscar_aluno`, `criar_aluno`, `sincronizar_com_fasitech`, `atualizar_crg_do_historico`, `preencher_dados_legado`. Nas rotas que chamam serviço externo antes do banco (sincronizar, atualizar-crg, preencher-legado) a ordem não muda: o `try/except` do serviço continua antes do uso da sessão.

- [ ] **Step 5: Lifespan**

Substitua `backend/app/main.py` por:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.alunos import router as alunos_router
from app.db.engine import criar_schema, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    criar_schema(engine)
    yield


app = FastAPI(title="Dashboard Educacional API", lifespan=lifespan)

app.include_router(alunos_router)


@app.get("/")
def raiz():
    """Health-check simples, só pra confirmar que a API está de pé."""
    return {"status": "ok"}
```

- [ ] **Step 6: conftest com dependency_overrides**

Substitua `tests/conftest.py` por:

```python
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
async def client(monkeypatch, tmp_path):
    engine_teste = create_engine(f"sqlite:///{tmp_path / 'teste.sqlite'}")
    criar_schema(engine_teste)
    SessionTeste = sessionmaker(bind=engine_teste, expire_on_commit=False)

    def sessao_de_teste():
        with SessionTeste() as session:
            yield session

    app.dependency_overrides[get_session] = sessao_de_teste
    monkeypatch.setattr(config, "RAIZ_LOTES", tmp_path / "lotes")

    transporte = ASGITransport(app=app)
    async with AsyncClient(transport=transporte, base_url="http://test") as cliente:
        yield cliente

    app.dependency_overrides.clear()
```

- [ ] **Step 7: Rodar os testes**

Run: `.venv/bin/python -m pytest -q`
Expected: `19 passed`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml backend/app/core/config.py backend/app/db/engine.py backend/app/api/alunos.py backend/app/main.py tests/conftest.py
git commit -m "refactor: engine por DATABASE_URL, sessão como dependência e schema no lifespan

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Modelos de governança e view `aluno_vigente`

**Files:**
- Modify: `backend/app/db/engine.py`
- Create: `backend/app/db/vigente.py`
- Create: `tests/test_schema.py`

**Interfaces:**
- Produces: classes ORM `Lote`, `ArquivoFonte`, `Ingestao`, `Excecao`, `CrgSemestre`; `Usuarios.ingestao_id: int` (NOT NULL, FK `ingestao.id`); `app.db.vigente.aluno_vigente: Table` (mesmas colunas de `usuarios` + `rn`); `criar_schema` também cria a view.
- Constantes: `Ingestao.PASSO_MANUAL = 0`, `PASSO_SINCRONIZAR = 1`, `PASSO_CRG = 2`, `PASSO_LEGADO = 3`.

- [ ] **Step 1: Teste do schema e da view**

Crie `tests/test_schema.py`:

```python
"""A view aluno_vigente resolve, por (matricula, periodo), a linha da
ingestão mais recente -- é ela que o dashboard lê (governança, seção 4.5)."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.db.engine import CrgSemestre, Ingestao, Lote, Usuarios, criar_schema
from app.db.vigente import aluno_vigente


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.sqlite'}")
    criar_schema(engine)
    return engine


def test_criar_schema_cria_tabelas_e_view(tmp_path):
    engine = _engine(tmp_path)
    inspector = inspect(engine)
    assert {"lote", "arquivo_fonte", "ingestao", "excecao", "crg_semestre", "usuarios"} <= set(inspector.get_table_names())
    assert "aluno_vigente" in inspector.get_view_names()


def test_criar_schema_e_idempotente(tmp_path):
    engine = _engine(tmp_path)
    criar_schema(engine)  # segunda chamada não pode falhar por view já existir
    assert "aluno_vigente" in inspect(engine).get_view_names()


def test_vigente_resolve_pela_ingestao_mais_recente(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        lote = Lote(id="2026-09-L01", periodos_cobertos="2026.1", executado_em=datetime.now(timezone.utc))
        s.add(lote)
        i1 = Ingestao(lote_id=lote.id, passo=1, registros_lidos=0, registros_aceitos=0, registros_rejeitados=0)
        i2 = Ingestao(lote_id=lote.id, passo=2, registros_lidos=0, registros_aceitos=0, registros_rejeitados=0)
        s.add_all([i1, i2])
        s.flush()
        s.add(Usuarios(matricula=1, periodo="2026.1", renda="A", ingestao_id=i1.id))
        s.add(Usuarios(matricula=1, periodo="2026.1", renda="B", ingestao_id=i2.id))
        s.add(Usuarios(matricula=2, periodo="2026.1", renda="C", ingestao_id=i1.id))
        s.add(CrgSemestre(matricula=1, semestre="2025.1", crg=7.5, ingestao_id=i2.id))
        s.commit()

        linhas = s.execute(select(aluno_vigente).order_by(aluno_vigente.c.matricula)).all()
        assert [(l.matricula, l.renda, l.ingestao_id) for l in linhas] == [(1, "B", i2.id), (2, "C", i1.id)]
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_schema.py -q`
Expected: FAIL com `ImportError` (`Lote` não existe).

- [ ] **Step 3: Modelos**

Em `backend/app/db/engine.py`, ajuste os imports do SQLAlchemy para:

```python
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker
```

Acrescente, logo depois de `class Base(DeclarativeBase): pass`, e **antes** de `Usuarios`:

```python
def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Lote(Base):
    """Uma rodada completa das rotas (governança, seção 3.1). Espelha
    raw/lotes/<id>/ no banco."""
    __tablename__ = "lote"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)       # 2026-09-L01
    executado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora)
    periodos_cobertos: Mapped[str] = mapped_column(String(100))        # '2025.2;2026.1'
    executado_por: Mapped[str | None] = mapped_column(String(100))
    observacao: Mapped[str | None] = mapped_column(Text)


class ArquivoFonte(Base):
    """De onde veio: um arquivo bruto do lote, identificado pelo hash."""
    __tablename__ = "arquivo_fonte"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    lote_id: Mapped[str] = mapped_column(ForeignKey("lote.id"))
    nome_original: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(30))   # pdf_historico | csv_legado | api_fasitech
    tamanho_bytes: Mapped[int] = mapped_column(Integer)


class Ingestao(Base):
    """Um passo do lote. Toda escrita em usuarios/crg_semestre/excecao
    referencia uma ingestão -- é o que torna 'rodei o endpoint' rastreável."""
    __tablename__ = "ingestao"
    __table_args__ = (UniqueConstraint("lote_id", "passo", name="ux_ingestao_lote_passo"),)

    PASSO_MANUAL = 0
    PASSO_SINCRONIZAR = 1
    PASSO_CRG = 2
    PASSO_LEGADO = 3

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[str] = mapped_column(ForeignKey("lote.id"))
    passo: Mapped[int] = mapped_column(Integer)
    arquivo_sha256: Mapped[str | None] = mapped_column(ForeignKey("arquivo_fonte.sha256"))
    executado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora)
    registros_lidos: Mapped[int] = mapped_column(Integer, default=0)
    registros_aceitos: Mapped[int] = mapped_column(Integer, default=0)
    registros_rejeitados: Mapped[int] = mapped_column(Integer, default=0)


class Excecao(Base):
    """O que não casou, com motivo. Substitui os contadores que somiam."""
    __tablename__ = "excecao"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingestao_id: Mapped[int] = mapped_column(ForeignKey("ingestao.id"))
    matricula: Mapped[int | None] = mapped_column(BigInteger)
    periodo: Mapped[str | None] = mapped_column(String(15))
    motivo: Mapped[str] = mapped_column(String(30))  # sem_academico | sem_socioeconomico | matricula_invalida | sem_periodo | duplicado
    detalhe: Mapped[str | None] = mapped_column(Text)


class CrgSemestre(Base):
    """CRG por semestre letivo, extraído do PDF do SIGAA (governança, 4.6).
    crg NULL = semestre ainda não apurado na data de emissão."""
    __tablename__ = "crg_semestre"

    matricula: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    semestre: Mapped[str] = mapped_column(String(6), primary_key=True)   # '2024.1'
    ingestao_id: Mapped[int] = mapped_column(ForeignKey("ingestao.id"), primary_key=True)
    crg: Mapped[float | None] = mapped_column(Float)
```

Na classe `Usuarios`, troque `matricula: Mapped[int] = mapped_column(Integer)` por `mapped_column(BigInteger)` (12 dígitos estouram `Integer` no PostgreSQL) e acrescente, logo após `id`:

```python
    ingestao_id: Mapped[int] = mapped_column(ForeignKey("ingestao.id"))
```

Substitua `criar_schema` por:

```python
def criar_schema(engine) -> None:
    """Cria tabelas e a view aluno_vigente que faltam. Chamado no lifespan,
    nunca no import. Idempotente: pode rodar a cada subida."""
    from app.db.vigente import VIEW_SQL, aluno_vigente

    Base.metadata.create_all(bind=engine)
    if aluno_vigente.name not in inspect(engine).get_view_names():
        with engine.begin() as conexao:
            conexao.execute(text(VIEW_SQL))
```

- [ ] **Step 4: A view**

Crie `backend/app/db/vigente.py`:

```python
"""aluno_vigente: o 'valor de agora' de cada (matricula, periodo) -- a linha
da ingestão mais recente (docs/governanca_dados.md, 4.5).

A view existe no banco (VIEW_SQL, criada por criar_schema) para quem
consulta por SQL, e aqui como Table para o código consultar com select().
Ela fica num MetaData separado de propósito: create_all não deve tentar
criá-la como tabela.
"""
from sqlalchemy import Column, Integer, MetaData, Table

from app.db.engine import Usuarios

VIEW_SQL = """
CREATE VIEW aluno_vigente AS
SELECT * FROM (
    SELECT u.*, ROW_NUMBER() OVER (
        PARTITION BY u.matricula, u.periodo ORDER BY u.ingestao_id DESC, u.id DESC
    ) AS rn
    FROM usuarios u
) ranked WHERE rn = 1
"""
# u.id DESC desempata quando duas linhas nascem na mesma ingestão -- acontece
# no passo manual (0), que é reaproveitado entre chamadas de POST /alunos.

aluno_vigente = Table(
    "aluno_vigente",
    MetaData(),
    *[Column(c.name, c.type) for c in Usuarios.__table__.columns],
    Column("rn", Integer),
)
```

- [ ] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest tests/test_schema.py -q`
Expected: `3 passed`. Os testes antigos em `test_alunos.py` vão **quebrar** agora (`ingestao_id` NOT NULL sem valor) — esperado; são reescritos nas Tasks 7–9. Confirme que só eles quebram: `.venv/bin/python -m pytest -q tests/test_schema.py tests/test_alunos.py::test_lista_alunos_comeca_vazia` → `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/engine.py backend/app/db/vigente.py tests/test_schema.py
git commit -m "feat: tabelas lote/arquivo_fonte/ingestao/excecao/crg_semestre e view aluno_vigente

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Serviço de lotes (diretório, hash, ingestão, exceção)

**Files:**
- Create: `backend/app/services/lotes.py`
- Create: `tests/test_servico_lotes.py`

**Interfaces:**
- Produces:
  - `caminho_do_lote(lote_id: str) -> Path` — `config.RAIZ_LOTES / lote_id`
  - `criar_diretorio(lote_id) -> Path` — cria `<lote>/historicos/`; erro se já existe
  - `sha256_de(caminho: Path) -> str`
  - `registrar_arquivo(session, lote_id, caminho, tipo) -> ArquivoFonte | None` — `None` se o hash já existe (duplicado)
  - `exigir_lote(session, lote_id) -> Lote` — levanta `HTTPException(400)` se não existe
  - `abrir_ingestao(session, lote_id, passo, arquivo_sha256=None) -> Ingestao` — para `passo=0` reaproveita a existente
  - `fechar_ingestao(session, ingestao, lidos, aceitos, rejeitados) -> None`
  - `registrar_excecao(session, ingestao, motivo, matricula=None, periodo=None, detalhe=None) -> None`

- [ ] **Step 1: Testes**

Crie `tests/test_servico_lotes.py`:

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from fastapi import HTTPException
import pytest

from app.core import config
from app.db.engine import ArquivoFonte, Excecao, Ingestao, Lote, criar_schema
from app.services import lotes


@pytest.fixture()
def sessao(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ_LOTES", tmp_path / "lotes")
    engine = create_engine(f"sqlite:///{tmp_path / 't.sqlite'}")
    criar_schema(engine)
    with Session(engine) as s:
        s.add(Lote(id="L01", periodos_cobertos="2026.1"))
        s.commit()
        yield s


def test_criar_diretorio_cria_historicos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ_LOTES", tmp_path / "lotes")
    caminho = lotes.criar_diretorio("2026-09-L01")
    assert caminho == tmp_path / "lotes" / "2026-09-L01"
    assert (caminho / "historicos").is_dir()
    with pytest.raises(FileExistsError):
        lotes.criar_diretorio("2026-09-L01")


def test_registrar_arquivo_grava_hash_e_detecta_duplicado(sessao, tmp_path):
    arquivo = tmp_path / "a.pdf"
    arquivo.write_bytes(b"conteudo")
    registro = lotes.registrar_arquivo(sessao, "L01", arquivo, "pdf_historico")
    assert registro.sha256 == lotes.sha256_de(arquivo)
    assert registro.tamanho_bytes == 8
    assert registro.nome_original == "a.pdf"
    assert lotes.registrar_arquivo(sessao, "L01", arquivo, "pdf_historico") is None


def test_exigir_lote_inexistente_da_400(sessao):
    assert lotes.exigir_lote(sessao, "L01").id == "L01"
    with pytest.raises(HTTPException) as erro:
        lotes.exigir_lote(sessao, "L99")
    assert erro.value.status_code == 400


def test_abrir_e_fechar_ingestao(sessao):
    ingestao = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_SINCRONIZAR)
    lotes.fechar_ingestao(sessao, ingestao, lidos=3, aceitos=2, rejeitados=1)
    gravada = sessao.get(Ingestao, ingestao.id)
    assert (gravada.registros_lidos, gravada.registros_aceitos, gravada.registros_rejeitados) == (3, 2, 1)


def test_abrir_ingestao_manual_reaproveita(sessao):
    a = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_MANUAL)
    b = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_MANUAL)
    assert a.id == b.id


def test_abrir_ingestao_repetida_do_mesmo_passo_da_409(sessao):
    lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    with pytest.raises(HTTPException) as erro:
        lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    assert erro.value.status_code == 409


def test_registrar_excecao(sessao):
    ingestao = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    lotes.registrar_excecao(sessao, ingestao, "sem_academico", matricula=123, periodo="2026.1")
    sessao.commit()
    excecoes = sessao.execute(select(Excecao)).scalars().all()
    assert [(e.motivo, e.matricula, e.periodo) for e in excecoes] == [("sem_academico", 123, "2026.1")]
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_servico_lotes.py -q`
Expected: FAIL com `ImportError` em `app.services.lotes`.

- [ ] **Step 3: Implementação**

Crie `backend/app/services/lotes.py`:

```python
"""Operações comuns a todo lote (docs/governanca_dados.md, seções 3 e 5):
diretório em raw/lotes/<id>/, hash dos insumos, abertura e fechamento de
ingestão, registro de exceção. As rotas usam isto em vez de repetir."""
import hashlib
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.db.engine import ArquivoFonte, Excecao, Ingestao, Lote


def caminho_do_lote(lote_id: str) -> Path:
    # Lido em tempo de chamada, não no import: os testes trocam config.RAIZ_LOTES.
    return config.RAIZ_LOTES / lote_id


def criar_diretorio(lote_id: str) -> Path:
    caminho = caminho_do_lote(lote_id)
    (caminho / "historicos").mkdir(parents=True, exist_ok=False)
    return caminho


def sha256_de(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def registrar_arquivo(session: Session, lote_id: str, caminho: Path, tipo: str) -> ArquivoFonte | None:
    """Registra o arquivo em arquivo_fonte. Devolve None se o mesmo conteúdo
    (mesmo hash) já entrou -- em qualquer lote."""
    sha = sha256_de(caminho)
    if session.get(ArquivoFonte, sha) is not None:
        return None
    registro = ArquivoFonte(
        sha256=sha,
        lote_id=lote_id,
        nome_original=caminho.name,
        tipo=tipo,
        tamanho_bytes=caminho.stat().st_size,
    )
    session.add(registro)
    session.flush()
    return registro


def exigir_lote(session: Session, lote_id: str) -> Lote:
    lote = session.get(Lote, lote_id)
    if lote is None:
        raise HTTPException(status_code=400, detail=f"Lote '{lote_id}' não existe. Crie com POST /lotes.")
    return lote


def abrir_ingestao(session: Session, lote_id: str, passo: int, arquivo_sha256: str | None = None) -> Ingestao:
    """Uma ingestão por passo por lote. O passo manual (0) é reaproveitado
    entre chamadas; os outros só podem rodar uma vez por lote."""
    existente = session.execute(
        select(Ingestao).where(Ingestao.lote_id == lote_id, Ingestao.passo == passo)
    ).scalars().first()
    if existente is not None:
        if passo == Ingestao.PASSO_MANUAL:
            return existente
        raise HTTPException(
            status_code=409,
            detail=f"Passo {passo} já foi executado no lote '{lote_id}' (ingestão {existente.id}).",
        )
    ingestao = Ingestao(lote_id=lote_id, passo=passo, arquivo_sha256=arquivo_sha256)
    session.add(ingestao)
    session.flush()
    return ingestao


def fechar_ingestao(session: Session, ingestao: Ingestao, lidos: int, aceitos: int, rejeitados: int) -> None:
    ingestao.registros_lidos += lidos
    ingestao.registros_aceitos += aceitos
    ingestao.registros_rejeitados += rejeitados
    session.commit()


def registrar_excecao(
    session: Session,
    ingestao: Ingestao,
    motivo: str,
    matricula: int | None = None,
    periodo: str | None = None,
    detalhe: str | None = None,
) -> None:
    session.add(Excecao(ingestao_id=ingestao.id, matricula=matricula, periodo=periodo, motivo=motivo, detalhe=detalhe))
```

- [ ] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_servico_lotes.py tests/test_schema.py -q`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/lotes.py tests/test_servico_lotes.py
git commit -m "feat: serviço de lotes (diretório, sha256, ingestão, exceção)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Rotas `/lotes`

**Files:**
- Create: `backend/app/schemas/lotes.py`
- Create: `backend/app/api/lotes.py`
- Modify: `backend/app/main.py`
- Modify: `tests/conftest.py` (fixture `lote`)
- Create: `tests/test_lotes.py`

**Interfaces:**
- Produces: `POST /lotes` (body `LoteCreate`, 201 → `LoteOut`, 409 se existe), `GET /lotes` → `list[LoteOut]`, `GET /lotes/{id}` → `LoteOut` (404). `LoteOut` inclui `ingestoes: list[IngestaoOut]` e `excecoes_por_motivo: dict[str, int]`.
- Fixture `lote` em `tests/conftest.py`: cria `2026-09-L01` via API e devolve o id.

- [ ] **Step 1: Testes**

Crie `tests/test_lotes.py`:

```python
from app.core import config


async def test_criar_lote_cria_diretorio_e_registro(client):
    resposta = await client.post("/lotes", json={
        "id": "2026-09-L01",
        "periodos_cobertos": ["2025.2", "2026.1"],
        "executado_por": "edinaldo",
    })
    assert resposta.status_code == 201, resposta.json()
    corpo = resposta.json()
    assert corpo["id"] == "2026-09-L01"
    assert corpo["periodos_cobertos"] == ["2025.2", "2026.1"]
    assert corpo["ingestoes"] == []
    assert corpo["excecoes_por_motivo"] == {}
    assert (config.RAIZ_LOTES / "2026-09-L01" / "historicos").is_dir()


async def test_criar_lote_duplicado_da_409(client):
    body = {"id": "2026-09-L01", "periodos_cobertos": ["2026.1"]}
    await client.post("/lotes", json=body)
    resposta = await client.post("/lotes", json=body)
    assert resposta.status_code == 409


async def test_criar_lote_com_id_invalido_da_422(client):
    resposta = await client.post("/lotes", json={"id": "../fora", "periodos_cobertos": ["2026.1"]})
    assert resposta.status_code == 422


async def test_listar_e_buscar_lote(client):
    await client.post("/lotes", json={"id": "2026-09-L01", "periodos_cobertos": ["2026.1"]})
    lista = await client.get("/lotes")
    assert [l["id"] for l in lista.json()] == ["2026-09-L01"]
    um = await client.get("/lotes/2026-09-L01")
    assert um.status_code == 200
    assert (await client.get("/lotes/L99")).status_code == 404
```

Acrescente ao final de `tests/conftest.py`:

```python
@pytest_asyncio.fixture()
async def lote(client):
    """Um lote aberto, pronto pra receber as rotas de dados. Devolve o id."""
    resposta = await client.post("/lotes", json={"id": "2026-09-L01", "periodos_cobertos": ["2025.2", "2026.1"]})
    assert resposta.status_code == 201, resposta.json()
    return "2026-09-L01"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_lotes.py -q`
Expected: 4 FAIL com 404 (rota não existe).

- [ ] **Step 3: Schemas**

Crie `backend/app/schemas/lotes.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoteCreate(BaseModel):
    # Também é nome de pasta em raw/lotes/: só letras, dígitos, '-' e '_'.
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,20}$", examples=["2026-09-L01"])
    periodos_cobertos: list[str] = Field(min_length=1, examples=[["2025.2", "2026.1"]])
    executado_por: str | None = None
    observacao: str | None = None


class IngestaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    passo: int
    arquivo_sha256: str | None
    executado_em: datetime
    registros_lidos: int
    registros_aceitos: int
    registros_rejeitados: int


class LoteOut(BaseModel):
    id: str
    executado_em: datetime
    periodos_cobertos: list[str]
    executado_por: str | None
    observacao: str | None
    ingestoes: list[IngestaoOut]
    excecoes_por_motivo: dict[str, int]
```

- [ ] **Step 4: Rotas**

Crie `backend/app/api/lotes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.engine import Excecao, Ingestao, Lote, get_session
from app.schemas.lotes import IngestaoOut, LoteCreate, LoteOut
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
    session.add(lote)
    session.commit()
    session.refresh(lote)
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
```

Em `backend/app/main.py`, acrescente `from app.api.lotes import router as lotes_router` e `app.include_router(lotes_router)` após o router de alunos.

- [ ] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest tests/test_lotes.py tests/test_servico_lotes.py tests/test_schema.py -q`
Expected: `14 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/lotes.py backend/app/api/lotes.py backend/app/main.py tests/conftest.py tests/test_lotes.py
git commit -m "feat: rotas POST/GET /lotes

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Extração do histórico SIGAA por semestre

**Files:**
- Rewrite: `backend/app/services/crg_historico.py`
- Create: `tests/test_crg_historico.py`

**Interfaces:**
- Produces:
  - `extrair_texto(caminho_pdf: Path) -> str` — pypdf, `extraction_mode="layout"`, páginas unidas por `\n`
  - `semestre_da_data(d: date) -> str` — mês ≤ 6 → `"AAAA.1"`, senão `"AAAA.2"`
  - `interpretar_historico(texto: str) -> dict` com chaves `matricula: int`, `nome: str`, `data_de_nascimento: str` (dd/mm/aaaa), `emitido_em: date`, `crg_por_semestre: dict[str, float | None]` (regra do zero já aplicada). Levanta `ValueError` se faltar matrícula, emissão ou bloco de semestres.
  - `ultimo_crg_apurado(crg_por_semestre) -> float | None` — valor do maior semestre não nulo
  - `carregar_historico(caminho_pdf: Path) -> dict` = `interpretar_historico(extrair_texto(caminho_pdf))`

- [ ] **Step 1: Testes com texto sintético**

Crie `tests/test_crg_historico.py`:

```python
"""Interpretação do texto do histórico SIGAA. Nenhum PDF real entra aqui
(dado pessoal): o texto abaixo imita o layout que pypdf devolve."""
from datetime import date

import pytest

from app.services.crg_historico import interpretar_historico, semestre_da_data, ultimo_crg_apurado

TEXTO = """
Histórico Acadêmico - Emitido em: 10/12/2025 às 15:43
 Dados Pessoais
Nome: ALUNA DE TESTE SILVA          Matrícula: 202016040099
Data de Nascimento: 05/03/2001      UF de Nascimento:CAMETÁ/PA
 Índices Acadêmicos
Ênfase: - CRG: 7.9662
                Coeficiente de Rendimento por Semestre Letivo
2020/Sem2: 10.0    2021/Sem1: 0.00    2021/Sem2: 7.50    2022/Sem1: 7.75
2025/Sem1: 8.29    2025/Sem2: 0.00    2026/Sem1: 0.00
 Componentes Curriculares Obrigatórios Pendentes:14
"""


def test_semestre_da_data():
    assert semestre_da_data(date(2025, 6, 30)) == "2025.1"
    assert semestre_da_data(date(2025, 7, 1)) == "2025.2"
    assert semestre_da_data(date(2025, 12, 10)) == "2025.2"


def test_interpreta_dados_pessoais_e_emissao():
    h = interpretar_historico(TEXTO)
    assert h["matricula"] == 202016040099
    assert h["nome"] == "ALUNA DE TESTE SILVA"
    assert h["data_de_nascimento"] == "05/03/2001"
    assert h["emitido_em"] == date(2025, 12, 10)


def test_regra_do_zero_anula_semestres_a_partir_da_emissao():
    """Emitido em 2025.2: 2025.2 e 2026.1 viram None; o 0.00 de 2021.1 é
    nota real e fica (governança, 4.6)."""
    crg = interpretar_historico(TEXTO)["crg_por_semestre"]
    assert crg == {
        "2020.2": 10.0, "2021.1": 0.0, "2021.2": 7.5, "2022.1": 7.75,
        "2025.1": 8.29, "2025.2": None, "2026.1": None,
    }


def test_ultimo_crg_apurado_ignora_nulos():
    crg = interpretar_historico(TEXTO)["crg_por_semestre"]
    assert ultimo_crg_apurado(crg) == 8.29
    assert ultimo_crg_apurado({"2026.1": None}) is None


def test_texto_sem_bloco_de_semestres_da_erro():
    with pytest.raises(ValueError):
        interpretar_historico("Emitido em: 10/12/2025\nMatrícula: 202016040099\nnada aqui")


def test_texto_sem_matricula_da_erro():
    with pytest.raises(ValueError):
        interpretar_historico("Emitido em: 10/12/2025\n2020/Sem2: 10.0")
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_crg_historico.py -q`
Expected: FAIL com `ImportError` (`interpretar_historico`).

- [ ] **Step 3: Implementação**

Substitua `backend/app/services/crg_historico.py` inteiro por:

```python
"""Lê o histórico acadêmico do SIGAA (PDF) e devolve o CRG por semestre
letivo -- é isso que dá o progresso do aluno (docs/governanca_dados.md, 4.6).

Dividido em duas funções de propósito: extrair_texto depende de PDF e
pypdf; interpretar_historico é texto puro e testável sem PDF real.
"""
import re
from datetime import date
from pathlib import Path

from pypdf import PdfReader

_EMISSAO = re.compile(r"Emitido em:\s*(\d{2})/(\d{2})/(\d{4})")
_MATRICULA = re.compile(r"Matrícula:\s*(\d{12})")
_NOME = re.compile(r"Nome:\s*(.+?)\s{2,}Matrícula")
_NASCIMENTO = re.compile(r"Data de Nascimento:\s*(\d{2}/\d{2}/\d{4})")
_TITULO_BLOCO = "Coeficiente de Rendimento por Semestre"
_FIM_BLOCO = "Componentes Curriculares"
_SEMESTRE = re.compile(r"(\d{4})/Sem([12]):\s*([\d.]+)")


def extrair_texto(caminho_pdf: Path) -> str:
    # layout preserva a posição das colunas; sem ele o bloco de semestres
    # se separa do título e 'Nome:' perde o valor (validado nos 56 PDFs).
    leitor = PdfReader(str(caminho_pdf))
    return "\n".join(pagina.extract_text(extraction_mode="layout") or "" for pagina in leitor.pages)


def semestre_da_data(d: date) -> str:
    return f"{d.year}.{1 if d.month <= 6 else 2}"


def aplicar_regra_do_zero(crg_por_semestre: dict[str, float], emitido_em: date) -> dict[str, float | None]:
    """Semestre igual ou posterior ao da emissão ainda não foi apurado: o
    0.00 que o SIGAA imprime ali não é nota. Antes disso, zero é zero."""
    corte = semestre_da_data(emitido_em)
    return {sem: (None if sem >= corte else valor) for sem, valor in crg_por_semestre.items()}


def interpretar_historico(texto: str) -> dict:
    emissao = _EMISSAO.search(texto)
    matricula = _MATRICULA.search(texto)
    if emissao is None or matricula is None:
        raise ValueError("Histórico sem data de emissão ou matrícula")

    inicio = texto.find(_TITULO_BLOCO)
    if inicio < 0:
        raise ValueError("Histórico sem bloco 'Coeficiente de Rendimento por Semestre Letivo'")
    fim = texto.find(_FIM_BLOCO, inicio)
    bloco = texto[inicio: fim if fim > 0 else None]
    semestres = {f"{ano}.{sem}": float(valor) for ano, sem, valor in _SEMESTRE.findall(bloco)}
    if not semestres:
        raise ValueError("Bloco de semestres vazio")

    dia, mes, ano = (int(x) for x in emissao.groups())
    emitido_em = date(ano, mes, dia)
    nome = _NOME.search(texto)
    nascimento = _NASCIMENTO.search(texto)
    return {
        "matricula": int(matricula.group(1)),
        "nome": nome.group(1).strip() if nome else None,
        "data_de_nascimento": nascimento.group(1) if nascimento else None,
        "emitido_em": emitido_em,
        "crg_por_semestre": aplicar_regra_do_zero(semestres, emitido_em),
    }


def ultimo_crg_apurado(crg_por_semestre: dict[str, float | None]) -> float | None:
    apurados = [(sem, v) for sem, v in crg_por_semestre.items() if v is not None]
    return max(apurados)[1] if apurados else None


def carregar_historico(caminho_pdf: Path) -> dict:
    return interpretar_historico(extrair_texto(caminho_pdf))
```

- [ ] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_crg_historico.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Validar nos PDFs reais (não entra no repo)**

Run, da raiz:

```bash
.venv/bin/python -c "
import glob
from pathlib import Path
from app.services.crg_historico import carregar_historico
ok=0
for f in sorted(glob.glob('backend/app/data/historicos/*.pdf')):
    h=carregar_historico(Path(f)); assert h['nome'] and h['data_de_nascimento']; ok+=1
print(ok, 'PDFs ok')
"
```

(com `PYTHONPATH=backend`). Expected: `56 PDFs ok`. Se algum falhar, ajuste a regex — não o teste.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/crg_historico.py tests/test_crg_historico.py
git commit -m "feat: extração do CRG por semestre do histórico SIGAA com regra do zero

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: FasiTech — envelope congelável

**Files:**
- Modify: `backend/app/services/fasitech_client.py`
- Create: `tests/test_fasitech_client.py`

**Interfaces:**
- Produces:
  - `buscar_paginas() -> dict` — envelope `{"url", "params", "coletado_em" (ISO UTC), "paginas": [corpo de cada página como veio]}`; mesmas exceções de hoje (`RuntimeError` sem URL, `httpx.HTTPError`)
  - `registros_do_envelope(envelope: dict) -> list[dict]` — concatena `paginas[*]["dados"]`; levanta `ValueError` se alguma página não tem lista em `dados`
  - `congelar_envelope(envelope: dict, destino: Path) -> Path` — grava JSON (`ensure_ascii=False`, `indent=2`)
- A função `buscar_dados_socioeconomicos` é **removida**; a rota passa a usar `buscar_paginas` (Task 7).

- [ ] **Step 1: Testes**

Crie `tests/test_fasitech_client.py`:

```python
import json

import pytest

from app.services.fasitech_client import congelar_envelope, registros_do_envelope


def test_registros_do_envelope_concatena_paginas():
    envelope = {"paginas": [{"dados": [{"matricula": 1}], "pagina": 1}, {"dados": [{"matricula": 2}], "pagina": 2}]}
    assert registros_do_envelope(envelope) == [{"matricula": 1}, {"matricula": 2}]


def test_registros_do_envelope_formato_inesperado_da_erro():
    with pytest.raises(ValueError):
        registros_do_envelope({"paginas": [{"total": 165, "pagina": 1}]})


def test_congelar_envelope_grava_json_legivel(tmp_path):
    envelope = {"url": "http://x", "params": {"pagina": 1}, "coletado_em": "2026-09-12T00:00:00+00:00", "paginas": [{"dados": [{"nome": "José"}]}]}
    destino = congelar_envelope(envelope, tmp_path / "lote" / "fasitech.json")
    assert destino.exists()
    assert json.loads(destino.read_text(encoding="utf-8")) == envelope
    assert "José" in destino.read_text(encoding="utf-8")  # ensure_ascii=False
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_fasitech_client.py -q`
Expected: FAIL com `ImportError`.

- [ ] **Step 3: Implementação**

Substitua `backend/app/services/fasitech_client.py` por:

```python
"""Coleta do FasiTech em dois tempos (docs/governanca_dados.md, 3.2):
buscar_paginas devolve a resposta como veio, num envelope com metadados;
congelar_envelope grava isso em raw/lotes/<id>/fasitech.json ANTES de
qualquer escrita no banco; registros_do_envelope é o que a rota importa."""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.core.config import FASITECH_TOKEN, FASITECH_URL

POR_PAGINA = 100


def buscar_paginas() -> dict:
    """Busca TODAS as páginas da API e devolve um envelope:
    {"url", "params", "coletado_em", "paginas": [corpo de cada página]}."""
    if not FASITECH_URL:
        raise RuntimeError(
            "FASITECH_URL não configurada em backend/.env "
            "(ainda não temos a rota correta do FasiTech para dados por aluno)"
        )

    headers = {"Authorization": f"Bearer {FASITECH_TOKEN}"}
    parametros_base = {"por_pagina": POR_PAGINA, "anonymize_matricula": "false"}
    paginas = []
    pagina = 1
    while True:
        resposta = httpx.get(FASITECH_URL, headers=headers, params={**parametros_base, "pagina": pagina}, timeout=10)
        resposta.raise_for_status()
        corpo = resposta.json()
        paginas.append(corpo)
        if not isinstance(corpo, dict) or pagina >= int(corpo.get("total_paginas", 1)):
            break
        pagina += 1

    return {
        "url": FASITECH_URL,
        "params": parametros_base,
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "paginas": paginas,
    }


def registros_do_envelope(envelope: dict) -> list[dict]:
    registros: list[dict] = []
    for corpo in envelope["paginas"]:
        dados = corpo.get("dados") if isinstance(corpo, dict) else None
        if not isinstance(dados, list):
            raise ValueError("Resposta do FasiTech não é uma lista de alunos (formato inesperado)")
        registros.extend(dados)
    return registros


def congelar_envelope(envelope: dict, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino
```

- [ ] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_fasitech_client.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fasitech_client.py tests/test_fasitech_client.py
git commit -m "feat: FasiTech devolve envelope congelável em fasitech.json

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: `/alunos` — leitura pela view, cadastro manual e `/sincronizar` por lote

**Files:**
- Modify: `backend/app/schemas/alunos.py`
- Rewrite: `backend/app/api/alunos.py` (GETs, `POST /alunos`, `POST /alunos/sincronizar`; as outras duas rotas ficam como estão até as Tasks 8–9, só com `Depends(get_session)`)
- Modify: `tests/test_alunos.py` (seções GET, POST /alunos e sincronizar)

**Interfaces:**
- Consumes: `get_session`, `aluno_vigente`, `servico.exigir_lote/abrir_ingestao/fechar_ingestao/registrar_excecao/registrar_arquivo/caminho_do_lote`, `buscar_paginas/registros_do_envelope/congelar_envelope`.
- Produces:
  - `GET /alunos`, `GET /alunos/{matricula}` leem `aluno_vigente`; `AlunoOut` tem `ingestao_id`.
  - `POST /alunos?lote=<id>` → 201, sempre insere (ingestão passo 0). Sem `lote` → 422; lote inexistente → 400.
  - `POST /alunos/sincronizar?lote=<id>` → `{"lote", "ingestao_id", "importados", "rejeitados"}`; 503/502 como hoje; 409 se o passo 1 já rodou no lote.
- Helper interno `_inserir_snapshot(session, dados: dict, ingestao_id: int) -> Usuarios`.

- [ ] **Step 1: Schema**

Em `backend/app/schemas/alunos.py`, na classe `AlunoOut`, acrescente após `id: int`:

```python
    ingestao_id: int
```

- [ ] **Step 2: Reescrever testes das seções GET, POST e sincronizar**

Em `tests/test_alunos.py`, apague tudo de `# GET /alunos e GET /alunos/{matricula}` até o fim da seção sincronizar (o teste `test_sincronizar_nao_duplica_na_segunda_chamada`, inclusive) e coloque:

```python
# ---------------------------------------------------------------------------
# GET /alunos e GET /alunos/{matricula}  (leem aluno_vigente)
# ---------------------------------------------------------------------------

async def test_lista_alunos_comeca_vazia(client):
    resposta = await client.get("/alunos")
    assert resposta.status_code == 200
    assert resposta.json() == []


async def test_lista_alunos_depois_de_criar(client, lote):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 123456, "periodo": "2026.1", "CRG": 8.5})
    resposta = await client.get("/alunos")
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["matricula"] == 123456
    assert corpo[0]["ingestao_id"] > 0


async def test_buscar_aluno_existente(client, lote):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 111, "periodo": "2026.1"})
    resposta = await client.get("/alunos/111")
    assert resposta.status_code == 200
    assert resposta.json()["matricula"] == 111


async def test_buscar_aluno_inexistente_da_404(client):
    assert (await client.get("/alunos/999")).status_code == 404


async def test_get_mostra_so_o_vigente_por_matricula_e_periodo(client, lote):
    """Append-only: duas inserções do mesmo (matricula, periodo) geram duas
    linhas em usuarios, mas a leitura devolve só a mais recente."""
    await client.post(f"/alunos?lote={lote}", json={"matricula": 5, "periodo": "2026.1", "renda": "A"})
    await client.post(f"/alunos?lote={lote}", json={"matricula": 5, "periodo": "2026.1", "renda": "B"})
    lista = (await client.get("/alunos")).json()
    assert [(a["matricula"], a["renda"]) for a in lista] == [(5, "B")]


# ---------------------------------------------------------------------------
# POST /alunos
# ---------------------------------------------------------------------------

async def test_criar_aluno_com_sucesso(client, lote):
    resposta = await client.post(f"/alunos?lote={lote}", json={"matricula": 42, "periodo": "2026.1", "CRG": 7.0, "nome": "Fulano"})
    assert resposta.status_code == 201, resposta.json()
    assert resposta.json()["nome"] == "Fulano"


async def test_criar_aluno_sem_lote_da_422(client):
    assert (await client.post("/alunos", json={"matricula": 42, "periodo": "2026.1"})).status_code == 422


async def test_criar_aluno_em_lote_inexistente_da_400(client):
    assert (await client.post("/alunos?lote=L99", json={"matricula": 42, "periodo": "2026.1"})).status_code == 400


async def test_criar_aluno_sem_matricula_da_422(client, lote):
    assert (await client.post(f"/alunos?lote={lote}", json={"periodo": "2026.1"})).status_code == 422


async def test_criar_aluno_sem_crg_funciona(client, lote):
    resposta = await client.post(f"/alunos?lote={lote}", json={"matricula": 7, "periodo": "2026.1"})
    assert resposta.status_code == 201
    assert resposta.json()["CRG"] is None


# ---------------------------------------------------------------------------
# POST /alunos/sincronizar
# ---------------------------------------------------------------------------

def _envelope(*registros):
    return {"url": "http://fasitech", "params": {}, "coletado_em": "2026-09-12T00:00:00+00:00",
            "paginas": [{"dados": list(registros), "pagina": 1, "total_paginas": 1}]}


async def test_sincronizar_sem_lote_da_422(client):
    assert (await client.post("/alunos/sincronizar")).status_code == 422


async def test_sincronizar_sem_url_configurada_da_503(client, lote, monkeypatch):
    def fasitech_nao_configurado():
        raise RuntimeError("FASITECH_URL não configurada")
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", fasitech_nao_configurado)
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 503


async def test_sincronizar_erro_de_rede_da_502(client, lote, monkeypatch):
    def fasitech_com_erro():
        raise httpx.HTTPError("timeout")
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", fasitech_com_erro)
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 502


async def test_sincronizar_formato_inesperado_da_502(client, lote, monkeypatch):
    """Regressão de um bug real: a rota /dashboard do FasiTech devolve um
    objeto sem 'dados'; sem checagem a API quebrava com 500."""
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: {"paginas": [{"total": 165, "pagina": 1}]})
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 502


async def test_sincronizar_congela_json_antes_de_gravar(client, lote, monkeypatch):
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 900001, "periodo": "2026.1"}))
    resposta = await client.post(f"/alunos/sincronizar?lote={lote}")
    assert resposta.status_code == 200, resposta.json()
    congelado = config.RAIZ_LOTES / lote / "fasitech.json"
    assert congelado.exists()
    assert "900001" in congelado.read_text(encoding="utf-8")
    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert detalhe["ingestoes"][0]["passo"] == 1
    assert detalhe["ingestoes"][0]["arquivo_sha256"] is not None


async def test_sincronizar_importa_validos_e_registra_rejeitados(client, lote, monkeypatch):
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope(
        {"matricula": 900001, "periodo": "2026.1", "genero": "Feminino"},
        {"matricula": 900002, "periodo": "2026.1", "genero": "Masculino"},
        {"periodo": "2026.1"},  # sem matricula -> exceção
    ))
    resposta = await client.post(f"/alunos/sincronizar?lote={lote}")
    corpo = resposta.json()
    assert (corpo["importados"], corpo["rejeitados"]) == (2, 1)
    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert detalhe["excecoes_por_motivo"] == {"matricula_invalida": 1}
    assert detalhe["ingestoes"][0]["registros_lidos"] == 3


async def test_sincronizar_duas_vezes_no_mesmo_lote_da_409(client, lote, monkeypatch):
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 1, "periodo": "2026.1"}))
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 200
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 409


async def test_sincronizar_em_lote_novo_insere_snapshot_e_vigente_muda(client, lote, monkeypatch):
    """Correção na fonte chega no lote seguinte como linha nova; a leitura
    passa a mostrar o valor novo e o antigo continua no banco."""
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 3, "periodo": "2026.1", "renda": "A"}))
    await client.post(f"/alunos/sincronizar?lote={lote}")
    await client.post("/lotes", json={"id": "2027-03-L02", "periodos_cobertos": ["2026.1"]})
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 3, "periodo": "2026.1", "renda": "B"}))
    await client.post("/alunos/sincronizar?lote=2027-03-L02")
    assert (await client.get("/alunos/3")).json()["renda"] == "B"
```

Acrescente no topo do arquivo, junto dos imports: `from app.core import config`.

- [ ] **Step 3: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_alunos.py -q -k "not crg and not legado"`
Expected: maioria FAIL (422 por falta de `lote`, `buscar_paginas` inexistente na rota).

- [ ] **Step 4: Reescrever as rotas**

Substitua o topo e as rotas GET/POST/sincronizar de `backend/app/api/alunos.py` (mantenha `atualizar_crg_do_historico` e `preencher_dados_legado` como estão por enquanto, apenas com `Depends(get_session)` da Task 1):

```python
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.db.engine import Ingestao, Usuarios, get_session
from app.db.vigente import aluno_vigente
from app.schemas.alunos import AlunoCreate, AlunoOut
from app.services import lotes as servico
from app.services.crg_historico import carregar_dados_do_historico  # removido na Task 8
from app.services.dados_legado import carregar_dados_legado
from app.services.fasitech_client import buscar_paginas, congelar_envelope, registros_do_envelope

router = APIRouter(prefix="/alunos", tags=["alunos"])

LoteParam = Query(..., description="Id do lote aberto com POST /lotes", examples=["2026-09-L01"])


def _inserir_snapshot(session: Session, dados: dict, ingestao_id: int) -> Usuarios:
    """usuarios é append-only: toda escrita é uma linha nova ligada à ingestão."""
    aluno = Usuarios(**dados, ingestao_id=ingestao_id)
    session.add(aluno)
    return aluno


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
    return aluno


@router.post("/sincronizar")
def sincronizar_com_fasitech(lote: str = LoteParam, session: Session = Depends(get_session)):
    """POST /alunos/sincronizar?lote=<id> -> passo 1 do lote. Busca o FasiTech,
    congela a resposta em <lote>/fasitech.json e só então grava: uma linha
    nova por registro válido; inválido vira exceção."""
    servico.exigir_lote(session, lote)
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
            servico.registrar_excecao(
                session, ingestao, "matricula_invalida",
                matricula=registro.get("matricula") if isinstance(registro.get("matricula"), int) else None,
                periodo=registro.get("periodo"), detalhe=str(erro)[:500],
            )
            continue
        _inserir_snapshot(session, aluno.model_dump(), ingestao.id)
        importados += 1

    servico.fechar_ingestao(session, ingestao, lidos=len(registros), aceitos=importados, rejeitados=rejeitados)
    return {"lote": lote, "ingestao_id": ingestao.id, "importados": importados, "rejeitados": rejeitados}
```

Observação: `abrir_ingestao` levanta 409 se o passo já rodou — por isso a chamada vem **depois** de congelar (o arquivo já registrado impede perder a evidência) e **antes** de qualquer insert.

- [ ] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest tests/test_alunos.py -q -k "not crg and not legado"`
Expected: todos PASS (17). Os testes de crg/legado ainda falham — próximas tasks.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/alunos.py backend/app/api/alunos.py tests/test_alunos.py
git commit -m "feat: /alunos lê aluno_vigente; POST e /sincronizar exigem lote e são append-only

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: `/atualizar-crg` por semestre, a partir dos PDFs do lote

**Files:**
- Modify: `backend/app/api/alunos.py`
- Modify: `tests/test_alunos.py` (seção atualizar-crg)

**Interfaces:**
- Consumes: `carregar_historico(Path) -> dict`, `ultimo_crg_apurado`, `CrgSemestre`, `servico.*`.
- Produces: `POST /alunos/atualizar-crg?lote=<id>` → `{"lote", "ingestao_id", "pdfs_lidos", "semestres_gravados", "alunos_atualizados", "sem_academico", "sem_socioeconomico", "duplicados"}`; 503 se `<lote>/historicos/` está vazio; 409 se o passo 2 já rodou.

- [ ] **Step 1: Testes**

Em `tests/test_alunos.py`, substitua a seção `POST /alunos/atualizar-crg` inteira por:

```python
# ---------------------------------------------------------------------------
# POST /alunos/atualizar-crg
# ---------------------------------------------------------------------------

def _pdf_falso(lote_id: str, matricula: int) -> None:
    """Cria um arquivo .pdf vazio no lote; o conteúdo não importa porque
    carregar_historico é substituído nos testes."""
    (config.RAIZ_LOTES / lote_id / "historicos" / f"historico_{matricula}.pdf").write_bytes(f"pdf {matricula}".encode())


def _historico(matricula: int, crg: dict, nome="ALUNO TESTE", nascimento="01/01/2000"):
    from datetime import date
    return {"matricula": matricula, "nome": nome, "data_de_nascimento": nascimento,
            "emitido_em": date(2025, 12, 10), "crg_por_semestre": crg}


def _falsificar_leitura(monkeypatch, por_matricula: dict):
    def carregar(caminho):
        matricula = int(caminho.stem.split("_")[1])
        return por_matricula[matricula]
    monkeypatch.setattr(rotas_alunos, "carregar_historico", carregar)


async def test_atualizar_crg_sem_pdfs_da_503(client, lote):
    assert (await client.post(f"/alunos/atualizar-crg?lote={lote}")).status_code == 503


async def test_atualizar_crg_grava_semestres_e_atualiza_vigente(client, lote, monkeypatch):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700001, "periodo": "2026.1", "renda": "A"})
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700002, "periodo": "2026.1"})
    _pdf_falso(lote, 700001)
    _falsificar_leitura(monkeypatch, {700001: _historico(700001, {"2024.2": 6.0, "2025.1": 7.5, "2025.2": None})})

    resposta = await client.post(f"/alunos/atualizar-crg?lote={lote}")
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert corpo["pdfs_lidos"] == 1
    assert corpo["semestres_gravados"] == 3
    assert corpo["alunos_atualizados"] == 1
    assert corpo["sem_academico"] == 1       # 700002 não tem PDF
    assert corpo["sem_socioeconomico"] == 0

    aluno = (await client.get("/alunos/700001")).json()
    assert aluno["CRG"] == 7.5               # último semestre apurado
    assert aluno["nome"] == "ALUNO TESTE"
    assert aluno["renda"] == "A"             # linha nova copia o vigente
    assert (await client.get("/alunos/700002")).json()["CRG"] is None

    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert detalhe["excecoes_por_motivo"] == {"sem_academico": 1}


async def test_atualizar_crg_pdf_sem_socioeconomico_vira_excecao(client, lote, monkeypatch):
    _pdf_falso(lote, 700003)
    _falsificar_leitura(monkeypatch, {700003: _historico(700003, {"2025.1": 8.0})})
    corpo = (await client.post(f"/alunos/atualizar-crg?lote={lote}")).json()
    assert corpo["sem_socioeconomico"] == 1
    assert corpo["semestres_gravados"] == 1  # o CRG é guardado mesmo assim
    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert detalhe["excecoes_por_motivo"] == {"sem_socioeconomico": 1}


async def test_atualizar_crg_atualiza_todos_os_periodos_da_matricula(client, lote, monkeypatch):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700004, "periodo": "2025.2"})
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700004, "periodo": "2026.1"})
    _pdf_falso(lote, 700004)
    _falsificar_leitura(monkeypatch, {700004: _historico(700004, {"2025.1": 6.5})})
    corpo = (await client.post(f"/alunos/atualizar-crg?lote={lote}")).json()
    assert corpo["alunos_atualizados"] == 2
    lista = (await client.get("/alunos")).json()
    assert [a["CRG"] for a in lista] == [6.5, 6.5]


async def test_atualizar_crg_mesmo_pdf_em_lote_novo_e_duplicado(client, lote, monkeypatch):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700005, "periodo": "2026.1"})
    _pdf_falso(lote, 700005)
    _falsificar_leitura(monkeypatch, {700005: _historico(700005, {"2025.1": 9.0})})
    await client.post(f"/alunos/atualizar-crg?lote={lote}")
    await client.post("/lotes", json={"id": "2027-03-L02", "periodos_cobertos": ["2026.2"]})
    _pdf_falso("2027-03-L02", 700005)  # mesmo conteúdo -> mesmo hash
    corpo = (await client.post("/alunos/atualizar-crg?lote=2027-03-L02")).json()
    assert corpo["duplicados"] == 1
    assert corpo["semestres_gravados"] == 0
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_alunos.py -q -k crg`
Expected: FAIL.

- [ ] **Step 3: Reescrever a rota**

Em `backend/app/api/alunos.py`, troque o import `from app.services.crg_historico import carregar_dados_do_historico` por `from app.services.crg_historico import carregar_historico, ultimo_crg_apurado`, acrescente `CrgSemestre` ao import de `app.db.engine`, e substitua `atualizar_crg_do_historico` por:

```python
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
    pdfs = sorted((servico.caminho_do_lote(lote) / "historicos").glob("*.pdf"))
    if not pdfs:
        raise HTTPException(status_code=503, detail=f"Nenhum PDF em {servico.caminho_do_lote(lote) / 'historicos'}")

    ingestao = servico.abrir_ingestao(session, lote, Ingestao.PASSO_CRG)
    contadores = {"pdfs_lidos": 0, "semestres_gravados": 0, "alunos_atualizados": 0,
                  "sem_academico": 0, "sem_socioeconomico": 0, "duplicados": 0}
    matriculas_com_pdf: set[int] = set()

    for pdf in pdfs:
        arquivo = servico.registrar_arquivo(session, lote, pdf, "pdf_historico")
        if arquivo is None:
            contadores["duplicados"] += 1
            servico.registrar_excecao(session, ingestao, "duplicado", detalhe=pdf.name)
            continue
        try:
            historico = carregar_historico(pdf)
        except ValueError as erro:
            # PDF ilegível não é 'sem acadêmico': vira exceção própria e segue.
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
        aceitos=contadores["pdfs_lidos"], rejeitados=contadores["duplicados"] + contadores["sem_socioeconomico"],
    )
    return {"lote": lote, "ingestao_id": ingestao.id, **contadores}
```

Atenção: `sem_academico` conta por `(matricula, periodo)` vigente sem PDF — no teste `test_atualizar_crg_grava_semestres_e_atualiza_vigente` é 1 (700002/2026.1).

- [ ] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_alunos.py -q -k crg`
Expected: `5 passed`. Depois `.venv/bin/python -m pytest -q -k "not legado"` → tudo PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/alunos.py tests/test_alunos.py
git commit -m "feat: /atualizar-crg lê PDFs do lote e grava CRG por semestre em crg_semestre

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: `/preencher-legado` por lote, append-only

**Files:**
- Modify: `backend/app/api/alunos.py`
- Modify: `tests/test_alunos.py` (seção preencher-legado)

**Interfaces:**
- Consumes: `carregar_dados_legado(caminho: Path) -> dict[(matricula, periodo), dict]` (já existe), `servico.*`, `_copia_para_snapshot`, `_inserir_snapshot`.
- Produces: `POST /alunos/preencher-legado?lote=<id>` → `{"lote", "ingestao_id", "atualizados", "campos_preenchidos"}`; 503 se `<lote>/DadosAgrupados.csv` não existe; 409 se o passo 3 já rodou.

- [ ] **Step 1: Testes**

Em `tests/test_alunos.py`, substitua a seção `POST /alunos/preencher-legado` por:

```python
# ---------------------------------------------------------------------------
# POST /alunos/preencher-legado  (só no L01 -- governança, 3.1)
# ---------------------------------------------------------------------------

def _csv_legado(lote_id: str, linhas: list[dict]) -> None:
    import csv
    caminho = config.RAIZ_LOTES / lote_id / "DadosAgrupados.csv"
    colunas = ["Matricula", "Periodo", "Genero", "Escolaridade Pai", "Qtd Computador", "CRG"]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)


async def test_preencher_legado_sem_csv_da_503(client, lote):
    assert (await client.post(f"/alunos/preencher-legado?lote={lote}")).status_code == 503


async def test_preencher_legado_preenche_so_campos_vazios(client, lote):
    """Só preenche o que está None -- não sobrescreve o que veio do FasiTech,
    nunca escreve CRG, e faz isso numa linha NOVA (a antiga continua)."""
    await client.post(f"/alunos?lote={lote}", json={"matricula": 800001, "periodo": "2026.1", "genero": "Feminino", "CRG": 9.0})
    _csv_legado(lote, [{"Matricula": "800001", "Periodo": "2026.1", "Genero": "Masculino",
                        "Escolaridade Pai": "Ensino Médio completo", "Qtd Computador": "Acima de 3", "CRG": "1.0"}])

    resposta = await client.post(f"/alunos/preencher-legado?lote={lote}")
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert (corpo["atualizados"], corpo["campos_preenchidos"]) == (1, 2)

    aluno = (await client.get("/alunos/800001")).json()
    assert aluno["genero"] == "Feminino"
    assert aluno["escolaridade_pai"] == "Ensino Médio completo"
    assert aluno["qtd_computador"] == "Acima de 3"
    assert aluno["CRG"] == 9.0

    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert [i["passo"] for i in detalhe["ingestoes"]] == [0, 3]
    assert detalhe["ingestoes"][1]["arquivo_sha256"] is not None


async def test_preencher_legado_ignora_aluno_sem_correspondencia(client, lote):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 800002, "periodo": "2026.1"})
    _csv_legado(lote, [])
    corpo = (await client.post(f"/alunos/preencher-legado?lote={lote}")).json()
    assert (corpo["atualizados"], corpo["campos_preenchidos"]) == (0, 0)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_alunos.py -q -k legado`
Expected: FAIL.

- [ ] **Step 3: Reescrever a rota**

Em `backend/app/api/alunos.py`, substitua `preencher_dados_legado` por:

```python
@router.post("/preencher-legado")
def preencher_dados_legado(lote: str = LoteParam, session: Session = Depends(get_session)):
    """POST /alunos/preencher-legado?lote=<id> -> passo 3, exclusivo do lote
    inicial. Lê <lote>/DadosAgrupados.csv e, para cada vigente com
    correspondência (matricula, periodo), insere linha nova = vigente + campos
    vazios preenchidos. Nunca mexe no CRG (o desse CSV está errado)."""
    servico.exigir_lote(session, lote)
    csv_legado = servico.caminho_do_lote(lote) / "DadosAgrupados.csv"
    if not csv_legado.exists():
        raise HTTPException(status_code=503, detail=f"CSV legado não encontrado: {csv_legado}")
    dados_legado = carregar_dados_legado(csv_legado)

    arquivo = servico.registrar_arquivo(session, lote, csv_legado, "csv_legado")
    ingestao = servico.abrir_ingestao(session, lote, Ingestao.PASSO_LEGADO, arquivo.sha256 if arquivo else None)

    atualizados = campos_preenchidos = 0
    vigentes = session.execute(select(aluno_vigente)).all()
    for linha in vigentes:
        dados = dados_legado.get((linha.matricula, linha.periodo))
        if not dados:
            continue
        snapshot = _copia_para_snapshot(linha)
        preenchidos = 0
        for campo, valor in dados.items():
            if valor is not None and snapshot.get(campo) is None:
                snapshot[campo] = valor
                preenchidos += 1
        if preenchidos:
            _inserir_snapshot(session, snapshot, ingestao.id)
            atualizados += 1
            campos_preenchidos += preenchidos

    servico.fechar_ingestao(session, ingestao, lidos=len(vigentes), aceitos=atualizados, rejeitados=0)
    return {"lote": lote, "ingestao_id": ingestao.id, "atualizados": atualizados, "campos_preenchidos": campos_preenchidos}
```

Em `backend/app/services/dados_legado.py`, remova a constante `CAMINHO_PADRAO` e o default do parâmetro: a assinatura vira `def carregar_dados_legado(caminho: Path) -> dict[tuple[int, str], dict]:`. O caminho `backend/app/data/` deixa de ser referenciado por código.

- [ ] **Step 4: Rodar tudo**

Run: `.venv/bin/python -m pytest -q`
Expected: todos PASS (≈ 44). Se algum teste antigo sobrou referenciando `buscar_dados_socioeconomicos` ou `carregar_dados_do_historico`, apague-o — ambos não existem mais.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/alunos.py backend/app/services/dados_legado.py tests/test_alunos.py
git commit -m "feat: /preencher-legado lê o CSV do lote e grava linha nova

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: Docker (PostgreSQL + backend), README e doc

**Files:**
- Create: `backend/Dockerfile`, `.dockerignore` (raiz do repo), `backend/.env.example`, `docker-compose.yml`
- Modify: `API_README.md`, `docs/governanca_dados.md` (seção 7, linha do passo 6)

**Interfaces:**
- Produces: `docker compose up --build` sobe `db` (PostgreSQL 17, sem porta no host — 5432 já está ocupada nesta máquina) e `backend` em `http://localhost:8000`, com `./data` montado em `/data` e `DADOS_RAW_DIR=/data/raw/lotes`.

- [ ] **Step 1: Dockerfile**

Crie `backend/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN useradd --create-home --uid 1000 app
COPY --from=build /install /usr/local
COPY --chown=app:app backend/app /app/app
USER app
WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

O contexto de build é a **raiz do repo** (por causa do `pyproject.toml`) — ver o compose.

Crie `.dockerignore` na **raiz do repo** (o contexto de build é a raiz):

```
.venv
.git
frontend
legado
data
docs
tests
**/__pycache__
**/*.sqlite
backend/app/data
```

- [ ] **Step 2: .env.example**

Crie `backend/.env.example`:

```dotenv
# Copie para backend/.env e preencha. backend/.env está no .gitignore.
FASITECH_URL=
FASITECH_TOKEN=

# Usado pelo docker compose (serviço db) e pelo backend.
POSTGRES_USER=dashboard
POSTGRES_PASSWORD=troque-esta-senha
POSTGRES_DB=dashboard
DATABASE_URL=postgresql+psycopg://dashboard:troque-esta-senha@db:5432/dashboard

# Onde ficam os lotes dentro do container (volume ./data:/data).
DADOS_RAW_DIR=/data/raw/lotes
```

- [ ] **Step 3: docker-compose.yml**

Crie `docker-compose.yml` na raiz:

```yaml
services:
  db:
    image: postgres:17-alpine
    env_file: backend/.env
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10
    # Sem `ports`: o banco só é alcançável pelo backend, na rede interna.

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    env_file: backend/.env
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data

volumes:
  pgdata:
```

- [ ] **Step 4: Subir e verificar**

```bash
cp -n backend/.env.example backend/.env   # se ainda não existir; preencha FASITECH_*
docker compose up --build -d
docker compose ps
curl -s localhost:8000/
curl -s -X POST localhost:8000/lotes -H 'content-type: application/json' \
  -d '{"id":"2026-09-L01","periodos_cobertos":["2025.2","2026.1"],"executado_por":"edinaldo"}'
ls data/raw/lotes/2026-09-L01/
docker compose exec db psql -U dashboard -d dashboard -c '\dv' -c '\dt'
```

Expected: `{"status":"ok"}`; 201 com o lote; pasta `historicos/` criada em `data/raw/lotes/2026-09-L01/`; `\dv` lista `aluno_vigente`, `\dt` lista as 6 tabelas. Se `backend` reiniciar em loop, `docker compose logs backend` — o erro mais provável é `DATABASE_URL` com host errado (tem que ser `db`).

Teste do passo 2 com os PDFs reais (fora do repo): `cp backend/app/data/historicos/*.pdf data/raw/lotes/2026-09-L01/historicos/` e `curl -s -X POST 'localhost:8000/alunos/atualizar-crg?lote=2026-09-L01'`. Expected: `pdfs_lidos: 56`, `semestres_gravados` > 500, `sem_socioeconomico: 56` (o banco ainda não tem FasiTech). Isso é só para validar o container; depois `docker compose down -v` para zerar.

- [ ] **Step 5: README e doc**

Em `API_README.md`:
- Na tabela "Visão Geral", acrescente a linha `| **Lotes** | Abre a rodada; pré-requisito das outras | POST /lotes |` e a coluna "Como entra" das 3 rotas ganha `?lote=<id>`.
- Substitua a seção "Como Rodar Localmente" por duas: **Com Docker (recomendado)** — `cp backend/.env.example backend/.env`, editar, `docker compose up --build`, Swagger em `http://localhost:8000/docs`; **Sem Docker** — o comando atual, com nota de que sem `DATABASE_URL` usa SQLite local.
- Acrescente uma seção **Fluxo de um lote** com os 6 passos da seção 5 do doc de governança (criar lote → sincronizar → copiar PDFs → atualizar-crg → [L01] preencher-legado → SHA256SUMS + lote.md + commit no repo privado), cada um com o `curl`.
- Título "As 6 Rotas" vira "As Rotas" e inclui `POST /lotes`, `GET /lotes`, `GET /lotes/{id}` com um exemplo de resposta.

Em `docs/governanca_dados.md`, seção 7, a linha do passo 6 vira:

`| 6 | Migrar para PostgreSQL e subir backend + banco com \`docker compose\` (junto dos passos 3–5) | JSONB, acesso | sim |`

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile .dockerignore backend/.env.example docker-compose.yml API_README.md docs/governanca_dados.md
git commit -m "chore: docker compose com PostgreSQL 17 e backend; README com fluxo por lote

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage.** §2.1–2.4 (Postgres, `DATABASE_URL`, testes em SQLite, lifespan) → Task 1 e 10. §2.5–2.6 (`POST /lotes`, `RAIZ_LOTES`) → Task 3–4. §2.7 (pypdf) → Task 5. §2.8 (view) → Task 2 e 7. §2.9 (passo 2 grava `usuarios` novo) → Task 8. §2.10 (congelar antes) → Task 6–7. §2.11 (contadores + `excecao`) → Tasks 7–9. §2.12 (Dockerfile) → Task 10. §3 contratos → Tasks 4, 7, 8, 9. §4 extração → Task 5. §5 Docker → Task 10. §6 testes → cada task. §7 fora do escopo → não há task para `repository.py` (correto). §8 ajuste do doc → Task 10.

**Placeholders.** Nenhum "TBD/TODO".

**Consistência de nomes.** `get_session` (T1) usado em T4/T7–9. `criar_schema` (T1/T2) em conftest e `test_schema`. `aluno_vigente` (T2) em T7–9. `servico.caminho_do_lote / criar_diretorio / registrar_arquivo / exigir_lote / abrir_ingestao / fechar_ingestao / registrar_excecao` (T3) em T4/T7–9. `Ingestao.PASSO_*` (T2) em T3/T7–9. `buscar_paginas / registros_do_envelope / congelar_envelope` (T6) em T7. `carregar_historico / ultimo_crg_apurado` (T5) em T8. `_inserir_snapshot` e `_copia_para_snapshot` definidos em T7/T8 e usados em T9. `LoteParam` em T7–9. Fixture `lote` (T4) em T7–9. `config.RAIZ_LOTES` em conftest (T1), T3, T7–9.
