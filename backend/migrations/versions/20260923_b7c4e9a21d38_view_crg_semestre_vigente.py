"""view crg_semestre_vigente

`crg_semestre` é append-only como `usuarios`: sua chave primária inclui
`ingestao_id`, então rodar um segundo lote grava o mesmo (matricula, semestre)
de novo. Ninguém consumia a tabela fora do fechamento, e por isso a falta de um
"valor de agora" não tinha aparecido -- agora o dashboard vai ler dela para a
trajetória por semestre, e sem esta view o gráfico desenharia o mesmo semestre
duas vezes.

Mesma lógica da `aluno_vigente` (governança §4.5): a linha da ingestão mais
recente por chave de negócio. Aqui não há desempate por `id` porque
`crg_semestre` não tem um -- `ingestao_id DESC` basta, já que a chave primária
impede duas linhas do mesmo semestre na mesma ingestão.

`crg` NULL continua sendo informação, não ausência: semestre ainda não apurado
na data de emissão do histórico (§4.6, a regra do zero). A view preserva o NULL
em vez de filtrar a linha, para quem consome poder distinguir "não apurado" de
"não existe".

O SQL está copiado aqui de propósito, não importado de app.db.vigente:
migração é um retrato congelado.

Revision ID: b7c4e9a21d38
Revises: a3f1c2d40b7e
Create Date: 2026-09-23 10:05:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7c4e9a21d38'
down_revision: Union[str, Sequence[str], None] = 'a3f1c2d40b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VIEW = """
CREATE VIEW crg_semestre_vigente AS
SELECT matricula, semestre, crg, ingestao_id
FROM (
    SELECT c.*, ROW_NUMBER() OVER (
        PARTITION BY c.matricula, c.semestre ORDER BY c.ingestao_id DESC
    ) AS rn
    FROM crg_semestre c
) ranked
WHERE rn = 1
"""


def upgrade() -> None:
    op.execute(VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS crg_semestre_vigente")
