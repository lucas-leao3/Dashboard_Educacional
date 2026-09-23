"""Turma e polo derivados da matrícula (docs/governanca_dados.md, §4.8).

A derivação acontece no banco, na view `aluno_vigente`. Por isso a maior
parte destes testes vai pela API: é o único jeito de provar que o SQL da view
faz o que a regra em Python promete -- e não só que a função Python funciona.
"""
from sqlalchemy import text

from app.db.matricula import (
    POLOS_POR_CODIGO, codigo_de_polo, digitos_da_matricula,
    polo_da_matricula, turma_da_matricula,
)


# ---------------------------------------------------------------------------
# A regra em Python
# ---------------------------------------------------------------------------

def test_turma_sao_os_quatro_primeiros_digitos():
    assert turma_da_matricula(202016040011) == "2020"
    assert turma_da_matricula(202316040045) == "2023"


def test_polo_sai_dos_digitos_5_a_8():
    assert polo_da_matricula(202016040011) == "Cametá"
    assert polo_da_matricula(202285640003) == "Limoeiro"
    assert polo_da_matricula(202485940009) == "Oeiras"
    assert codigo_de_polo(202016040011) == "1604"


def test_matricula_fora_do_padrao_nao_vira_turma_nem_polo():
    for ruim in [None, "", "   ", 0, 1, 20201604, "2020160400112", "abcdefghijkl", "20201604001x"]:
        assert digitos_da_matricula(ruim) is None
        assert turma_da_matricula(ruim) is None
        assert polo_da_matricula(ruim) is None


def test_codigo_de_polo_desconhecido_nao_inventa_nome():
    assert codigo_de_polo(202099990001) == "9999"
    assert polo_da_matricula(202099990001) is None


# ---------------------------------------------------------------------------
# A derivação no banco
# ---------------------------------------------------------------------------

async def test_tabela_polo_vem_semeada_pela_migracao(db_engine):
    with db_engine.connect() as conexao:
        linhas = dict(conexao.execute(text("SELECT codigo, nome FROM polo")).all())
    assert linhas == POLOS_POR_CODIGO


async def test_get_alunos_traz_turma_e_polo_derivados(client, lote):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 202016040011, "periodo": "2026.1"})
    [aluno] = (await client.get("/alunos")).json()
    assert aluno["turma"] == "2020"
    assert aluno["polo_cod"] == "1604"
    assert aluno["polo_nome"] == "Cametá"


async def test_derivacao_cobre_os_tres_polos_e_varios_anos(client, lote):
    casos = {
        202016040002: ("2020", "Cametá"),
        202285640003: ("2022", "Limoeiro"),
        202485940009: ("2024", "Oeiras"),
        202616040012: ("2026", "Cametá"),
    }
    for matricula in casos:
        await client.post(f"/alunos?lote={lote}", json={"matricula": matricula, "periodo": "2026.1"})
    por_matricula = {a["matricula"]: a for a in (await client.get("/alunos")).json()}
    for matricula, (turma, polo) in casos.items():
        assert (por_matricula[matricula]["turma"], por_matricula[matricula]["polo_nome"]) == (turma, polo)


async def test_matricula_fora_do_padrao_devolve_nulo_no_banco(client, lote):
    """O CASE da view protege o que a §4.8 exige: sem 12 dígitos, NULL --
    nunca uma turma fatiada de lixo."""
    await client.post(f"/alunos?lote={lote}", json={"matricula": 123456, "periodo": "2026.1"})
    [aluno] = (await client.get("/alunos")).json()
    assert aluno["turma"] is None
    assert aluno["polo_cod"] is None
    assert aluno["polo_nome"] is None


async def test_polo_desconhecido_aparece_com_codigo_e_sem_nome(client, lote):
    """LEFT JOIN, não JOIN: matrícula de polo que ainda não está na tabela
    continua na view (com polo_nome nulo) em vez de sumir do dashboard."""
    await client.post(f"/alunos?lote={lote}", json={"matricula": 202099990001, "periodo": "2026.1"})
    [aluno] = (await client.get("/alunos")).json()
    assert aluno["turma"] == "2020"
    assert aluno["polo_cod"] == "9999"
    assert aluno["polo_nome"] is None


async def test_post_alunos_ja_responde_com_os_derivados(client, lote):
    """O 201 descreve a linha gravada, e ela também precisa vir com turma e
    polo -- senão quem cadastra manualmente não vê o que o banco calculou."""
    resposta = await client.post(f"/alunos?lote={lote}", json={"matricula": 202516040040, "periodo": "2026.1"})
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert (corpo["turma"], corpo["polo_cod"], corpo["polo_nome"]) == ("2025", "1604", "Cametá")


async def test_buscar_aluno_por_matricula_traz_os_derivados(client, lote):
    await client.post(f"/alunos?lote={lote}", json={"matricula": 202485940009, "periodo": "2026.1"})
    corpo = (await client.get("/alunos/202485940009")).json()
    assert (corpo["turma"], corpo["polo_nome"]) == ("2024", "Oeiras")
