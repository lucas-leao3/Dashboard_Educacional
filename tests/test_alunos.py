"""Testes da API de alunos.

Rodar: pytest -v   (da raiz do projeto, com a venvDashboard ativada)

Quando um teste falha, o pytest imprime o traceback inteiro -- qual
asserção quebrou, o valor esperado e o valor recebido. Não precisa de
nada especial pra "ver o erro": rodar com -v já mostra tudo.

Nas rotas que dependem do FasiTech (POST /alunos/sincronizar), a função
`buscar_dados_socioeconomicos` é sempre substituída por uma versão de
mentira (monkeypatch) -- os testes não fazem nenhuma chamada de rede de
verdade, nem dependem de token válido.
"""
import httpx

import app.api.alunos as rotas_alunos


# ---------------------------------------------------------------------------
# GET /alunos e GET /alunos/{matricula}
# ---------------------------------------------------------------------------

async def test_lista_alunos_comeca_vazia(client):
    resposta = await client.get("/alunos")

    assert resposta.status_code == 200
    assert resposta.json() == []


async def test_lista_alunos_depois_de_criar(client):
    await client.post("/alunos", json={"matricula": 555, "periodo": "2026.1"})

    resposta = await client.get("/alunos")

    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


async def test_buscar_aluno_existente(client):
    await client.post("/alunos", json={"matricula": 444, "periodo": "2026.1"})

    resposta = await client.get("/alunos/444")

    assert resposta.status_code == 200, resposta.json()
    assert resposta.json()["matricula"] == 444


async def test_buscar_aluno_inexistente_da_404(client):
    resposta = await client.get("/alunos/999999")

    assert resposta.status_code == 404, resposta.json()
    assert resposta.json()["detail"] == "Aluno não encontrado"


# ---------------------------------------------------------------------------
# POST /alunos
# ---------------------------------------------------------------------------

async def test_criar_aluno_com_sucesso(client):
    payload = {"matricula": 111, "periodo": "2026.1", "CRG": 7.5, "nome": "Teste"}

    resposta = await client.post("/alunos", json=payload)

    assert resposta.status_code == 201, resposta.json()
    corpo = resposta.json()
    assert corpo["matricula"] == 111
    assert corpo["CRG"] == 7.5
    assert "id" in corpo


async def test_criar_aluno_sem_matricula_da_422(client):
    payload = {"periodo": "2026.1", "CRG": 7.5}

    resposta = await client.post("/alunos", json=payload)

    assert resposta.status_code == 422, resposta.json()
    campos_com_erro = [erro["loc"][-1] for erro in resposta.json()["detail"]]
    assert "matricula" in campos_com_erro


async def test_criar_aluno_sem_crg_funciona(client):
    """Regressão: CRG virou opcional depois de descobrir que a API do
    FasiTech não devolve nota nenhuma -- a correspondência entre dado
    acadêmico e socioeconômico é feita pela matrícula, não pelo CRG."""
    payload = {"matricula": 222, "periodo": "2026.1"}

    resposta = await client.post("/alunos", json=payload)

    assert resposta.status_code == 201, resposta.json()
    assert resposta.json()["CRG"] is None


async def test_criar_aluno_duplicado_da_409(client):
    payload = {"matricula": 333, "periodo": "2026.1", "CRG": 8.0}

    primeira = await client.post("/alunos", json=payload)
    segunda = await client.post("/alunos", json=payload)

    assert primeira.status_code == 201, primeira.json()
    assert segunda.status_code == 409, segunda.json()


# ---------------------------------------------------------------------------
# POST /alunos/sincronizar
# ---------------------------------------------------------------------------

async def test_sincronizar_sem_url_configurada_da_503(client, monkeypatch):
    def fasitech_nao_configurado():
        raise RuntimeError("FASITECH_URL não configurada")

    monkeypatch.setattr(rotas_alunos, "buscar_dados_socioeconomicos", fasitech_nao_configurado)

    resposta = await client.post("/alunos/sincronizar")

    assert resposta.status_code == 503, resposta.json()


async def test_sincronizar_erro_de_rede_da_502(client, monkeypatch):
    def fasitech_com_erro():
        raise httpx.HTTPError("timeout")

    monkeypatch.setattr(rotas_alunos, "buscar_dados_socioeconomicos", fasitech_com_erro)

    resposta = await client.post("/alunos/sincronizar")

    assert resposta.status_code == 502, resposta.json()


async def test_sincronizar_formato_inesperado_da_502(client, monkeypatch):
    """Regressão de um bug real: a rota /dashboard do FasiTech devolve um
    objeto (dict), não uma lista, e sem essa checagem a API quebrava com
    erro 500 (TypeError) em vez de responder um erro tratado."""

    def fasitech_formato_errado():
        return {"total": 165, "pagina": 1}

    monkeypatch.setattr(rotas_alunos, "buscar_dados_socioeconomicos", fasitech_formato_errado)

    resposta = await client.post("/alunos/sincronizar")

    assert resposta.status_code == 502, resposta.json()


async def test_sincronizar_importa_validos_ignora_invalidos(client, monkeypatch):
    dados_fasitech = [
        {"matricula": 900001, "periodo": "2026.1", "genero": "Feminino"},
        {"matricula": 900002, "periodo": "2026.1", "genero": "Masculino"},
        {"periodo": "2026.1"},  # sem matricula -> inválido, deve ser ignorado
    ]

    monkeypatch.setattr(rotas_alunos, "buscar_dados_socioeconomicos", lambda: dados_fasitech)

    resposta = await client.post("/alunos/sincronizar")

    assert resposta.status_code == 200, resposta.json()
    assert resposta.json() == {"importados": 2, "ignorados": 1}


