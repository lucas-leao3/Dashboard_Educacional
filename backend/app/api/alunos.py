from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import get_session
from app.db.vigente import aluno_integrado
from app.schemas.alunos import AlunoOut

router = APIRouter(prefix="/alunos", tags=["alunos"])

# Só leitura. Aluno entra na base por POST /lotes/importar, e só aparece aqui
# se passou pelo cruzamento: a view `aluno_integrado` é `aluno_vigente`
# restrita a quem tem socioeconômico E acadêmico. Quem ficou de fora está no
# relatório de não integrados do lote (GET /lotes/{id}/relatorio).


@router.get("", response_model=list[AlunoOut])
def listar_alunos(session: Session = Depends(get_session)):
    """GET /alunos -> o valor vigente de cada (matricula, periodo) integrado."""
    return session.execute(
        select(aluno_integrado).order_by(aluno_integrado.c.matricula, aluno_integrado.c.periodo)
    ).all()


@router.get("/{matricula}", response_model=AlunoOut)
def buscar_aluno(matricula: int, session: Session = Depends(get_session)):
    """GET /alunos/{matricula} -> o vigente do período mais recente. 404 se não
    existir ou não estiver integrado."""
    aluno = session.execute(
        select(aluno_integrado)
        .where(aluno_integrado.c.matricula == matricula)
        .order_by(aluno_integrado.c.periodo.desc())
    ).first()
    if aluno is None:
        raise HTTPException(status_code=404, detail="Aluno não encontrado entre os integrados")
    return aluno
