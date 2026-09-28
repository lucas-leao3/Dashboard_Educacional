"""GET /lotes/{id}/relatorio: integrados e não integrados, com completude.

Critério do cruzamento (o mesmo da view `aluno_integrado`):
socioeconômico = linha em usuarios; acadêmico = CRG por semestre de um histórico.
"""
from types import SimpleNamespace

from app.services.relatorio import CAMPOS_SOCIOECONOMICOS, completude
from conftest import historico, zip_de

# Um registro com todo o questionário respondido (pcd = Não).
COMPLETO = {campo: "x" for campo in CAMPOS_SOCIOECONOMICOS} | {"pcd": "Não", "tipo_deficiencia": None}


def _socio(**campos):
    return SimpleNamespace(**({c: None for c in CAMPOS_SOCIOECONOMICOS} | campos))


# ---------------------------------------------------------------------------
# Completude
# ---------------------------------------------------------------------------

def test_completude_registro_completo_e_100_por_cento():
    c = completude(_socio(**COMPLETO), tem_academico=True, crg=7.0)
    assert c == {"campos_avaliados": 13, "qtd_campos_sem_resposta": 0,
                 "campos_sem_resposta": [], "percentual_preenchimento": 100.0}


def test_completude_lista_os_campos_vazios_e_trata_texto_em_branco_como_vazio():
    c = completude(_socio(**(COMPLETO | {"renda": None, "deslocamento": "  "})), tem_academico=True, crg=None)
    assert c["campos_sem_resposta"] == ["CRG", "renda", "deslocamento"]
    assert c["qtd_campos_sem_resposta"] == 3
    assert c["percentual_preenchimento"] == round(100 * 10 / 13, 1)


def test_tipo_deficiencia_so_conta_para_quem_declarou_deficiencia():
    sem = completude(_socio(**COMPLETO), tem_academico=False, crg=None)
    com = completude(_socio(**(COMPLETO | {"pcd": "Sim"})), tem_academico=False, crg=None)
    assert "tipo_deficiencia" not in sem["campos_sem_resposta"]
    assert com["campos_sem_resposta"] == ["tipo_deficiencia"]
    assert com["campos_avaliados"] == sem["campos_avaliados"] + 1


def test_prefiro_nao_responder_e_resposta():
    """É uma opção do instrumento, escolhida pelo aluno -- não campo em branco."""
    c = completude(_socio(**(COMPLETO | {"renda": "Prefiro não responder"})), tem_academico=False, crg=None)
    assert "renda" not in c["campos_sem_resposta"]


def test_completude_so_avalia_as_fontes_que_o_registro_tem():
    so_academico = completude(None, tem_academico=True, crg=6.0)
    assert (so_academico["campos_avaliados"], so_academico["percentual_preenchimento"]) == (1, 100.0)
    nada = completude(None, tem_academico=False, crg=None)
    assert (nada["campos_avaliados"], nada["percentual_preenchimento"]) == (0, None)


# ---------------------------------------------------------------------------
# Relatório pela API
# ---------------------------------------------------------------------------

async def _importar_cenario(importar, fontes) -> str:
    """1 integrado completo, 2 integrado incompleto, 3 só socioeconômico,
    4 só histórico, um registro do FasiTech sem matrícula e um PDF ilegível."""
    fontes.fasitech = [
        {"matricula": 1, "periodo": "2026.1", **COMPLETO},
        {"matricula": 2, "periodo": "2026.1", "genero": "Feminino"},
        {"matricula": 3, "periodo": "2026.1", "genero": "Masculino"},
        {"periodo": "2026.1", "genero": "Feminino"},
    ]
    fontes.historicos = {
        "h1": historico(1, {"2025.1": 8.0}, nome="Um"),
        "h2": historico(2, {"2025.1": None}, nome="Dois"),
        "h4": historico(4, {"2025.1": 6.0}, nome="Quatro"),
        "ilegivel": ValueError("Histórico sem data de emissão ou matrícula"),
    }
    resposta = await importar(zip_de(["h1.pdf", "h2.pdf", "h4.pdf", "ilegivel.pdf"]))
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()["id"]


