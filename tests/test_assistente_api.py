"""POST /assistente/perguntar e /executar, com o LLM falsificado."""
import json

from app.services.assistente import pipeline
from app.services.assistente.execucao import ConsultaDemorada
from app.services.assistente.provedor_llm import LLMIndisponivel

A, B = 202016040001, 202016040002


def _json(**consulta):
    return json.dumps(consulta, ensure_ascii=False)


async def _perguntar(client, pergunta="pergunta"):
    return await client.post("/assistente/perguntar", json={"pergunta": pergunta})


async def test_forma_dashboard_nao_executa_e_explica(client, llm):
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"]))
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "dashboard"
    assert corpo["dashboard"] == {"id": "polos", "params": {}}
    assert corpo["explicacao"] == {"consulta_interpretada": "Contagem de alunos por Polo", "filtros_aplicados": [],
                                   "fontes": ["aluno_integrado"], "forma": "dashboard"}


async def test_forma_texto(client, llm, semear):
    semear(A)
    semear(B)
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "turma", "valor": "2020"}]))
    corpo = (await _perguntar(client, "Quantos alunos ingressaram em 2020?")).json()
    assert corpo["forma"] == "texto"
    assert corpo["texto"]["mensagem"] == "2 aluno(s) integrado(s) com Turma: 2020."


async def test_forma_tabela(client, llm, semear):
    semear(A, renda="Até 1 salário mínimo")
    semear(B)
    llm.respostas.append(_json(tipo="lista", metrica="alunos", filtros=[{"campo": "renda", "valor": "até 1 salário mínimo"}]))
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "tabela"
    assert corpo["tabela"]["total"] == 1
    assert corpo["explicacao"]["filtros_aplicados"] == [{"rotulo": "Renda familiar", "valor": "Até 1 salário mínimo"}]


async def test_forma_dinamica(client, llm, semear):
    semear(A, renda="Até 1 salário mínimo")
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]))
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "dinamico"
    assert corpo["dinamico"]["graficos"][0]["tipo"] == "barras"


async def test_resultado_vazio_vira_texto(client, llm):
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]))
    corpo = (await _perguntar(client)).json()
    assert (corpo["forma"], corpo["texto"]["mensagem"]) == ("texto", "Nenhum aluno com esses filtros.")


async def test_fora_do_catalogo(client, llm):
    llm.respostas.append(_json(tipo="fora_do_catalogo", interpretacao="A base não tem dado de evasão."))
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "nao_entendi"
    assert "evasão" in corpo["nao_entendi"]["motivo"]
    assert corpo["nao_entendi"]["sugestoes"]


async def test_nova_tentativa_manda_o_erro_ao_modelo(client, llm):
    llm.respostas += [_json(tipo="agregado", metrica="inexistente"),
                      _json(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"])]
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "dashboard"
    assert len(llm.chamadas) == 2
    assert "inexistente" in llm.chamadas[1][-1]["content"]


async def test_duas_respostas_invalidas_viram_nao_entendi(client, llm):
    llm.respostas += ["isto não é json", _json(tipo="agregado", metrica="inexistente")]
    assert (await _perguntar(client)).json()["forma"] == "nao_entendi"


async def test_json_embrulhado_em_markdown_e_aproveitado(client, llm):
    llm.respostas.append("```json\n" + _json(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"]) + "\n```")
    assert (await _perguntar(client)).json()["forma"] == "dashboard"


async def test_llm_indisponivel_vira_503(client, llm):
    llm.respostas.append(LLMIndisponivel("Groq respondeu HTTP 429."))
    resposta = await _perguntar(client)
    assert (resposta.status_code, resposta.json()["detail"]) == (503, "Groq respondeu HTTP 429.")


async def test_consulta_demorada_vira_504(client, llm, semear, monkeypatch):
    semear(A)
    def lenta(session, consulta):
        raise ConsultaDemorada()
    monkeypatch.setattr(pipeline, "resolver", lenta)
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]))
    assert (await _perguntar(client)).status_code == 504


async def test_nada_que_identifica_aluno_sai_para_o_llm(client, llm, semear):
    semear(A, nome="MARIA DA SILVA", CRG=6.5)
    llm.respostas.append(_json(tipo="lista", metrica="alunos", filtros=[{"campo": "matricula", "valor": "⟨A1⟩"}],
                               interpretacao="Perfil de ⟨A1⟩"))
    corpo = (await _perguntar(client, f"Mostre a Maria da Silva, matrícula {A}")).json()
    assert corpo["forma"] == "dashboard"
    assert corpo["dashboard"] == {"id": "perfil", "params": {"matricula": str(A)}}
    assert corpo["consulta"]["interpretacao"] == f"Perfil de {A}"
    enviado = json.dumps(llm.chamadas, ensure_ascii=False).lower()
    assert str(A) not in enviado
    assert "maria" not in enviado
    assert len(llm.chamadas) == 1  # resultado nunca volta ao modelo


async def test_executar_nao_chama_o_llm(client, llm, semear):
    semear(A, renda="Até 1 salário mínimo")
    consulta = {"tipo": "agregado", "metrica": "contagem_alunos", "dimensoes": ["renda"]}
    corpo = (await client.post("/assistente/executar", json={"consulta": consulta})).json()
    assert corpo["forma"] == "dinamico"
    assert llm.chamadas == []


async def test_executar_consulta_fora_do_catalogo_e_422(client, llm):
    resposta = await client.post("/assistente/executar", json={"consulta": {"tipo": "agregado", "metrica": "evasao"}})
    assert resposta.status_code == 422