async def test_sincronizar_nao_duplica_na_segunda_chamada(client, monkeypatch):
    dados_fasitech = [{"matricula": 900003, "periodo": "2026.1"}]

    monkeypatch.setattr(rotas_alunos, "buscar_dados_socioeconomicos", lambda: dados_fasitech)

    primeira = await client.post("/alunos/sincronizar")
    segunda = await client.post("/alunos/sincronizar")

    assert primeira.json() == {"importados": 1, "ignorados": 0}
    assert segunda.json() == {"importados": 0, "ignorados": 1}


# ---------------------------------------------------------------------------
# POST /alunos/atualizar-crg
# ---------------------------------------------------------------------------

async def test_atualizar_crg_sem_csv_da_503(client, monkeypatch):
    def csv_nao_encontrado():
        raise FileNotFoundError("crg_historico.csv")

    monkeypatch.setattr(rotas_alunos, "carregar_dados_do_historico", csv_nao_encontrado)

    resposta = await client.post("/alunos/atualizar-crg")

    assert resposta.status_code == 503, resposta.json()


async def test_atualizar_crg_preenche_alunos_existentes(client, monkeypatch):
    """Regressão: CRG, nome e data de nascimento devem ser atualizados por
    matrícula, ignorando alunos que não aparecem no CSV e sem quebrar
    quando o CSV cita alguém que ainda não está cadastrado."""
    await client.post("/alunos", json={"matricula": 700001, "periodo": "2026.1"})
    await client.post("/alunos", json={"matricula": 700002, "periodo": "2026.1"})

    monkeypatch.setattr(
        rotas_alunos,
        "carregar_dados_do_historico",
        lambda: {
            700001: {"CRG": 7.5, "nome": "ALUNO TESTE", "data_de_nascimento": "01/01/2000"},
            700003: {"CRG": 8.0, "nome": "OUTRO ALUNO", "data_de_nascimento": "02/02/2000"},
        },
    )

    resposta = await client.post("/alunos/atualizar-crg")

    assert resposta.status_code == 200, resposta.json()
    assert resposta.json() == {"atualizados": 1, "nao_encontrados": 1}

    aluno_atualizado = await client.get("/alunos/700001")
    corpo = aluno_atualizado.json()
    assert corpo["CRG"] == 7.5
    assert corpo["nome"] == "ALUNO TESTE"
    assert corpo["data_de_nascimento"] == "01/01/2000"

    aluno_sem_crg = await client.get("/alunos/700002")
    assert aluno_sem_crg.json()["CRG"] is None


async def test_atualizar_crg_atualiza_todos_os_periodos_da_matricula(client, monkeypatch):
    """O CRG é um dado acadêmico do aluno, não do snapshot socioeconômico --
    se a mesma matrícula tiver mais de um período salvo, todos são
    atualizados."""
    await client.post("/alunos", json={"matricula": 700004, "periodo": "2025.2"})
    await client.post("/alunos", json={"matricula": 700004, "periodo": "2026.1"})

    monkeypatch.setattr(
        rotas_alunos,
        "carregar_dados_do_historico",
        lambda: {700004: {"CRG": 6.5, "nome": "FULANO", "data_de_nascimento": "03/03/2000"}},
    )

    resposta = await client.post("/alunos/atualizar-crg")

    assert resposta.json() == {"atualizados": 2, "nao_encontrados": 0}


# ---------------------------------------------------------------------------
# POST /alunos/preencher-legado
# ---------------------------------------------------------------------------

async def test_preencher_legado_sem_csv_da_503(client, monkeypatch):
    def csv_nao_encontrado():
        raise FileNotFoundError("DadosAgrupados.csv")

    monkeypatch.setattr(rotas_alunos, "carregar_dados_legado", csv_nao_encontrado)

    resposta = await client.post("/alunos/preencher-legado")

    assert resposta.status_code == 503, resposta.json()


async def test_preencher_legado_preenche_so_campos_vazios(client, monkeypatch):
    """Regressão: só preenche o que está None -- não sobrescreve o que já
    veio do FasiTech, e nunca escreve CRG (nem que o dicionário mandasse)."""
    await client.post("/alunos", json={
        "matricula": 800001, "periodo": "2026.1", "genero": "Feminino", "CRG": 9.0,
    })

    monkeypatch.setattr(
        rotas_alunos,
        "carregar_dados_legado",
        lambda: {
            (800001, "2026.1"): {
                "genero": "Masculino",  # já preenchido -- não deve mudar
                "escolaridade_pai": "Ensino Médio completo",  # vazio -- deve preencher
                "qtd_computador": "Acima de 3",  # vazio -- deve preencher
            }
        },
    )

    resposta = await client.post("/alunos/preencher-legado")

    assert resposta.status_code == 200, resposta.json()
    assert resposta.json() == {"atualizados": 1, "campos_preenchidos": 2}

    aluno = (await client.get("/alunos/800001")).json()
    assert aluno["genero"] == "Feminino"  # não foi sobrescrito
    assert aluno["escolaridade_pai"] == "Ensino Médio completo"
    assert aluno["qtd_computador"] == "Acima de 3"
    assert aluno["CRG"] == 9.0  # nunca mexido por esse endpoint


async def test_preencher_legado_ignora_aluno_sem_correspondencia(client, monkeypatch):
    await client.post("/alunos", json={"matricula": 800002, "periodo": "2026.1"})

    monkeypatch.setattr(rotas_alunos, "carregar_dados_legado", lambda: {})

    resposta = await client.post("/alunos/preencher-legado")

    assert resposta.json() == {"atualizados": 0, "campos_preenchidos": 0}
