"""Interpretação do texto do histórico SIGAA. Nenhum PDF real entra aqui
(dado pessoal): o texto abaixo imita o layout que pypdf devolve."""
from datetime import date

import pytest

from app.services.crg_historico import interpretar_historico, semestre_da_data, ultimo_crg_apurado

TEXTO = """
Histórico Acadêmico - Emitido em: 10/12/2025 às 15:43
 Dados Pessoais
Nome: ALUNA DE TESTE SILVA          Matrícula: 202016040099
Data de Nascimento: 05/03/2001      UF de Nascimento:CAMETÁ/PA
 Índices Acadêmicos
Ênfase: - CRG: 7.9662
                Coeficiente de Rendimento por Semestre Letivo
2020/Sem2: 10.0    2021/Sem1: 0.00    2021/Sem2: 7.50    2022/Sem1: 7.75
2025/Sem1: 8.29    2025/Sem2: 0.00    2026/Sem1: 0.00
 Componentes Curriculares Obrigatórios Pendentes:14
"""


def test_semestre_da_data():
    assert semestre_da_data(date(2025, 6, 30)) == "2025.1"
    assert semestre_da_data(date(2025, 7, 1)) == "2025.2"
    assert semestre_da_data(date(2025, 12, 10)) == "2025.2"


def test_interpreta_dados_pessoais_e_emissao():
    h = interpretar_historico(TEXTO)
    assert h["matricula"] == 202016040099
    assert h["nome"] == "ALUNA DE TESTE SILVA"
    assert h["data_de_nascimento"] == "05/03/2001"
    assert h["emitido_em"] == date(2025, 12, 10)


def test_regra_do_zero_anula_semestres_a_partir_da_emissao():
    """Emitido em 2025.2: 2025.2 e 2026.1 viram None; o 0.00 de 2021.1 é
    nota real e fica (governança, 4.6)."""
    crg = interpretar_historico(TEXTO)["crg_por_semestre"]
    assert crg == {
        "2020.2": 10.0, "2021.1": 0.0, "2021.2": 7.5, "2022.1": 7.75,
        "2025.1": 8.29, "2025.2": None, "2026.1": None,
    }


def test_ultimo_crg_apurado_ignora_nulos():
    crg = interpretar_historico(TEXTO)["crg_por_semestre"]
    assert ultimo_crg_apurado(crg) == 8.29
    assert ultimo_crg_apurado({"2026.1": None}) is None


def test_texto_sem_bloco_de_semestres_da_erro():
    with pytest.raises(ValueError):
        interpretar_historico("Emitido em: 10/12/2025\nMatrícula: 202016040099\nnada aqui")


def test_texto_sem_matricula_da_erro():
    with pytest.raises(ValueError):
        interpretar_historico("Emitido em: 10/12/2025\n2020/Sem2: 10.0")
