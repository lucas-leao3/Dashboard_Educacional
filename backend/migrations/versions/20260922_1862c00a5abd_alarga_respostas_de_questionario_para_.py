"""alarga respostas de questionario para 150

As larguras originais vieram do vocabulário do CSV legado ("Sim"/"Não",
"Própria"/"Alugada"). A API do FasiTech traz opções mais longas -- entre elas
"Prefiro não responder", 21 caracteres -- e 13 das 19 colunas socioeconômicas
não cabiam. O passo 1 do lote 2026-09-L01 quebrou com

    psycopg.errors.StringDataRightTruncation:
    value too long for type character varying(10)

Largura de coluna não é validação útil aqui: o vocabulário é do instrumento de
pesquisa, muda entre ondas, e apertar a coluna só troca "dado preservado" por
"ingestão derrubada". 150 para todas.

Duas coisas que o autogenerate não escreve sozinho:

1. A view aluno_vigente é SELECT u.* -- depende de toda coluna de usuarios, e o
   PostgreSQL recusa ALTER TYPE em coluna usada por view ("cannot alter type of
   a column used by a view or rule"). Ela cai antes dos ALTER e volta depois.

2. batch_alter_table, não alter_column solto: o SQLite (usado pelos testes) não
   tem ALTER COLUMN, e o batch mode recria a tabela. Em PostgreSQL o batch emite
   ALTER normal.

Atenção no downgrade: o PostgreSQL recusa estreitar a coluna se já houver
resposta mais longa gravada (não trunca, dá erro). Reverter esta revisão com
dado carregado exige tratar essas linhas antes.

Revision ID: 1862c00a5abd
Revises: 4d680647575a
Create Date: 2026-09-22 22:13:23.367684+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1862c00a5abd'
down_revision: Union[str, Sequence[str], None] = '4d680647575a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Cópia do SQL da revisão inicial: migração é retrato congelado.
VIEW_ALUNO_VIGENTE = """
CREATE VIEW aluno_vigente AS
SELECT * FROM (
    SELECT u.*, ROW_NUMBER() OVER (
        PARTITION BY u.matricula, u.periodo ORDER BY u.ingestao_id DESC, u.id DESC
    ) AS rn
    FROM usuarios u
) ranked WHERE rn = 1
"""


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS aluno_vigente")
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.alter_column(
            'genero',
            existing_type=sa.String(length=20),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'cor_etnia',
            existing_type=sa.String(length=10),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'pcd',
            existing_type=sa.String(length=5),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'tipo_deficiencia',
            existing_type=sa.String(length=100),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'assistencia_estudantil',
            existing_type=sa.String(length=5),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'saude_mental',
            existing_type=sa.String(length=10),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'estresse',
            existing_type=sa.String(length=50),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'acompanhamento',
            existing_type=sa.String(length=20),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'escolaridade_pai',
            existing_type=sa.String(length=20),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'escolaridade_mae',
            existing_type=sa.String(length=20),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'qtd_computador',
            existing_type=sa.String(length=20),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'qtd_celular',
            existing_type=sa.String(length=20),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'computador_proprio',
            existing_type=sa.String(length=5),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'gasto_internet',
            existing_type=sa.String(length=30),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'acesso_internet',
            existing_type=sa.String(length=5),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'tipo_moradia',
            existing_type=sa.String(length=10),
            type_=sa.String(length=150),
            existing_nullable=True,
        )
    op.execute(VIEW_ALUNO_VIGENTE)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS aluno_vigente")
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.alter_column(
            'genero',
            existing_type=sa.String(length=150),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'cor_etnia',
            existing_type=sa.String(length=150),
            type_=sa.String(length=10),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'pcd',
            existing_type=sa.String(length=150),
            type_=sa.String(length=5),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'tipo_deficiencia',
            existing_type=sa.String(length=150),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'assistencia_estudantil',
            existing_type=sa.String(length=150),
            type_=sa.String(length=5),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'saude_mental',
            existing_type=sa.String(length=150),
            type_=sa.String(length=10),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'estresse',
            existing_type=sa.String(length=150),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'acompanhamento',
            existing_type=sa.String(length=150),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'escolaridade_pai',
            existing_type=sa.String(length=150),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'escolaridade_mae',
            existing_type=sa.String(length=150),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'qtd_computador',
            existing_type=sa.String(length=150),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'qtd_celular',
            existing_type=sa.String(length=150),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'computador_proprio',
            existing_type=sa.String(length=150),
            type_=sa.String(length=5),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'gasto_internet',
            existing_type=sa.String(length=150),
            type_=sa.String(length=30),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'acesso_internet',
            existing_type=sa.String(length=150),
            type_=sa.String(length=5),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'tipo_moradia',
            existing_type=sa.String(length=150),
            type_=sa.String(length=10),
            existing_nullable=True,
        )
    op.execute(VIEW_ALUNO_VIGENTE)
