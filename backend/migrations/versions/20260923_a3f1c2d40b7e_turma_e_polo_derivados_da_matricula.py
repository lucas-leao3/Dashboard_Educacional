"""turma e polo derivados da matricula

O dashboard mostrava "Sem polo informado" e "Sem turma informada" para todo
mundo. Não era defeito de mapeamento: consultada em 2026-09-23, a API do
FasiTech devolve `polo` NULO em 187 de 187 registros e não devolve
`primeiro_ano_eletivo` campo algum (a resposta tem 16 chaves, nenhuma é
essa). Os dois valores nunca chegaram. A matrícula é a única origem
possível, e a §4.8 da governança já previa isto como passo 7.

Esta revisão faz a derivação acontecer NO BANCO, para que a API, o
`vigente.csv` e quem consulta por SQL leiam o mesmo valor:

1. Tabela `polo` (codigo -> nome), semeada com os três códigos validados em
   120/120 linhas reais. Tabela em vez de dicionário no código porque a view
   resolve o nome por JOIN -- polo novo passa a ser INSERT, não deploy.
2. A view `aluno_vigente` ganha `turma`, `polo_cod` e `polo_nome`.

**Por que view e não coluna gerada**, como o DDL da §4.8 sugere. Dois
motivos:

1. Coluna gerada não dispensa a view. Ela resolveria `turma` e `polo_cod`,
   que são recortes da matrícula, mas `polo_nome` sai de um LEFT JOIN com a
   tabela `polo` -- e coluna gerada não pode consultar outra tabela. Seria a
   derivação em dois lugares para entregar um valor só.
2. `usuarios` é tabela de auditoria: append-only, existe para registrar o que
   a fonte mandou. Valor calculado pertence ao modelo de leitura. Com a regra
   na view, reinterpretá-la amanhã é uma revisão que troca a view, sem tocar
   em uma linha de dado histórico.

O SQL da view está copiado aqui de propósito, não importado de
app.db.vigente: migração é um retrato congelado. Mudá-la no futuro é uma
revisão nova, não reescrever esta.

Sobre a expressão: `CASE WHEN length(CAST(matricula AS TEXT)) = 12` protege o
caso que a §4.8 exige -- matrícula fora do padrão devolve NULL em vez de
fatiar lixo e inventar uma turma.

Revision ID: a3f1c2d40b7e
Revises: 1862c00a5abd
Create Date: 2026-09-23 09:20:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c2d40b7e'
down_revision: Union[str, Sequence[str], None] = '1862c00a5abd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLOS = [
    {"codigo": "1604", "nome": "Cametá"},
    {"codigo": "8564", "nome": "Limoeiro"},
    {"codigo": "8594", "nome": "Oeiras"},
]

_DIGITOS = "CAST(ranked.matricula AS TEXT)"
_TURMA = f"CASE WHEN length({_DIGITOS}) = 12 THEN substr({_DIGITOS}, 1, 4) END"
_POLO_COD = f"CASE WHEN length({_DIGITOS}) = 12 THEN substr({_DIGITOS}, 5, 4) END"

VIEW_NOVA = f"""
CREATE VIEW aluno_vigente AS
SELECT
    ranked.*,
    {_TURMA} AS turma,
    {_POLO_COD} AS polo_cod,
    polo.nome AS polo_nome
FROM (
    SELECT u.*, ROW_NUMBER() OVER (
        PARTITION BY u.matricula, u.periodo ORDER BY u.ingestao_id DESC, u.id DESC
    ) AS rn
    FROM usuarios u
) ranked
LEFT JOIN polo ON polo.codigo = {_POLO_COD}
WHERE ranked.rn = 1
"""

VIEW_ANTIGA = """
CREATE VIEW aluno_vigente AS
SELECT * FROM (
    SELECT u.*, ROW_NUMBER() OVER (
        PARTITION BY u.matricula, u.periodo ORDER BY u.ingestao_id DESC, u.id DESC
    ) AS rn
    FROM usuarios u
) ranked WHERE rn = 1
"""


def upgrade() -> None:
    tabela_polo = op.create_table(
        'polo',
        sa.Column('codigo', sa.String(length=4), nullable=False),
        sa.Column('nome', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('codigo'),
    )
    op.bulk_insert(tabela_polo, POLOS)
    # A view referencia `polo`, então só pode ser recriada depois dela.
    op.execute("DROP VIEW IF EXISTS aluno_vigente")
    op.execute(VIEW_NOVA)


def downgrade() -> None:
    # Ordem inversa: a view some antes da tabela de que ela depende.
    op.execute("DROP VIEW IF EXISTS aluno_vigente")
    op.execute(VIEW_ANTIGA)
    op.drop_table('polo')
