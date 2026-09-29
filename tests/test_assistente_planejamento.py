"""Regras determinísticas: forma da resposta, gráfico e textos."""
import pytest

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.compilador import Resultado
from app.services.assistente.planejador import params_do_dashboard, planejar
from app.services.assistente.respostas import descrever, filtros_aplicados, tabela_para, texto_para
from app.services.assistente.visualizacao import chave_renda, montar_dinamico


def _c(**campos):
    return ConsultaEstruturada(**campos)


# Os casos de aceitação do spec, já como ConsultaEstruturada.
CASOS = [
    ("Quantos alunos existem por polo?", _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"]), "dashboard", "polos"),
    ("Mostre os alunos do polo de Cametá", _c(tipo="lista", metrica="alunos", filtros=[{"campo": "polo", "valor": "Cametá"}]), "dashboard", "turmas"),
    ("Evolução por semestre", _c(tipo="agregado", metrica="crg_medio_semestre", dimensoes=["semestre"]), "dashboard", "longitudinal"),
    ("Distribuição de renda", _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]), "dinamico", None),
    ("Compare renda por polo", _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo", "renda"]), "dinamico", None),
    ("Campos com mais ausentes", _c(tipo="operacional", metrica="campos_sem_resposta"), "dinamico", None),
    ("Ingressaram em 2020", _c(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "turma", "valor": "2020"}]), "texto", None),
    ("Registros do último lote", _c(tipo="operacional", metrica="resumo_ultimo_lote"), "texto", None),
    ("Alunos com dados incompletos", _c(tipo="lista", metrica="alunos_incompletos"), "tabela", None),
    ("Sem socioeconômico", _c(tipo="lista", metrica="nao_integrados", filtros=[{"campo": "motivo", "valor": "sem_socioeconomico"}]), "tabela", None),
    ("Polos com maior evasão", _c(tipo="fora_do_catalogo", interpretacao="Não há dado de evasão."), "nao_entendi", None),
]


@pytest.mark.parametrize("pergunta,consulta,forma,dashboard", CASOS, ids=[c[0] for c in CASOS])
def test_casos_de_aceitacao(pergunta, consulta, forma, dashboard):
    plano = planejar(consulta)
    assert plano.forma == forma
    assert (plano.dashboard.id if plano.dashboard else None) == dashboard


def test_params_do_dashboard_levam_filtros_e_dimensao():
    c = _c(tipo="agregado", metrica="crg_medio", dimensoes=["renda"], filtros=[{"campo": "polo", "valor": "Cametá"}])
    plano = planejar(c)
    assert plano.dashboard.id == "bidimensional"
    assert params_do_dashboard(plano.dashboard, c) == {"polo": "Cametá", "dimensao": "renda"}


def test_filtro_que_o_dashboard_nao_tem_vira_dinamico():
    c = _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"], filtros=[{"campo": "renda", "valor": "x"}])
    assert planejar(c).forma == "dinamico"


def test_lista_com_filtro_fora_do_dashboard_vira_tabela():
    c = _c(tipo="lista", metrica="alunos", filtros=[{"campo": "polo", "valor": "Cametá"}, {"campo": "renda", "valor": "x"}])
    assert planejar(c).forma == "tabela"


# --- visualização --------------------------------------------------------

def _res(linhas):
    return Resultado(list(linhas[0]) if linhas else [], linhas, ["aluno_integrado"])


def test_ordem_natural_da_renda():
    rendas = ["Sem resposta", "Acima de 3 salários mínimos", "De 1 a 2 salários mínimos", "Até 1 salário mínimo"]
    assert sorted(rendas, key=chave_renda) == [
        "Até 1 salário mínimo", "De 1 a 2 salários mínimos", "Acima de 3 salários mínimos", "Sem resposta"]


def test_sem_dimensao_vira_kpi():
    bloco = montar_dinamico(_c(tipo="agregado", metrica="crg_medio"), _res([{"valor": 7.0, "n": 2}]))
    assert (bloco.kpis[0].valor, bloco.kpis[0].n, bloco.graficos) == (7.0, 2, [])


def test_distribuicao_do_crg_vira_histograma():
    g = montar_dinamico(_c(tipo="agregado", metrica="distribuicao_crg"), _res([{"faixa": 6, "valor": 1, "n": 1}])).graficos[0]
    assert (g.tipo, g.eixo) == ("histograma", "faixa")


def test_semestre_vira_linha_cronologica_com_nulo_preservado():
    linhas = [{"semestre": "2025.1", "valor": 7.0, "n": 2}, {"semestre": "2024.2", "valor": None, "n": 0}]
    g = montar_dinamico(_c(tipo="agregado", metrica="crg_medio_semestre", dimensoes=["semestre"]), _res(linhas)).graficos[0]
    assert g.tipo == "linha"
    assert [(d["semestre"], d["valor"]) for d in g.dados] == [("2024.2", None), ("2025.1", 7.0)]


def test_semestre_e_turma_vira_uma_linha_por_turma():
    linhas = [{"semestre": "2025.1", "turma": "2021", "valor": 7.0, "n": 1},
              {"semestre": "2025.1", "turma": "2020", "valor": 6.0, "n": 1}]
    g = montar_dinamico(_c(tipo="agregado", metrica="crg_medio_semestre", dimensoes=["semestre", "turma"]), _res(linhas)).graficos[0]
    assert (g.tipo, g.eixo, g.serie, g.series, g.serie_ordinal) == ("linha", "semestre", "turma", ["2020", "2021"], True)


