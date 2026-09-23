from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import get_session
from app.db.vigente import crg_semestre_vigente
from app.schemas.crg import CrgSemestreOut

router = APIRouter(prefix="/crg-semestres", tags=["crg"])


@router.get("", response_model=list[CrgSemestreOut])
def listar_crg_por_semestre(session: Session = Depends(get_session)):
    """GET /crg-semestres -> a trajetória acadêmica: um ponto por
    (matricula, semestre), já resolvido pela ingestão mais recente.

    É a única série temporal de desempenho que a base tem. O `CRG` de
    `/alunos` é o do último semestre apurado, repetido em todos os períodos de
    coleta do aluno -- serve para o corte transversal, não para trajetória.

    Semestre sem nota vem com `crg` null e **continua na lista**: é semestre
    não apurado (§4.6), não linha ausente. Quem desenha faz lacuna ali."""
    return session.execute(
        select(crg_semestre_vigente).order_by(
            crg_semestre_vigente.c.matricula, crg_semestre_vigente.c.semestre
        )
    ).all()
