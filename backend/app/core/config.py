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

# Derivados de cada lote (vigente.csv, correspondencia.csv), gerados por
# POST /lotes/{id}/fechar. Regeneráveis a partir do banco -- não vão para o
# repositório de dados. No container é /data/processed.
RAIZ_PROCESSADA = Path(os.getenv("DADOS_PROCESSED_DIR", _RAIZ_REPO / "data" / "processed"))
