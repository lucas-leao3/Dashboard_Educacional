"""Pergunta -> resposta: anonimiza, interpreta, planeja, executa, descreve."""
import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.schemas.assistente import BlocoDashboard, ConsultaEstruturada, Explicacao, RespostaAssistente
from app.services.assistente.anonimizador import anonimizar, nomes_da_base, restaurar
from app.services.assistente.catalogo import validar, valores_validos
from app.services.assistente.compilador import Resultado, fontes, resolver_sql
from app.services.assistente.intencao import interpretar
from app.services.assistente.operacionais import resolver_operacional
from app.services.assistente.planejador import params_do_dashboard, planejar
from app.services.assistente.provedor_llm import ProvedorLLM
from app.services.assistente.respostas import (descrever, filtros_aplicados, nao_entendi, tabela_para,
                                               texto_para)
from app.services.assistente.visualizacao import montar_dinamico

log = logging.getLogger("app.assistente")
_NAO_TRADUZIDA = "Não consegui traduzir a pergunta para o que o assistente sabe consultar."


def resolver(session: Session, consulta: ConsultaEstruturada) -> Resultado:
    if consulta.tipo == "operacional" or consulta.metrica in ("alunos_incompletos", "nao_integrados"):
        return resolver_operacional(session, consulta)
    return resolver_sql(session, consulta)


def _restaurar(consulta: ConsultaEstruturada, marcadores: dict[str, str]) -> ConsultaEstruturada | None:
    """Troca ⟨An⟩ pela matrícula. Marcador que a pergunta não tinha (inventado
    pelo modelo) torna a consulta inválida."""
    filtros = []
    for f in consulta.filtros:
        if f.campo == "matricula":
            valores = f.valor if isinstance(f.valor, list) else [f.valor]
            reais = [marcadores.get(v, v) for v in valores]
            if not all(v.isdigit() for v in reais):
                return None
            f = f.model_copy(update={"valor": reais if isinstance(f.valor, list) else reais[0]})
        filtros.append(f)
    return consulta.model_copy(update={"filtros": filtros, "interpretacao": restaurar(consulta.interpretacao, marcadores)})


def _resposta(pergunta, consulta, forma, fontes_usadas, **bloco) -> RespostaAssistente:
    explicacao = Explicacao(
        consulta_interpretada=descrever(consulta) if consulta else _NAO_TRADUZIDA,
        filtros_aplicados=filtros_aplicados(consulta) if consulta else [],
        fontes=fontes_usadas, forma=forma)
    return RespostaAssistente(id=uuid.uuid4().hex, pergunta=pergunta, consulta=consulta, forma=forma,
                              explicacao=explicacao, **bloco)


def responder(session: Session, consulta: ConsultaEstruturada | None, pergunta: str | None) -> RespostaAssistente:
    if consulta is None:
        return _resposta(pergunta, None, "nao_entendi", [], nao_entendi=nao_entendi(_NAO_TRADUZIDA))
    plano = planejar(consulta)
    if plano.forma == "nao_entendi":
        return _resposta(pergunta, consulta, "nao_entendi", [], nao_entendi=nao_entendi(consulta.interpretacao or _NAO_TRADUZIDA))
    if plano.forma == "dashboard":
        bloco = BlocoDashboard(id=plano.dashboard.id, params=params_do_dashboard(plano.dashboard, consulta))
        return _resposta(pergunta, consulta, "dashboard", fontes(consulta), dashboard=bloco)
    resultado = resolver(session, consulta)
    vazio = not resultado.linhas or (consulta.metrica == "contagem_alunos" and not consulta.dimensoes
                                     and not resultado.linhas[0]["valor"])
    if vazio or plano.forma == "texto":
        return _resposta(pergunta, consulta, "texto", resultado.fontes, texto=texto_para(consulta, resultado))
    if plano.forma == "tabela":
        return _resposta(pergunta, consulta, "tabela", resultado.fontes, tabela=tabela_para(resultado))
    return _resposta(pergunta, consulta, "dinamico", resultado.fontes, dinamico=montar_dinamico(consulta, resultado))


def perguntar(session: Session, provedor: ProvedorLLM, pergunta: str) -> RespostaAssistente:
    inicio = time.monotonic()
    anonima = anonimizar(pergunta, nomes_da_base(session))
    interpretada = interpretar(provedor, anonima.texto, valores_validos(session))
    consulta = _restaurar(interpretada, anonima.marcadores) if interpretada else None
    resposta = responder(session, consulta, pergunta)
    # Só o que já saiu para o LLM vai ao log: pergunta e consulta anonimizadas.
    log.info("assistente pergunta=%r consulta=%s forma=%s duracao_ms=%d", anonima.texto,
             interpretada.model_dump_json() if interpretada else None, resposta.forma,
             (time.monotonic() - inicio) * 1000)
    return resposta


def executar(session: Session, consulta: ConsultaEstruturada) -> RespostaAssistente:
    """Reexecuta uma consulta salva (histórico, link compartilhado), sem LLM."""
    return responder(session, validar(consulta, valores_validos(session)), None)
