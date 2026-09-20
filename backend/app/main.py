from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.alunos import router as alunos_router
from app.api.lotes import router as lotes_router
from app.db.engine import criar_schema, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    criar_schema(engine)
    yield


app = FastAPI(title="Dashboard Educacional API", lifespan=lifespan)

app.include_router(alunos_router)
app.include_router(lotes_router)


@app.get("/")
def raiz():
    """Health-check simples, só pra confirmar que a API está de pé."""
    return {"status": "ok"}
