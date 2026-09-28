"""Operacionais: os mesmos números da tela /dados (relatorio_do_lote)."""
from sqlalchemy.orm import Session

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.operacionais import resolver_operacional
from app.services.relatorio import CAMPOS_SOCIOECONOMICOS
from conftest import historico, zip_de

COMPLETO = {campo: "x" for campo in CAMPOS_SOCIOECONOMICOS} | {"pcd": "Não", "tipo_deficiencia": None}
INTEGRADO, INCOMPLETO, SO_SOCIO, SO_HIST = 202016040001, 202016040002, 202185940003, 202216040004


async def _importar(importar, fontes) -> str:
    fontes.fasitech = [
        {"matricula": INTEGRADO, "periodo": "2026.1", **COMPLETO},
        {"matricula": INCOMPLETO, "periodo": "2026.1", "genero": "Feminino"},
        {"matricula": SO_SOCIO, "periodo": "2026.1", "genero": "Masculino"},
    ]
    fontes.historicos = {"h1": historico(INTEGRADO, {"2025.1": 8.0}, nome="Um"),
                         "h2": historico(INCOMPLETO, {"2025.1": 7.0}, nome="Dois"),
                         "h4": historico(SO_HIST, {"2025.1": 6.0}, nome="Quatro")}
    resposta = await importar(zip_de(["h1.pdf", "h2.pdf", "h4.pdf"]))
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()["id"]


def _rodar(db_engine, **consulta):
    with Session(db_engine) as s:
        return resolver_operacional(s, ConsultaEstruturada(**consulta))


async def test_nao_integrados_por_motivo(db_engine, importar, fontes):
    await _importar(importar, fontes)
    sem_socio = _rodar(db_engine, tipo="lista", metrica="nao_integrados",
                       filtros=[{"campo": "motivo", "valor": "sem_socioeconomico"}])
    assert [l["matricula"] for l in sem_socio.linhas] == [SO_HIST]
    todos = _rodar(db_engine, tipo="lista", metrica="nao_integrados")
    assert {l["matricula"] for l in todos.linhas} == {SO_HIST, SO_SOCIO}


async def test_incompletos_com_polo_e_turma_da_matricula(db_engine, importar, fontes):
    await _importar(importar, fontes)
    r = _rodar(db_engine, tipo="lista", metrica="alunos_incompletos")
    assert [(l["matricula"], l["polo"], l["turma"]) for l in r.linhas] == [(INCOMPLETO, "Cametá", "2020")]
    vazio = _rodar(db_engine, tipo="lista", metrica="alunos_incompletos", filtros=[{"campo": "polo", "valor": "Oeiras"}])
    assert vazio.linhas == []


async def test_campos_sem_resposta_bate_com_o_relatorio(client, db_engine, importar, fontes):
    lote = await _importar(importar, fontes)
    r = _rodar(db_engine, tipo="operacional", metrica="campos_sem_resposta")
    relatorio = (await client.get(f"/lotes/{lote}/relatorio")).json()
    total = sum(l["qtd_campos_sem_resposta"] for l in relatorio["integrados"])
    assert sum(l["valor"] for l in r.linhas) == total
    assert {l["n"] for l in r.linhas} == {len(relatorio["integrados"])}


async def test_resumo_do_ultimo_lote(db_engine, importar, fontes):
    lote = await _importar(importar, fontes)
    [linha] = _rodar(db_engine, tipo="operacional", metrica="resumo_ultimo_lote").linhas
    assert (linha["lote"], linha["integrados"], linha["nao_integrados"]) == (lote, 2, 2)


async def test_sem_lote_nenhum_devolve_vazio(db_engine):
    r = _rodar(db_engine, tipo="operacional", metrica="resumo_ultimo_lote")
    assert (r.linhas, r.total) == ([], 0)
