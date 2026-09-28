"""Catálogo: o que não está nele não existe para o assistente."""
import pytest
from sqlalchemy.orm import Session

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.catalogo import ConsultaInvalida, validar, valores_validos

VALORES = {
    "polo": ["Cametá", "Oeiras", "Sem polo informado"],
    "turma": ["2020", "2021", "Sem turma informada"],
    "periodo": ["2025.(1 e 2)", "2025.(3 e 4)"],
    "semestre": ["2024.1", "2024.2"],
    "renda": ["Até 1 salário mínimo", "De 1 a 2 salários mínimos", "Sem resposta"],
    "motivo": ["sem_academico", "sem_socioeconomico"],
}


def _c(**campos):
    return ConsultaEstruturada(**campos)


def test_aceita_consulta_do_catalogo():
    c = _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"],
           filtros=[{"campo": "turma", "op": "=", "valor": "2020"}])
    assert validar(c, VALORES) == c


def test_troca_valor_pela_grafia_canonica():
    c = _c(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "polo", "valor": "CAMETA"}])
    assert validar(c, VALORES).filtros[0].valor == "Cametá"


def test_aceita_numero_onde_o_catalogo_tem_texto():
    c = _c(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "turma", "valor": 2020}])
    assert validar(c, VALORES).filtros[0].valor == "2020"


def test_rejeita_metrica_inexistente_listando_as_validas():
    with pytest.raises(ConsultaInvalida, match="contagem_alunos"):
        validar(_c(tipo="agregado", metrica="evasao"), VALORES)


def test_rejeita_metrica_de_outro_tipo():
    with pytest.raises(ConsultaInvalida):
        validar(_c(tipo="lista", metrica="contagem_alunos"), VALORES)


def test_rejeita_dimensao_que_a_metrica_nao_aceita():
    with pytest.raises(ConsultaInvalida, match="semestre"):
        validar(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["semestre"]), VALORES)


def test_crg_por_semestre_exige_a_dimensao_semestre():
    with pytest.raises(ConsultaInvalida):
        validar(_c(tipo="agregado", metrica="crg_medio_semestre", dimensoes=["turma"]), VALORES)


def test_rejeita_valor_fora_do_catalogo_mostrando_os_validos():
    c = _c(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "polo", "valor": "Belém"}])
    with pytest.raises(ConsultaInvalida, match="Cametá"):
        validar(c, VALORES)


def test_entre_so_em_campo_ordenavel_e_com_dois_valores():
    ok = _c(tipo="agregado", metrica="contagem_alunos",
            filtros=[{"campo": "turma", "op": "entre", "valor": ["2020", "2021"]}])
    assert validar(ok, VALORES).filtros[0].valor == ["2020", "2021"]
    for filtro in ({"campo": "polo", "op": "entre", "valor": ["Cametá", "Oeiras"]},
                   {"campo": "turma", "op": "entre", "valor": ["2020"]}):
        with pytest.raises(ConsultaInvalida):
            validar(_c(tipo="agregado", metrica="contagem_alunos", filtros=[filtro]), VALORES)


def test_matricula_aceita_marcador_ou_digitos_e_nada_mais():
    for valor in ("⟨A1⟩", "202016040001"):
        c = _c(tipo="lista", metrica="alunos", filtros=[{"campo": "matricula", "valor": valor}])
        assert validar(c, VALORES).filtros[0].valor == valor
    with pytest.raises(ConsultaInvalida):
        validar(_c(tipo="lista", metrica="alunos", filtros=[{"campo": "matricula", "valor": "Maria"}]), VALORES)


def test_fora_do_catalogo_passa_direto():
    c = _c(tipo="fora_do_catalogo", interpretacao="Não há dado de evasão.")
    assert validar(c, VALORES) == c


async def test_valores_validos_vem_do_banco_com_o_rotulo_de_ausencia(db_engine, semear):
    semear(202016040001, renda="Até 1 salário mínimo")
    semear(202185940002)
    with Session(db_engine) as s:
        valores = valores_validos(s)
    assert valores["polo"] == ["Cametá", "Oeiras", "Sem polo informado"]
    assert valores["turma"] == ["2020", "2021", "Sem turma informada"]
    assert valores["renda"] == ["Até 1 salário mínimo", "Sem resposta"]
    assert valores["semestre"] == ["2025.1"]
    assert "sem_socioeconomico" in valores["motivo"]
