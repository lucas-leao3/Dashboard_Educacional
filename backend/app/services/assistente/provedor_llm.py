"""Quem interpreta a pergunta: um LLM atrás de uma interface mínima.

O provedor não sabe nada de catálogo nem de prompt (isso é intencao.py): ele
recebe mensagens no formato de chat e devolve o texto da resposta. Trocar o
Groq por outro provedor compatível com OpenAI é mudar GROQ_URL e GROQ_MODELO;
um provedor de outro formato é uma classe nova com `completar`.

O que sai por aqui é só a pergunta anonimizada e o catálogo (spec, D2).
"""
from typing import Protocol

import httpx

from app.core import config

TIMEOUT_S = 20


class LLMIndisponivel(Exception):
    """Sem chave, fora do ar, timeout, 429 ou resposta sem forma: vira 503."""


class ProvedorLLM(Protocol):
    def completar(self, mensagens: list[dict]) -> str: ...


class ProvedorGroq:
    def __init__(self, chave: str, modelo: str, url: str, cliente: httpx.Client | None = None):
        self.chave = chave
        self.modelo = modelo
        self.url = url.rstrip("/")
        self.cliente = cliente or httpx.Client(timeout=TIMEOUT_S)

    def completar(self, mensagens: list[dict]) -> str:
        if not self.chave:
            raise LLMIndisponivel("GROQ_API_KEY não configurada: o assistente está desligado.")
        try:
            resposta = self.cliente.post(
                f"{self.url}/chat/completions",
                headers={"Authorization": f"Bearer {self.chave}"},
                json={
                    "model": self.modelo,
                    "messages": mensagens,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
        except httpx.HTTPError as erro:
            raise LLMIndisponivel(f"Groq inacessível ({erro.__class__.__name__}).") from erro
        if resposta.status_code != 200:
            raise LLMIndisponivel(f"Groq respondeu HTTP {resposta.status_code}.")
        try:
            return resposta.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as erro:
            raise LLMIndisponivel("Groq devolveu uma resposta sem o formato esperado.") from erro


def provedor_padrao() -> ProvedorLLM:
    return ProvedorGroq(config.GROQ_API_KEY, config.GROQ_MODELO, config.GROQ_URL)
