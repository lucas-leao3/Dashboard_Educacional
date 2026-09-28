"""Segunda camada de defesa: mesmo que o compilador erre, o banco recusa."""
import pytest
from sqlalchemy import func, literal_column, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.vigente import aluno_integrado
from app.services.assistente.execucao import ConsultaDemorada, executar_select


@pytest.mark.parametrize("sql", [
    "INSERT INTO polo (codigo, nome) VALUES ('9999', 'X')",
    "UPDATE polo SET nome = 'X'",
    "DELETE FROM usuarios",
    "DROP VIEW aluno_integrado",
    "ALTER TABLE usuarios ADD COLUMN x int",
    "TRUNCATE usuarios",
    "SELECT * FROM usuarios",  # tabela crua: fora da whitelist
])
async def test_role_do_assistente_so_le_as_views_liberadas(db_engine, sql):
    with Session(db_engine) as s:
        s.execute(text("SET LOCAL ROLE leitor_assistente"))
        with pytest.raises(ProgrammingError, match="permission denied|must be owner"):
            s.execute(text(sql))


async def test_executa_como_a_role_e_devolve_dicionarios(db_engine, semear):
    semear(202016040001)
    with Session(db_engine) as s:
        linhas = executar_select(s, select(literal_column("current_user").label("quem"),
                                           select(func.count()).select_from(aluno_integrado).scalar_subquery().label("n")))
        assert linhas == [{"quem": "leitor_assistente", "n": 1}]
        # role e timeout morrem com a transação
        assert s.execute(text("SELECT current_user")).scalar() != "leitor_assistente"


async def test_recusa_o_que_nao_e_select(db_engine):
    with Session(db_engine) as s, pytest.raises(TypeError):
        executar_select(s, text("DELETE FROM usuarios"))


async def test_consulta_lenta_e_cancelada(db_engine):
    with Session(db_engine) as s, pytest.raises(ConsultaDemorada):
        executar_select(s, select(func.pg_sleep(1)), timeout_ms=100)
