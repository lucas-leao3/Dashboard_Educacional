from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.alunos import router as alunos_router
from app.api.assistente import router as assistente_router
from app.api.crg import router as crg_router
from app.api.lotes import router as lotes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # O schema NÃO é criado aqui. Quem o cria e o evolui é o Alembic,
    # rodado antes do uvicorn pelo command do docker-compose
    # (`alembic upgrade head`). Ver docs/migracoes.md.
    yield


app = FastAPI(title="Dashboard Educacional API", lifespan=lifespan)

app.include_router(alunos_router)
app.include_router(assistente_router)
app.include_router(crg_router)
app.include_router(lotes_router)


@app.get("/")
def raiz():
    """Health-check simples, só pra confirmar que a API está de pé."""
    return {"status": "ok"}
