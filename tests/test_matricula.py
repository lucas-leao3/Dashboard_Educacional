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


async def test_get_alunos_traz_turma_e_polo_derivados(client, semear):
    semear(202016040011)
    [aluno] = (await client.get("/alunos")).json()
    assert aluno["turma"] == "2020"
    assert aluno["polo_cod"] == "1604"
    assert aluno["polo_nome"] == "Cametá"


async def test_derivacao_cobre_os_tres_polos_e_varios_anos(client, semear):
    casos = {
        202016040002: ("2020", "Cametá"),
        202285640003: ("2022", "Limoeiro"),
        202485940009: ("2024", "Oeiras"),
        202616040012: ("2026", "Cametá"),
    }
    for matricula in casos:
        semear(matricula)
    por_matricula = {a["matricula"]: a for a in (await client.get("/alunos")).json()}
    for matricula, (turma, polo) in casos.items():
        assert (por_matricula[matricula]["turma"], por_matricula[matricula]["polo_nome"]) == (turma, polo)


async def test_matricula_fora_do_padrao_devolve_nulo_no_banco(client, semear):
    """O CASE da view protege o que a §4.8 exige: sem 12 dígitos, NULL --
    nunca uma turma fatiada de lixo."""
    semear(123456)
    [aluno] = (await client.get("/alunos")).json()
    assert aluno["turma"] is None
    assert aluno["polo_cod"] is None
    assert aluno["polo_nome"] is None


async def test_polo_desconhecido_aparece_com_codigo_e_sem_nome(client, semear):
    """LEFT JOIN, não JOIN: matrícula de polo que ainda não está na tabela
    continua na view (com polo_nome nulo) em vez de sumir do dashboard."""
    semear(202099990001)
    [aluno] = (await client.get("/alunos")).json()
    assert aluno["turma"] == "2020"
    assert aluno["polo_cod"] == "9999"
    assert aluno["polo_nome"] is None


async def test_buscar_aluno_por_matricula_traz_os_derivados(client, semear):
    semear(202485940009)
    corpo = (await client.get("/alunos/202485940009")).json()
    assert (corpo["turma"], corpo["polo_nome"]) == ("2024", "Oeiras")
