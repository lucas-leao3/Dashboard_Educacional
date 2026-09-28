import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# URL (base) da API do FasiTech que devolve os dados socioeconômicos por aluno,
# paginada -- ver backend/.env pro histórico das URLs testadas até chegar nela.
FASITECH_URL = os.getenv("FASITECH_URL", "")
FASITECH_TOKEN = os.getenv("FASITECH_TOKEN", "")

# Banco: PostgreSQL, e só. Os testes sobem um PostgreSQL descartável em
# contêiner (ver tests/conftest.py); em produção é o serviço `db` do compose.
#
# Não há mais fallback para SQLite. Ele existia "pra desenvolvimento rápido" e
# saiu caro: aceitava calado um schema que o PostgreSQL recusa, e o passo 1 do
# lote 2026-09-L01 quebrou em produção com StringDataRightTruncation enquanto a
# suíte passava (docs/migracoes.md). Um fallback que diverge do banco real não
# é conveniência, é um teste que mente. Sem DATABASE_URL, falhar alto é o
# comportamento correto -- melhor que criar um arquivo .sqlite sem avisar.
_RAIZ_REPO = Path(__file__).resolve().parents[3]
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não configurada. Copie backend/.env.example para "
        "backend/.env e aponte para o PostgreSQL (o serviço `db` do "
        "docker-compose.yml). Não há fallback para SQLite."
    )

if DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        f"DATABASE_URL aponta para SQLite ({DATABASE_URL.split(':')[0]}). "
        "Este projeto roda em PostgreSQL: o schema usa tipos e larguras que o "
        "SQLite ignora, e testar noutro banco esconde defeito (docs/migracoes.md)."
    )

# Onde ficam os lotes de dados brutos (docs/governanca_dados.md, seção 3.2).
# No container é /data/raw/lotes (volume ./data). Os serviços leem este nome
# em tempo de chamada (config.RAIZ_LOTES), então os testes podem trocá-lo.
RAIZ_LOTES = Path(os.getenv("DADOS_RAW_DIR", _RAIZ_REPO / "data" / "raw" / "lotes"))

# Derivados de cada lote (vigente.csv, correspondencia.csv), gerados por
# POST /lotes/{id}/fechar. Regeneráveis a partir do banco -- não vão para o
# repositório de dados. No container é /data/processed.
RAIZ_PROCESSADA = Path(os.getenv("DADOS_PROCESSED_DIR", _RAIZ_REPO / "data" / "processed"))

# Assistente de consultas (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md).
# Sem GROQ_API_KEY o app sobe normalmente: só POST /assistente/perguntar
# responde 503. /assistente/executar não usa o LLM e segue funcionando.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODELO = os.getenv("GROQ_MODELO", "llama-3.3-70b-versatile")
GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1")
