"""role leitor_assistente: só leitura, só nas views do assistente

Revision ID: d7a2b4c6e810
Revises: c5e8a1f3d920
Create Date: 2026-09-25

O assistente de consultas executa SQL montado a partir da pergunta de um
usuário. O compilador só produz SELECT, mas a garantia não pode depender só
dele: a execução assume esta role (SET LOCAL ROLE), que tem SELECT apenas nas
duas views que o compilador usa. INSERT, UPDATE, DELETE, DROP, ALTER e
TRUNCATE são recusados pelo próprio banco. Os itens operacionais (relatório
do lote) não passam por aqui: são código fixo, sem SQL derivado da pergunta.

A role é do cluster, não do banco: o downgrade revoga os privilégios mas não a
apaga, porque outros bancos do mesmo servidor (os clones da suíte de testes,
por exemplo) podem ter grants para ela.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd7a2b4c6e810'
down_revision: Union[str, Sequence[str], None] = 'c5e8a1f3d920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE = "leitor_assistente"
VIEWS = "aluno_integrado, crg_semestre_vigente"


def upgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE} NOLOGIN;
            END IF;
        END $$""")
    op.execute(f"GRANT {ROLE} TO CURRENT_USER")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT ON {VIEWS} TO {ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE SELECT ON {VIEWS} FROM {ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE}")
