"""Testes da API de alunos.

Rodar: pytest -v   (da raiz do projeto, com a venvDashboard ativada)

Quando um teste falha, o pytest imprime o traceback inteiro -- qual
asserção quebrou, o valor esperado e o valor recebido. Não precisa de
nada especial pra "ver o erro": rodar com -v já mostra tudo.

Nas rotas que dependem do FasiTech (POST /alunos/sincronizar), a função
`buscar_paginas` é sempre substituída por uma versão de
mentira (monkeypatch) -- os testes não fazem nenhuma chamada de rede de
verdade, nem dependem de token válido.
"""
import httpx

import app.api.alunos as rotas_alunos
from app.core import config


# ---------------------------------------------------------------------------
# GET /alunos e GET /alunos/{matricula}  (leem aluno_vigente)
# ---------------------------------------------------------------------------

async def test_lista_alunos_comeca_vazia(client):
    resposta = await client.get("/alunos")
    assert resposta.status_code == 200
    assert resposta.json() == []


async def test_lista_alunos_depois_de_criar(client, lote):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 123456, "periodo": "2026.1", "CRG": 8.5})
    resposta = await client.get("/alunos")
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["matricula"] == 123456
    assert corpo[0]["ingestao_id"] > 0


async def test_buscar_aluno_existente(client, lote):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 111, "periodo": "2026.1"})
    resposta = await client.get("/alunos/111")
    assert resposta.status_code == 200
    assert resposta.json()["matricula"] == 111


async def test_buscar_aluno_inexistente_da_404(client):
    assert (await client.get("/alunos/999")).status_code == 404


async def test_get_mostra_so_o_vigente_por_matricula_e_periodo(client, lote):
    """Append-only: duas inserções do mesmo (matricula, periodo) geram duas
    linhas em usuarios, mas a leitura devolve só a mais recente."""
    await client.post(f"/alunos?lote={lote}", json={"matricula": 5, "periodo": "2026.1", "renda": "A"})
    await client.post(f"/alunos?lote={lote}", json={"matricula": 5, "periodo": "2026.1", "renda": "B"})
    lista = (await client.get("/alunos")).json()
    assert [(a["matricula"], a["renda"]) for a in lista] == [(5, "B")]


# ---------------------------------------------------------------------------
# POST /alunos
# ---------------------------------------------------------------------------

async def test_criar_aluno_com_sucesso(client, lote):
    resposta = await client.post(f"/alunos?lote={lote}", json={"matricula": 42, "periodo": "2026.1", "CRG": 7.0, "nome": "Fulano"})
    assert resposta.status_code == 201, resposta.json()
    assert resposta.json()["nome"] == "Fulano"


async def test_criar_aluno_sem_lote_da_422(client):
    assert (await client.post("/alunos", json={"matricula": 42, "periodo": "2026.1"})).status_code == 422


async def test_criar_aluno_em_lote_inexistente_da_400(client):
    assert (await client.post("/alunos?lote=L99", json={"matricula": 42, "periodo": "2026.1"})).status_code == 400


async def test_criar_aluno_sem_matricula_da_422(client, lote):
    assert (await client.post(f"/alunos?lote={lote}", json={"periodo": "2026.1"})).status_code == 422


async def test_criar_aluno_sem_crg_funciona(client, lote):
    resposta = await client.post(f"/alunos?lote={lote}", json={"matricula": 7, "periodo": "2026.1"})
    assert resposta.status_code == 201
    assert resposta.json()["CRG"] is None


# ---------------------------------------------------------------------------
# POST /alunos/sincronizar
# ---------------------------------------------------------------------------

def _envelope(*registros):
    return {"url": "http://fasitech", "params": {}, "coletado_em": "2026-09-12T00:00:00+00:00",
            "paginas": [{"dados": list(registros), "pagina": 1, "total_paginas": 1}]}


async def test_sincronizar_sem_lote_da_422(client):
    assert (await client.post("/alunos/sincronizar")).status_code == 422


async def test_sincronizar_sem_url_configurada_da_503(client, lote, monkeypatch):
    def fasitech_nao_configurado():
        raise RuntimeError("FASITECH_URL não configurada")
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", fasitech_nao_configurado)
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 503


async def test_sincronizar_erro_de_rede_da_502(client, lote, monkeypatch):
    def fasitech_com_erro():
        raise httpx.HTTPError("timeout")
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", fasitech_com_erro)
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 502


async def test_sincronizar_formato_inesperado_da_502(client, lote, monkeypatch):
    """Regressão de um bug real: a rota /dashboard do FasiTech devolve um
    objeto sem 'dados'; sem checagem a API quebrava com 500."""
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: {"paginas": [{"total": 165, "pagina": 1}]})
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 502


