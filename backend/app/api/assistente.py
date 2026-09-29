from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.engine import get_session
from app.schemas.assistente import ExecutarIn, PerguntaIn, RespostaAssistente
from app.services.assistente import pipeline
from app.services.assistente.catalogo import ConsultaInvalida
from app.services.assistente.execucao import ConsultaDemorada
from app.services.assistente.provedor_llm import LLMIndisponivel, ProvedorLLM, provedor_padrao

router = APIRouter(prefix="/assistente", tags=["assistente"])

# Só leitura. O LLM recebe a pergunta anonimizada e o catálogo, nunca dado de
# aluno (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md).

_DEMORADA = "A consulta passou de 5 s e foi cancelada."


def obter_provedor() -> ProvedorLLM:
    """Dependência: os testes trocam pelo ProvedorFalso."""
    return provedor_padrao()


@router.post("/perguntar", response_model=RespostaAssistente)
def perguntar(corpo: PerguntaIn, session: Session = Depends(get_session),
              provedor: ProvedorLLM = Depends(obter_provedor)):
    """POST /assistente/perguntar -> a resposta na forma escolhida, com explicação.
    503 se o LLM estiver indisponível; /executar continua funcionando."""
    try:
        return pipeline.perguntar(session, provedor, corpo.pergunta)
    except LLMIndisponivel as erro:
        raise HTTPException(503, str(erro)) from erro
    except ConsultaDemorada as erro:
        raise HTTPException(504, _DEMORADA) from erro


@router.post("/executar", response_model=RespostaAssistente)
def executar(corpo: ExecutarIn, session: Session = Depends(get_session)):
    """POST /assistente/executar -> reexecuta uma ConsultaEstruturada sem LLM
    (histórico, link compartilhado). 422 se ela citar algo fora do catálogo."""
    try:
        return pipeline.executar(session, corpo.consulta)
    except ConsultaInvalida as erro:
        raise HTTPException(422, str(erro)) from erro
    except ConsultaDemorada as erro:
        raise HTTPException(504, _DEMORADA) from erro
