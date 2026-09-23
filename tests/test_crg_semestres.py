"""GET /crg-semestres: a trajetória acadêmica por semestre letivo.

É a única série temporal real de desempenho que a base tem. O CRG gravado em
`usuarios` é o do último semestre apurado, repetido em todos os períodos de
coleta do aluno -- serve para o corte transversal, não para trajetória.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.engine import CrgSemestre, Ingestao


async def _ingestao(db_engine, lote_id: str, passo: int = 2) -> int:
    with Session(db_engine) as s:
        ingestao = Ingestao(lote_id=lote_id, passo=passo, registros_lidos=0,
                            registros_aceitos=0, registros_rejeitados=0)
        s.add(ingestao)
        s.commit()
        return ingestao.id


async def _gravar(db_engine, ingestao_id: int, linhas: list[tuple[int, str, float | None]]) -> None:
    with Session(db_engine) as s:
        for matricula, semestre, crg in linhas:
            s.add(CrgSemestre(matricula=matricula, semestre=semestre, crg=crg, ingestao_id=ingestao_id))
        s.commit()


async def test_lista_vazia_sem_dado(client):
    resposta = await client.get("/crg-semestres")
    assert resposta.status_code == 200
    assert resposta.json() == []


async def test_devolve_um_ponto_por_semestre_ordenado(client, db_engine, lote):
    i = await _ingestao(db_engine, lote)
    await _gravar(db_engine, i, [(202016040011, "2024.2", 8.0), (202016040011, "2023.1", 6.5), (202016040011, "2024.1", 7.0)])
    corpo = (await client.get("/crg-semestres")).json()
    assert [(p["semestre"], p["crg"]) for p in corpo] == [("2023.1", 6.5), ("2024.1", 7.0), ("2024.2", 8.0)]
    assert all(p["matricula"] == 202016040011 for p in corpo)


async def test_semestre_nao_apurado_vem_como_null_e_nao_some(client, db_engine, lote):
    """Regra do zero (§4.6): sem nota o semestre continua na resposta, com
    crg null. Some da lista -> o gráfico cola dois semestres distantes como se
    fossem vizinhos; vira zero -> inventa uma queda."""
    i = await _ingestao(db_engine, lote)
    await _gravar(db_engine, i, [(202016040011, "2025.1", 7.5), (202016040011, "2025.2", None)])
    corpo = (await client.get("/crg-semestres")).json()
    assert [(p["semestre"], p["crg"]) for p in corpo] == [("2025.1", 7.5), ("2025.2", None)]


async def test_segunda_ingestao_substitui_o_semestre_em_vez_de_duplicar(client, db_engine, lote):
    """`crg_semestre` é append-only e sua PK inclui ingestao_id: rodar outro
    lote grava o mesmo semestre de novo. A view resolve pelo mais recente --
    sem isso o gráfico desenharia o mesmo ponto duas vezes."""
    antiga = await _ingestao(db_engine, lote, passo=2)
    await _gravar(db_engine, antiga, [(202016040011, "2024.1", 6.0)])
    nova = await _ingestao(db_engine, lote, passo=3)
    await _gravar(db_engine, nova, [(202016040011, "2024.1", 9.0)])

    corpo = (await client.get("/crg-semestres")).json()
    assert len(corpo) == 1
    assert corpo[0]["crg"] == 9.0


async def test_varios_alunos_saem_agrupados_por_matricula(client, db_engine, lote):
    i = await _ingestao(db_engine, lote)
    await _gravar(db_engine, i, [(202016040011, "2024.1", 7.0), (202285640003, "2024.1", 5.0), (202016040011, "2024.2", 8.0)])
    corpo = (await client.get("/crg-semestres")).json()
    assert [(p["matricula"], p["semestre"]) for p in corpo] == [
        (202016040011, "2024.1"), (202016040011, "2024.2"), (202285640003, "2024.1"),
    ]


async def test_view_existe_no_banco(db_engine):
    with db_engine.connect() as conexao:
        assert conexao.execute(text("SELECT count(*) FROM crg_semestre_vigente")).scalar() == 0