async def test_sincronizar_congela_json_antes_de_gravar(client, lote, monkeypatch):
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 900001, "periodo": "2026.1"}))
    resposta = await client.post(f"/alunos/sincronizar?lote={lote}")
    assert resposta.status_code == 200, resposta.json()
    congelado = config.RAIZ_LOTES / lote / "fasitech.json"
    assert congelado.exists()
    assert "900001" in congelado.read_text(encoding="utf-8")
    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert detalhe["ingestoes"][0]["passo"] == 1
    assert detalhe["ingestoes"][0]["arquivo_sha256"] is not None


async def test_sincronizar_importa_validos_e_registra_rejeitados(client, lote, monkeypatch):
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope(
        {"matricula": 900001, "periodo": "2026.1", "genero": "Feminino"},
        {"matricula": 900002, "periodo": "2026.1", "genero": "Masculino"},
        {"periodo": "2026.1"},  # sem matricula -> exceção
        {"matricula": 900003},  # sem periodo -> exceção
    ))
    resposta = await client.post(f"/alunos/sincronizar?lote={lote}")
    corpo = resposta.json()
    assert (corpo["importados"], corpo["rejeitados"]) == (2, 2)
    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert detalhe["excecoes_por_motivo"] == {"matricula_invalida": 1, "sem_periodo": 1}
    assert detalhe["ingestoes"][0]["registros_lidos"] == 4


