"""ProvedorGroq: o único ponto que fala com o LLM. Nenhum teste chama a rede."""
import json

import httpx
import pytest

from app.services.assistente.provedor_llm import LLMIndisponivel, ProvedorGroq


def _groq(handler, chave="k"):
    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    return ProvedorGroq(chave, "modelo-x", "https://groq.test/v1", cliente=cliente)


def test_envia_pedido_json_deterministico_e_devolve_o_conteudo():
    visto = {}

    def handler(req):
        visto["url"] = str(req.url)
        visto["auth"] = req.headers["authorization"]
        visto["corpo"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"tipo": "agregado"}'}}]})

    assert _groq(handler).completar([{"role": "user", "content": "oi"}]) == '{"tipo": "agregado"}'
    assert visto["url"] == "https://groq.test/v1/chat/completions"
    assert visto["auth"] == "Bearer k"
    assert visto["corpo"]["model"] == "modelo-x"
    assert visto["corpo"]["temperature"] == 0
    assert visto["corpo"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status", [429, 500])
def test_erro_http_vira_indisponivel(status):
    with pytest.raises(LLMIndisponivel, match=str(status)):
        _groq(lambda req: httpx.Response(status)).completar([])


def test_falha_de_rede_vira_indisponivel():
    def handler(req):
        raise httpx.ConnectTimeout("lento")
    with pytest.raises(LLMIndisponivel):
        _groq(handler).completar([])


def test_resposta_sem_choices_vira_indisponivel():
    with pytest.raises(LLMIndisponivel):
        _groq(lambda req: httpx.Response(200, json={"erro": "x"})).completar([])


def test_sem_chave_nao_chama_a_rede():
    def handler(req):
        raise AssertionError("não devia chamar a rede")
    with pytest.raises(LLMIndisponivel, match="GROQ_API_KEY"):
        _groq(handler, chave="").completar([])