def test_duas_dimensoes_de_contagem_viram_barras_empilhadas_100():
    linhas = [{"polo": "Cametá", "renda": "Sem resposta", "valor": 1, "n": 1},
              {"polo": "Cametá", "renda": "Até 1 salário mínimo", "valor": 3, "n": 3},
              {"polo": "Oeiras", "renda": "Até 1 salário mínimo", "valor": 1, "n": 1}]
    g = montar_dinamico(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo", "renda"]), _res(linhas)).graficos[0]
    assert g.tipo == "barras_empilhadas"
    assert g.series == ["Até 1 salário mínimo", "Sem resposta"]
    assert sum(d["percentual"] for d in g.dados if d["polo"] == "Cametá") == 100.0


def test_duas_dimensoes_de_media_viram_barras_agrupadas():
    linhas = [{"polo": "Cametá", "genero": "Feminino", "valor": 7.0, "n": 2}]
    g = montar_dinamico(_c(tipo="agregado", metrica="crg_medio", dimensoes=["polo", "genero"]), _res(linhas)).graficos[0]
    assert g.tipo == "barras_agrupadas"


def test_poucas_categorias_nominais_viram_rosca_com_percentual():
    linhas = [{"genero": "Feminino", "valor": 3, "n": 3}, {"genero": "Masculino", "valor": 1, "n": 1}]
    g = montar_dinamico(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["genero"]), _res(linhas)).graficos[0]
    assert g.tipo == "rosca"
    assert [d["percentual"] for d in g.dados] == [75.0, 25.0]


def test_ordinal_vira_barras_na_ordem_natural_mesmo_com_poucas_categorias():
    linhas = [{"renda": "De 1 a 2 salários mínimos", "valor": 5, "n": 5}, {"renda": "Até 1 salário mínimo", "valor": 1, "n": 1}]
    g = montar_dinamico(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]), _res(linhas)).graficos[0]
    assert g.tipo == "barras"
    assert [d["renda"] for d in g.dados] == ["Até 1 salário mínimo", "De 1 a 2 salários mínimos"]


def test_nominal_com_muitas_categorias_vira_barras_por_valor_com_ausencia_no_fim():
    nomes = ["A", "B", "C", "D", "E"]
    linhas = [{"cor_etnia": n, "valor": i + 1, "n": i + 1} for i, n in enumerate(nomes)] + [
        {"cor_etnia": "Sem resposta", "valor": 99, "n": 99}]
    g = montar_dinamico(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["cor_etnia"]), _res(linhas)).graficos[0]
    assert g.tipo == "barras"
    assert [d["cor_etnia"] for d in g.dados] == ["E", "D", "C", "B", "A", "Sem resposta"]


# --- respostas -----------------------------------------------------------

def test_filtros_aplicados_e_descricao():
    c = _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"],
           filtros=[{"campo": "turma", "op": "entre", "valor": ["2020", "2022"]},
                    {"campo": "renda", "op": "in", "valor": ["A", "B"]}])
    assert [(f.rotulo, f.valor) for f in filtros_aplicados(c)] == [("Turma", "2020 a 2022"), ("Renda familiar", "A, B")]
    assert descrever(c) == "Contagem de alunos por Polo com Turma: 2020 a 2022, Renda familiar: A, B"


def test_textos():
    turma = [{"campo": "turma", "valor": "2020"}]
    assert texto_para(_c(tipo="agregado", metrica="contagem_alunos", filtros=turma),
                      _res([{"valor": 2, "n": 2}])).mensagem == "2 aluno(s) integrado(s) com Turma: 2020."
    assert texto_para(_c(tipo="agregado", metrica="contagem_alunos"),
                      _res([{"valor": 0, "n": 0}])).mensagem == "Nenhum aluno com esses filtros."
    assert texto_para(_c(tipo="agregado", metrica="crg_medio"),
                      _res([{"valor": 7.0, "n": 2}])).mensagem == "CRG médio de 7,00, sobre 2 aluno(s) com CRG apurado."
    sem_lote = Resultado([], [], ["lote"], 0, sem_lote=True)
    assert texto_para(_c(tipo="operacional", metrica="resumo_ultimo_lote"), sem_lote).mensagem == "Nenhum lote importado ainda."
    assert texto_para(_c(tipo="operacional", metrica="campos_sem_resposta"), sem_lote).mensagem == "Nenhum lote importado ainda."
    resumo = {"lote": "2026-09-L02", "fechado_em": None, "registros_lidos": 10, "registros_aceitos": 9,
              "integrados": 7, "nao_integrados": 3}
    assert texto_para(_c(tipo="operacional", metrica="resumo_ultimo_lote"), _res([resumo])).mensagem == (
        "No lote 2026-09-L02 foram lidos 10 registros e aceitos 9. Na base consolidada até ele, "
        "7 aluno(s) estão integrados e 3 não integrados.")


def test_tabela_rotula_as_colunas():
    t = tabela_para(Resultado(["matricula", "renda"], [{"matricula": 1, "renda": "x"}], ["aluno_integrado"], 1))
    assert [(c.id, c.rotulo) for c in t.colunas] == [("matricula", "Matrícula"), ("renda", "Renda familiar")]
    assert t.total == 1
