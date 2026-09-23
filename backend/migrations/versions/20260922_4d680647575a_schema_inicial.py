"""schema inicial

Estado do schema no momento em que o Alembic passou a versioná-lo: as seis
tabelas de app.db.engine mais a view aluno_vigente. Bancos que já existiam
antes desta revisão foram marcados com `alembic stamp` -- ver
docs/governanca_dados.md.

O SQL da view está copiado aqui de propósito, não importado de
app.db.vigente: migração é um retrato congelado, e mudar a view no futuro
tem que virar uma nova revisão, não reescrever esta.

Revision ID: 4d680647575a
Revises: 
Create Date: 2026-09-22 22:01:32.878367+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d680647575a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    op.create_table('lote',
    sa.Column('id', sa.String(length=20), nullable=False),
    sa.Column('executado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('periodos_cobertos', sa.String(length=100), nullable=False),
    sa.Column('executado_por', sa.String(length=100), nullable=True),
    sa.Column('observacao', sa.Text(), nullable=True),
    sa.Column('fechado_em', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('arquivo_fonte',
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('lote_id', sa.String(length=20), nullable=False),
    sa.Column('nome_original', sa.String(length=255), nullable=False),
    sa.Column('tipo', sa.String(length=30), nullable=False),
    sa.Column('tamanho_bytes', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['lote_id'], ['lote.id'], ),
    sa.PrimaryKeyConstraint('sha256')
    )
    op.create_table('ingestao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lote_id', sa.String(length=20), nullable=False),
    sa.Column('passo', sa.Integer(), nullable=False),
    sa.Column('arquivo_sha256', sa.String(length=64), nullable=True),
    sa.Column('executado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('registros_lidos', sa.Integer(), nullable=False),
    sa.Column('registros_aceitos', sa.Integer(), nullable=False),
    sa.Column('registros_rejeitados', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['arquivo_sha256'], ['arquivo_fonte.sha256'], ),
    sa.ForeignKeyConstraint(['lote_id'], ['lote.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lote_id', 'passo', name='ux_ingestao_lote_passo')
    )
    op.create_table('crg_semestre',
    sa.Column('matricula', sa.BigInteger(), nullable=False),
    sa.Column('semestre', sa.String(length=6), nullable=False),
    sa.Column('ingestao_id', sa.Integer(), nullable=False),
    sa.Column('crg', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['ingestao_id'], ['ingestao.id'], ),
    sa.PrimaryKeyConstraint('matricula', 'semestre', 'ingestao_id')
    )
    op.create_table('excecao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ingestao_id', sa.Integer(), nullable=False),
    sa.Column('matricula', sa.BigInteger(), nullable=True),
    sa.Column('periodo', sa.String(length=15), nullable=True),
    sa.Column('motivo', sa.String(length=30), nullable=False),
    sa.Column('detalhe', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['ingestao_id'], ['ingestao.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ingestao_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=100), nullable=True),
    sa.Column('data_de_nascimento', sa.String(), nullable=True),
    sa.Column('matricula', sa.BigInteger(), nullable=False),
    sa.Column('primeiro_ano_eletivo', sa.String(length=10), nullable=True),
    sa.Column('CRG', sa.Float(), nullable=True),
    sa.Column('periodo', sa.String(length=15), nullable=False),
    sa.Column('genero', sa.String(length=20), nullable=True),
    sa.Column('polo', sa.String(length=15), nullable=True),
    sa.Column('cor_etnia', sa.String(length=10), nullable=True),
    sa.Column('pcd', sa.String(length=5), nullable=True),
    sa.Column('tipo_deficiencia', sa.String(length=100), nullable=True),
    sa.Column('renda', sa.String(length=150), nullable=True),
    sa.Column('deslocamento', sa.String(length=150), nullable=True),
    sa.Column('trabalho', sa.String(length=150), nullable=True),
    sa.Column('assistencia_estudantil', sa.String(length=5), nullable=True),
    sa.Column('saude_mental', sa.String(length=10), nullable=True),
    sa.Column('estresse', sa.String(length=50), nullable=True),
    sa.Column('acompanhamento', sa.String(length=20), nullable=True),
    sa.Column('escolaridade_pai', sa.String(length=20), nullable=True),
    sa.Column('escolaridade_mae', sa.String(length=20), nullable=True),
    sa.Column('qtd_computador', sa.String(length=20), nullable=True),
    sa.Column('qtd_celular', sa.String(length=20), nullable=True),
    sa.Column('computador_proprio', sa.String(length=5), nullable=True),
    sa.Column('gasto_internet', sa.String(length=30), nullable=True),
    sa.Column('acesso_internet', sa.String(length=5), nullable=True),
    sa.Column('tipo_moradia', sa.String(length=10), nullable=True),
    sa.Column('data_hora', sa.String(length=20), nullable=True),
    sa.ForeignKeyConstraint(['ingestao_id'], ['ingestao.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.execute(VIEW_ALUNO_VIGENTE)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS aluno_vigente")
    op.drop_table('usuarios')
    op.drop_table('excecao')
    op.drop_table('crg_semestre')
    op.drop_table('ingestao')
    op.drop_table('arquivo_fonte')
    op.drop_table('lote')
