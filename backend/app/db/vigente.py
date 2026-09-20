"""aluno_vigente: o 'valor de agora' de cada (matricula, periodo) -- a linha
da ingestão mais recente (docs/governanca_dados.md, 4.5).

A view existe no banco (VIEW_SQL, criada por criar_schema) para quem
consulta por SQL, e aqui como Table para o código consultar com select().
Ela fica num MetaData separado de propósito: create_all não deve tentar
criá-la como tabela.
"""
from sqlalchemy import Column, Integer, MetaData, Table

from app.db.engine import Usuarios

VIEW_SQL = """
CREATE VIEW aluno_vigente AS
SELECT * FROM (
    SELECT u.*, ROW_NUMBER() OVER (
        PARTITION BY u.matricula, u.periodo ORDER BY u.ingestao_id DESC, u.id DESC
    ) AS rn
    FROM usuarios u
) ranked WHERE rn = 1
"""
# u.id DESC desempata quando duas linhas nascem na mesma ingestão -- acontece
# no passo manual (0), que é reaproveitado entre chamadas de POST /alunos.

aluno_vigente = Table(
    "aluno_vigente",
    MetaData(),
    *[Column(c.name, c.type) for c in Usuarios.__table__.columns],
    Column("rn", Integer),
)
