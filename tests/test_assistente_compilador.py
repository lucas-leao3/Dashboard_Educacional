"""Os números do assistente têm que ser os mesmos das telas."""
from sqlalchemy.orm import Session

from app.db.engine import CrgSemestre
from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.compilador import resolver_sql

A, B, C, D = 202016040001, 202016040002, 202185940003, 202216040004


def _cenario(semear):
    """A: Cametá/2020, dois períodos, mudou de renda. B: Cametá/2020, sem renda.
    C: Oeiras/2021, sem CRG. D: só socioeconômico (não integrado)."""
    semear(A, periodo="2025.(1 e 2)", renda="Até 1 salário mínimo", CRG=6.0)
    semear(A, periodo="2025.(3 e 4)", renda="De 1 a 2 salários mínimos", CRG=6.0)
    semear(B, periodo="2025.(3 e 4)", CRG=8.0)
    semear(C, periodo="2025.(3 e 4)", renda="Até 1 salário mínimo")
    semear(D, periodo="2025.(3 e 4)", academico=False)


def _rodar(db_engine, **consulta):
    with Session(db_engine) as s:
        return resolver_sql(s, ConsultaEstruturada(**consulta))


def _por(resultado, chave):
    return {l[chave]: l["valor"] for l in resultado.linhas}


async def test_contagem_por_polo_bate_com_get_alunos(client, db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"])
    esperado: dict[str, set] = {}
    for a in (await client.get("/alunos")).json():
        esperado.setdefault(a["polo_nome"], set()).add(a["matricula"])
    assert _por(r, "polo") == {p: len(m) for p, m in esperado.items()} == {"Cametá": 2, "Oeiras": 1}
    assert r.fontes == ["aluno_integrado"]


async def test_aluno_conta_uma_vez_pela_resposta_mais_recente(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"])
    assert _por(r, "renda") == {"De 1 a 2 salários mínimos": 1, "Até 1 salário mínimo": 1, "Sem resposta": 1}


async def test_por_periodo_o_aluno_entra_em_cada_periodo(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="contagem_alunos", dimensoes=["periodo"])
    assert _por(r, "periodo") == {"2025.(1 e 2)": 1, "2025.(3 e 4)": 3}


async def test_crg_medio_usa_um_crg_por_aluno_e_ignora_nulo(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="crg_medio")
    assert r.linhas == [{"valor": 7.0, "n": 2}]  # (6 + 8) / 2; por período seria 6,67


async def test_filtro_por_turma_sem_dimensao(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="contagem_alunos",
               filtros=[{"campo": "turma", "valor": "2020"}])
    assert r.linhas == [{"valor": 2, "n": 2}]


async def test_crg_por_semestre_bate_com_get_crg_semestres_e_preserva_nulo(client, db_engine, semear):
    _cenario(semear)
    with Session(db_engine) as s:
        passo2 = semear.ingestoes[2]
        s.add_all([CrgSemestre(matricula=A, semestre="2025.2", crg=5.0, ingestao_id=passo2),
                   CrgSemestre(matricula=B, semestre="2025.2", crg=None, ingestao_id=passo2),
                   CrgSemestre(matricula=A, semestre="2024.2", crg=None, ingestao_id=passo2)])
        s.commit()
    r = _rodar(db_engine, tipo="agregado", metrica="crg_medio_semestre", dimensoes=["semestre"])
    notas: dict[str, list] = {}
    for p in (await client.get("/crg-semestres")).json():
        notas.setdefault(p["semestre"], []).append(p["crg"])
    esperado = {s: (round(sum(v for v in vs if v is not None) / len([v for v in vs if v is not None]), 2)
                    if any(v is not None for v in vs) else None) for s, vs in notas.items()}
    assert _por(r, "semestre") == esperado
    assert _por(r, "semestre")["2024.2"] is None
    assert r.fontes == ["crg_semestre_vigente", "aluno_integrado"]


async def test_distribuicao_do_crg_em_faixas_inteiras(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="distribuicao_crg")
    assert _por(r, "faixa") == {6: 1, 8: 1}


async def test_lista_de_alunos_do_polo_com_total(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="lista", metrica="alunos", filtros=[{"campo": "polo", "valor": "Cametá"}])
    assert [l["matricula"] for l in r.linhas] == [A, B]
    assert r.linhas[0]["periodo"] == "2025.(3 e 4)"
    assert r.total == 2
    assert "total" not in r.colunas


async def test_filtro_pela_categoria_de_ausencia(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="lista", metrica="alunos", filtros=[{"campo": "renda", "valor": "Sem resposta"}])
    assert [l["matricula"] for l in r.linhas] == [B]
    assert "renda" in r.colunas
