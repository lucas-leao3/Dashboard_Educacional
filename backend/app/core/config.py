import os

from dotenv import load_dotenv

load_dotenv()

# URL (base) da API do FasiTech que devolve os dados socioeconômicos por aluno,
# paginada -- ver backend/.env pro histórico das URLs testadas até chegar nela.
FASITECH_URL = os.getenv("FASITECH_URL", "")
FASITECH_TOKEN = os.getenv("FASITECH_TOKEN", "")