async def test_sincronizar_nao_grava_dado_pessoal_em_excecao(client, lote, db_engine, monkeypatch):
    """LGPD: o detalhe da exceção não pode carregar o valor submetido -- só
    o nome do campo e o tipo do erro (docs/governanca_dados.md)."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db.engine import Excecao

    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope(
        {"matricula": "nao-numero", "periodo": "2026.1", "nome": "MARCADOR_SENSIVEL"},
    ))
    resposta = await client.post(f"/alunos/sincronizar?lote={lote}")
    assert resposta.status_code == 200, resposta.json()

    with Session(db_engine) as session:
        excecoes = session.execute(select(Excecao)).scalars().all()
    assert len(excecoes) == 1
    detalhe = excecoes[0].detalhe or ""
    assert "nao-numero" not in detalhe
    assert "MARCADOR_SENSIVEL" not in detalhe
    assert "input_value" not in detalhe


async def test_sincronizar_duas_vezes_no_mesmo_lote_da_409(client, lote, monkeypatch):
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 1, "periodo": "2026.1"}))
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 200
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 409


async def test_sincronizar_repetido_nao_sobrescreve_fasitech_json(client, lote, monkeypatch):
    """Regressão: a segunda chamada tem que ser recusada ANTES de tocar a
    rede ou o disco -- senão fasitech.json (a evidência congelada) é
    sobrescrito com conteúdo novo enquanto o hash já gravado no banco ainda
    aponta para o conteúdo antigo."""
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 1, "periodo": "2026.1"}))
    assert (await client.post(f"/alunos/sincronizar?lote={lote}")).status_code == 200

    def buscar_paginas_nao_deveria_ser_chamada():
        raise AssertionError("buscar_paginas não deveria ser chamada na segunda tentativa")

    monkeypatch.setattr(rotas_alunos, "buscar_paginas", buscar_paginas_nao_deveria_ser_chamada)
    resposta = await client.post(f"/alunos/sincronizar?lote={lote}")
    assert resposta.status_code == 409, resposta.json()

    congelado = (config.RAIZ_LOTES / lote / "fasitech.json").read_text(encoding="utf-8")
    assert '"matricula": 1' in congelado
    assert '"matricula": 2' not in congelado


async def test_sincronizar_em_lote_novo_insere_snapshot_e_vigente_muda(client, lote, monkeypatch):
    """Correção na fonte chega no lote seguinte como linha nova; a leitura
    passa a mostrar o valor novo e o antigo continua no banco."""
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 3, "periodo": "2026.1", "renda": "A"}))
    await client.post(f"/alunos/sincronizar?lote={lote}")
    await client.post("/lotes", json={"id": "2027-03-L02", "periodos_cobertos": ["2026.1"]})
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": 3, "periodo": "2026.1", "renda": "B"}))
    await client.post("/alunos/sincronizar?lote=2027-03-L02")
    assert (await client.get("/alunos/3")).json()["renda"] == "B"


# ---------------------------------------------------------------------------
# POST /alunos/atualizar-crg
# ---------------------------------------------------------------------------

def _pdf_falso(lote_id: str, matricula: int) -> None:
    """Cria um arquivo .pdf vazio no lote; o conteúdo não importa porque
    carregar_historico é substituído nos testes."""
    (config.RAIZ_LOTES / lote_id / "historicos" / f"historico_{matricula}.pdf").write_bytes(f"pdf {matricula}".encode())


def _historico(matricula: int, crg: dict, nome="ALUNO TESTE", nascimento="01/01/2000"):
    from datetime import date
    return {"matricula": matricula, "nome": nome, "data_de_nascimento": nascimento,
            "emitido_em": date(2025, 12, 10), "crg_por_semestre": crg}


def _falsificar_leitura(monkeypatch, por_matricula: dict):
    def carregar(caminho):
        matricula = int(caminho.stem.split("_")[1])
        return por_matricula[matricula]
    monkeypatch.setattr(rotas_alunos, "carregar_historico", carregar)


async def test_atualizar_crg_sem_pdfs_da_503(client, lote):
    assert (await client.post(f"/alunos/atualizar-crg?lote={lote}")).status_code == 503


async def test_atualizar_crg_grava_semestres_e_atualiza_vigente(client, lote, monkeypatch):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700001, "periodo": "2026.1", "renda": "A"})
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700002, "periodo": "2026.1"})
    _pdf_falso(lote, 700001)
    _falsificar_leitura(monkeypatch, {700001: _historico(700001, {"2024.2": 6.0, "2025.1": 7.5, "2025.2": None})})

    resposta = await client.post(f"/alunos/atualizar-crg?lote={lote}")
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert corpo["pdfs_lidos"] == 1
    assert corpo["semestres_gravados"] == 3
    assert corpo["alunos_atualizados"] == 1
    assert corpo["sem_academico"] == 1       # 700002 não tem PDF
    assert corpo["sem_socioeconomico"] == 0

    aluno = (await client.get("/alunos/700001")).json()
    assert aluno["CRG"] == 7.5               # último semestre apurado
    assert aluno["nome"] == "ALUNO TESTE"
    assert aluno["renda"] == "A"             # linha nova copia o vigente
    assert (await client.get("/alunos/700002")).json()["CRG"] is None

    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert detalhe["excecoes_por_motivo"] == {"sem_academico": 1}


async def test_atualizar_crg_pdf_sem_socioeconomico_vira_excecao(client, lote, monkeypatch):
    _pdf_falso(lote, 700003)
    _falsificar_leitura(monkeypatch, {700003: _historico(700003, {"2025.1": 8.0})})
    corpo = (await client.post(f"/alunos/atualizar-crg?lote={lote}")).json()
    assert corpo["sem_socioeconomico"] == 1
    assert corpo["semestres_gravados"] == 1  # o CRG é guardado mesmo assim
    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert detalhe["excecoes_por_motivo"] == {"sem_socioeconomico": 1}


async def test_atualizar_crg_atualiza_todos_os_periodos_da_matricula(client, lote, monkeypatch):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700004, "periodo": "2025.2"})
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700004, "periodo": "2026.1"})
    _pdf_falso(lote, 700004)
    _falsificar_leitura(monkeypatch, {700004: _historico(700004, {"2025.1": 6.5})})
    corpo = (await client.post(f"/alunos/atualizar-crg?lote={lote}")).json()
    assert corpo["alunos_atualizados"] == 2
    lista = (await client.get("/alunos")).json()
    assert [a["CRG"] for a in lista] == [6.5, 6.5]


async def test_atualizar_crg_mesmo_pdf_em_lote_novo_e_duplicado(client, lote, monkeypatch):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 700005, "periodo": "2026.1"})
    _pdf_falso(lote, 700005)
    _falsificar_leitura(monkeypatch, {700005: _historico(700005, {"2025.1": 9.0})})
    await client.post(f"/alunos/atualizar-crg?lote={lote}")
    await client.post("/lotes", json={"id": "2027-03-L02", "periodos_cobertos": ["2026.2"]})
    _pdf_falso("2027-03-L02", 700005)  # mesmo conteúdo -> mesmo hash
    corpo = (await client.post("/alunos/atualizar-crg?lote=2027-03-L02")).json()
    assert corpo["duplicados"] == 1
    assert corpo["semestres_gravados"] == 0
    assert corpo["sem_academico"] == 0  # PDF duplicado ainda identifica a matrícula
    detalhe = (await client.get("/lotes/2027-03-L02")).json()
    assert detalhe["excecoes_por_motivo"] == {"duplicado": 1}


async def test_atualizar_crg_pdf_ilegivel_conta_como_rejeitado(client, lote, monkeypatch):
    """PDF que quebra em carregar_historico não pode sumir dos contadores:
    registros_lidos tem que bater com aceitos + rejeitados (T8)."""
    _pdf_falso(lote, 700006)

    def carregar_com_erro(caminho):
        raise ValueError("Histórico sem data de emissão ou matrícula")

    monkeypatch.setattr(rotas_alunos, "carregar_historico", carregar_com_erro)

    corpo = (await client.post(f"/alunos/atualizar-crg?lote={lote}")).json()
    assert corpo["ilegiveis"] == 1
    assert corpo["pdfs_lidos"] == 0

    detalhe = (await client.get(f"/lotes/{lote}")).json()
    ingestao = detalhe["ingestoes"][0]
    assert ingestao["registros_lidos"] == 1
    assert ingestao["registros_rejeitados"] == 1
