from fastapi import FastAPI

from app.api.alunos import router as alunos_router

app = FastAPI(title="Dashboard Educacional API")

app.include_router(alunos_router)


@app.get("/")
def raiz():
    """Health-check simples, só pra confirmar que a API está de pé."""
    return {"status": "ok"}
