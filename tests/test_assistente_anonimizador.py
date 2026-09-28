"""O que identifica aluno não sai da máquina (spec, D2)."""
from sqlalchemy.orm import Session

from app.services.assistente.anonimizador import anonimizar, nomes_da_base, restaurar

NOMES = {"maria da silva": "202016040001"}


def test_matricula_vira_marcador_e_volta():
    a = anonimizar("Perfil da matrícula 202016040001", {})
    assert a.texto == "Perfil da matrícula ⟨A1⟩"
    assert restaurar(a.texto, a.marcadores) == "Perfil da matrícula 202016040001"


def test_qualquer_sequencia_longa_de_digitos_sai_mesmo_fora_da_base():
    assert anonimizar("aluno 999999999", {}).texto == "aluno ⟨A1⟩"


def test_nome_da_base_casa_sem_caixa_e_sem_acento():
    a = anonimizar("Mostre a MARIA DA SÍLVA", NOMES)
    assert a.texto == "Mostre a ⟨A1⟩"
    assert a.marcadores == {"⟨A1⟩": "202016040001"}


def test_nome_e_matricula_do_mesmo_aluno_viram_o_mesmo_marcador():
    a = anonimizar("Maria da Silva, matrícula 202016040001", NOMES)
    assert a.texto == "⟨A1⟩, matrícula ⟨A1⟩"


def test_palavra_solta_e_trecho_de_palavra_nao_casam():
    assert anonimizar("alunos de Maria", NOMES).texto == "alunos de Maria"
    assert anonimizar("rosemaria da silvana", NOMES).texto == "rosemaria da silvana"


async def test_nomes_da_base_ignora_nome_de_uma_palavra(db_engine, semear):
    semear(202016040001, nome="MARIA DA SILVA")
    semear(202016040002, nome="JOSE")
    with Session(db_engine) as s:
        assert nomes_da_base(s) == {"maria da silva": "202016040001"}