async def test_relatorio_separa_integrados_e_nao_integrados_com_motivo(importar, fontes, client):
    lote_id = await _importar_cenario(importar, fontes)
    corpo = (await client.get(f"/lotes/{lote_id}/relatorio")).json()

    assert [(l["matricula"], l["nome"], l["status"]) for l in corpo["integrados"]] == [
        (1, "Um", "Integrado com sucesso"), (2, "Dois", "Integrado com sucesso"),
    ]
    assert all(l["academico"] and l["socioeconomico"] for l in corpo["integrados"])

    por_motivo = {l["motivo"]: l for l in corpo["nao_integrados"]}
    assert set(por_motivo) == {"sem_academico", "sem_socioeconomico", "falha_identificacao", "matricula_nao_encontrada"}
    assert (por_motivo["sem_academico"]["matricula"], por_motivo["sem_academico"]["academico"],
            por_motivo["sem_academico"]["socioeconomico"]) == (3, False, True)
    assert por_motivo["sem_academico"]["motivo_descricao"] == "Possui socioeconômico e não possui acadêmico"
    assert (por_motivo["sem_socioeconomico"]["matricula"], por_motivo["sem_socioeconomico"]["nome"]) == (4, "Quatro")
    assert por_motivo["sem_socioeconomico"]["motivo_descricao"] == "Possui acadêmico e não possui socioeconômico"
    assert por_motivo["falha_identificacao"]["matricula"] is None
    assert "ilegivel.pdf" in por_motivo["falha_identificacao"]["detalhe"]
    assert por_motivo["matricula_nao_encontrada"]["motivo_descricao"] == "Matrícula não encontrada"

    assert corpo["resumo"] == {
        "total": 6, "integrados": 2, "nao_integrados": 4,
        "por_motivo": {"sem_academico": 1, "sem_socioeconomico": 1, "falha_identificacao": 1, "matricula_nao_encontrada": 1},
        "preenchimento_medio_integrados": round((100.0 + round(100 * 1 / 13, 1)) / 2, 1),
    }


async def test_os_dois_relatorios_trazem_campos_sem_resposta(importar, fontes, client):
    lote_id = await _importar_cenario(importar, fontes)
    corpo = (await client.get(f"/lotes/{lote_id}/relatorio")).json()
    integrados = {l["matricula"]: l for l in corpo["integrados"]}
    assert integrados[1]["campos_sem_resposta"] == []
    assert integrados[2]["campos_sem_resposta"][0] == "CRG"            # nenhum semestre apurado
    assert integrados[2]["qtd_campos_sem_resposta"] == 12
    sem_academico = next(l for l in corpo["nao_integrados"] if l["motivo"] == "sem_academico")
    assert "genero" not in sem_academico["campos_sem_resposta"]
    assert sem_academico["qtd_campos_sem_resposta"] == 11
    for linha in corpo["integrados"] + corpo["nao_integrados"]:
        assert {"campos_sem_resposta", "qtd_campos_sem_resposta", "percentual_preenchimento"} <= linha.keys()
        assert linha["qtd_campos_sem_resposta"] == len(linha["campos_sem_resposta"])


async def test_integrados_do_ultimo_lote_sao_exatamente_os_alunos_do_dashboard(importar, fontes, client):
    """Consistência: o relatório explica o total que o dashboard mostra."""
    lote_id = await _importar_cenario(importar, fontes)
    relatorio = (await client.get(f"/lotes/{lote_id}/relatorio")).json()
    no_dashboard = {a["matricula"] for a in (await client.get("/alunos")).json()}
    assert {l["matricula"] for l in relatorio["integrados"]} == no_dashboard
    no_grafico = {p["matricula"] for p in (await client.get("/crg-semestres")).json()}
    assert no_grafico == no_dashboard


async def test_relatorio_de_lote_antigo_e_o_retrato_do_fechamento(importar, fontes, client):
    """O aluno 3 ganha histórico no lote seguinte: vira integrado no L02 e no
    dashboard, mas o relatório do L01 continua dizendo o que era verdade
    quando ele fechou."""
    primeiro = await _importar_cenario(importar, fontes)
    fontes.historicos["h3"] = historico(3, {"2025.1": 5.5}, nome="Tres")
    segundo = (await importar(zip_de(["h3.pdf"]))).json()["id"]

    antigo = (await client.get(f"/lotes/{primeiro}/relatorio")).json()
    novo = (await client.get(f"/lotes/{segundo}/relatorio")).json()
    assert 3 not in {l["matricula"] for l in antigo["integrados"]}
    assert 3 in {l["matricula"] for l in novo["integrados"]}
    assert 3 in {a["matricula"] for a in (await client.get("/alunos")).json()}
