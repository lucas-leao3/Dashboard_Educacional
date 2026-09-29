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


def test_primeiro_nome_com_outro_sobrenome_casa():
    """Ninguém digita o nome completo do SIGAA: "Maria Santos" é a Maria da Silva Santos."""
    nomes = {"maria da silva santos": "202016040001"}
    for pergunta in ("CRG da Maria Santos?", "CRG da maria silva?"):
        a = anonimizar(pergunta, nomes)
        assert a.texto.startswith("CRG da ⟨A1⟩")
        assert a.marcadores == {"⟨A1⟩": "202016040001"}


def test_nome_parcial_de_dois_alunos_sai_mas_nao_resolve_para_nenhum():
    a = anonimizar("Mostre a Maria Silva", {"maria da silva": "202016040001", "maria souza silva": "202016040002"})
    assert a.texto == "Mostre a ⟨A1⟩"
    assert a.marcadores == {"⟨A1⟩": "⟨A1⟩"}  # sem matrícula: o pipeline responde "não entendi"


def test_matricula_com_separadores_vira_marcador():
    for escrita in ("2020.1604.0001", "2020-1604-0001"):
        a = anonimizar(f"matrícula {escrita}", {})
        assert (a.texto, a.marcadores) == ("matrícula ⟨A1⟩", {"⟨A1⟩": "202016040001"})


def test_intervalo_de_semestres_nao_vira_matricula():
    assert anonimizar("CRG entre 2024.1-2025.2", {}).texto == "CRG entre 2024.1-2025.2"


async def test_nomes_da_base_ignora_nome_de_uma_palavra(db_engine, semear):
    semear(202016040001, nome="MARIA DA SILVA")
    semear(202016040002, nome="JOSE")
    with Session(db_engine) as s:
        assert nomes_da_base(s) == {"maria da silva": "202016040001"}
