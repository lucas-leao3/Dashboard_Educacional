"""Alunos do FasiTech ausentes da base integrada (app/services/ausentes.py).

"Importado" é o mesmo critério da view `aluno_integrado`: linha em usuarios
(socioeconômico) E CRG por semestre em crg_semestre (acadêmico).
"""
import csv
import json

from sqlalchemy.orm import Session

from app.services.ausentes import (
    alunos_ausentes, alunos_do_fasitech, base_importada, escrever_csv, executar,
)

POLOS = {"1604": "Cametá", "8594": "Oeiras"}


# ---------------------------------------------------------------------------
# Leitura do FasiTech
# ---------------------------------------------------------------------------

def test_um_aluno_por_matricula_mesmo_com_varios_periodos():
    alunos, invalidos = alunos_do_fasitech([
        {"matricula": 202016040011, "periodo": "2025.1"},
        {"matricula": 202016040011, "periodo": "2025.2", "polo": "CAMETÁ"},
        {"matricula": "202216040002", "periodo": "2025.2"},
    ])
    assert list(alunos) == ["202016040011", "202216040002"]
    assert alunos["202016040011"]["polo_api"] == "CAMETÁ"   # primeiro valor preenchido
    assert invalidos == 0


def test_matricula_nula_vazia_ou_fora_do_padrao_nao_entra_e_e_contada():
    alunos, invalidos = alunos_do_fasitech([
        {"matricula": None}, {"matricula": ""}, {}, {"matricula": "2020160400"}, {"matricula": "20201604001X"},
        {"matricula": 202016040011},
    ])
    assert list(alunos) == ["202016040011"]
    assert invalidos == 5


# ---------------------------------------------------------------------------
# Comparação
# ---------------------------------------------------------------------------

def test_so_quem_nao_esta_na_base_entra_no_relatorio_ordenado_por_matricula():
    fasitech = {m: {"nome": None, "polo_api": None} for m in ("202416040002", "202016040011", "202285940003")}
    linhas = alunos_ausentes(fasitech, integradas={"202016040011"}, nomes={}, polos=POLOS)
    assert [l["matricula"] for l in linhas] == ["202285940003", "202416040002"]
    assert linhas[0] == {"nome": "", "matricula": "202285940003", "polo": "Oeiras", "turma": "2022"}


def test_polo_da_tabela_vence_o_texto_da_api_e_api_cobre_codigo_desconhecido():
    fasitech = {
        "202016040011": {"nome": None, "polo_api": "CAMETÁ"},
        "202099990001": {"nome": None, "polo_api": "NOVO POLO"},
        "202099990002": {"nome": None, "polo_api": None},
    }
    polos = {l["matricula"]: l["polo"] for l in alunos_ausentes(fasitech, set(), {}, POLOS)}
    assert polos == {"202016040011": "Cametá", "202099990001": "NOVO POLO", "202099990002": ""}


def test_nome_vem_da_api_ou_da_base_e_e_normalizado():
    fasitech = {"202016040011": {"nome": None, "polo_api": None},
                "202116040002": {"nome": "  JOÃO   DA  SILVA ", "polo_api": None}}
    linhas = alunos_ausentes(fasitech, set(), nomes={"202016040011": "Maria Conceição"}, polos=POLOS)
    assert [l["nome"] for l in linhas] == ["Maria Conceição", "JOÃO DA SILVA"]


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def test_csv_em_utf8_com_cabecalho_e_acentos(tmp_path):
    destino = escrever_csv(tmp_path / "sub" / "ausentes.csv",
                           [{"nome": "José Açaí", "matricula": "202016040011", "polo": "Cametá", "turma": "2020"}])
    assert destino.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM: o Excel abre os acentos certos
    with open(destino, encoding="utf-8-sig", newline="") as f:
        assert list(csv.reader(f)) == [["nome", "matricula", "polo", "turma"],
                                       ["José Açaí", "202016040011", "Cametá", "2020"]]


# ---------------------------------------------------------------------------
# Base importada (PostgreSQL) e execução ponta a ponta
# ---------------------------------------------------------------------------

async def test_base_importada_separa_socioeconomico_academico_e_integrados(db_engine, semear):
    semear(202016040011, academico=True)
    semear(202116040002, academico=False)
    with Session(db_engine) as session:
        base = base_importada(session)
    assert base["integradas"] == {"202016040011"}
    assert base["socioeconomico"] == {"202016040011", "202116040002"}
    assert base["academico"] == {"202016040011"}
    assert base["polos"]["1604"] == "Cametá"


async def test_executar_com_snapshot_gera_o_csv_e_o_resumo(db_engine, semear, tmp_path):
    semear(202016040011, academico=True, nome="FULANO INTEGRADO")
    semear(202116040002, academico=False)
    snapshot = tmp_path / "fasitech.json"
    snapshot.write_text(json.dumps({"paginas": [{"dados": [
        {"matricula": 202016040011}, {"matricula": 202116040002}, {"matricula": 202285940003},
        {"matricula": 202285940003}, {"matricula": None},
    ]}]}), encoding="utf-8")

    with Session(db_engine) as session:
        resumo = executar(session, snapshot=snapshot, saida=tmp_path / "ausentes.csv")

    assert resumo["fasitech_registros"] == 5
    assert resumo["fasitech_alunos"] == 3
    assert resumo["fasitech_matricula_invalida"] == 1
    assert resumo["base_integrados"] == 1
    assert resumo["ausentes"] == 2
    assert resumo["ausentes_sem_academico"] == 1       # sincronizado, sem histórico
    assert resumo["ausentes_fora_da_base"] == 1        # respondeu depois do último lote
    with open(resumo["arquivo"], encoding="utf-8-sig", newline="") as f:
        assert [l["matricula"] for l in csv.DictReader(f)] == ["202116040002", "202285940003"]
