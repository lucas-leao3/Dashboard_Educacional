"""importação simplificada: historico, aluno_integrado e lote fechado imutável

Três peças da governança simplificada (docs/governanca_simplificada.md):

1. **Tabela `historico`.** Uma linha por PDF de histórico lido: matrícula,
   nome, nascimento, data de emissão e o `periodo` extraído dela (semestre
   letivo da data "Emitido em"). É daqui que sai `lote.periodos_cobertos` --
   o usuário não informa mais o período. Também dá nome a quem tem histórico
   e não tem resposta no FasiTech, que antes não ficava em lugar nenhum.

2. **View `aluno_integrado`.** `aluno_vigente` restrita a quem passou pelo
   cruzamento: tem socioeconômico (linha em `usuarios`) E acadêmico (CRG por
   semestre extraído de um histórico). É a única base dos dashboards.

3. **Lote fechado é imutável no banco, não só na API.** Triggers recusam
   UPDATE/DELETE em `lote` fechado e qualquer INSERT/UPDATE/DELETE em linha
   ligada a um lote fechado (ingestao, arquivo_fonte, usuarios, crg_semestre,
   excecao, historico). A importação grava tudo e fecha o lote na mesma
   transação, então os triggers só mordem depois do COMMIT.

O SQL está copiado aqui de propósito, não importado de app.db.vigente:
migração é um retrato congelado.

Revision ID: c5e8a1f3d920
Revises: b7c4e9a21d38
Create Date: 2026-09-25 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e8a1f3d920'
down_revision: Union[str, Sequence[str], None] = 'b7c4e9a21d38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VIEW_INTEGRADO = """
CREATE VIEW aluno_integrado AS
SELECT av.*
FROM aluno_vigente av
WHERE EXISTS (SELECT 1 FROM crg_semestre c WHERE c.matricula = av.matricula)
"""

FUNCAO_LOTE = """
CREATE FUNCTION lote_fechado_imutavel() RETURNS trigger AS $$
BEGIN
    IF OLD.fechado_em IS NOT NULL THEN
        RAISE EXCEPTION 'Lote % está fechado desde %: não pode ser alterado nem apagado.',
            OLD.id, OLD.fechado_em USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$$ LANGUAGE plpgsql
"""

# Uma função para as seis tabelas-filhas: a linha aponta para o lote direto
# (lote_id) ou através da ingestão (ingestao_id). to_jsonb evita uma função
# por tabela só para ler a coluna certa.
FUNCAO_FILHAS = """
CREATE FUNCTION recusa_escrita_em_lote_fechado() RETURNS trigger AS $$
DECLARE
    linhas jsonb[];
    linha jsonb;
    alvo text;
    fechado timestamptz;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        linhas := array_append(linhas, to_jsonb(OLD));
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        linhas := array_append(linhas, to_jsonb(NEW));
    END IF;
    FOREACH linha IN ARRAY linhas LOOP
        alvo := linha->>'lote_id';
        IF alvo IS NULL THEN
            SELECT i.lote_id INTO alvo FROM ingestao i WHERE i.id = (linha->>'ingestao_id')::int;
        END IF;
        SELECT l.fechado_em INTO fechado FROM lote l WHERE l.id = alvo;
        IF fechado IS NOT NULL THEN
            RAISE EXCEPTION 'Lote % está fechado desde %: % não aceita escrita ligada a ele.',
                alvo, fechado, TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    END LOOP;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$$ LANGUAGE plpgsql
"""

TABELAS_FILHAS = ("ingestao", "arquivo_fonte", "usuarios", "crg_semestre", "excecao", "historico")


def upgrade() -> None:
    op.create_table(
        "historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ingestao_id", sa.Integer(), sa.ForeignKey("ingestao.id"), nullable=False),
        sa.Column("arquivo_sha256", sa.String(64), sa.ForeignKey("arquivo_fonte.sha256"), nullable=True),
        sa.Column("matricula", sa.BigInteger(), nullable=False),
        sa.Column("nome", sa.String(100), nullable=True),
        sa.Column("data_de_nascimento", sa.String(), nullable=True),
        sa.Column("emitido_em", sa.Date(), nullable=False),
        sa.Column("periodo", sa.String(6), nullable=False),
    )
    op.create_index("ix_historico_matricula", "historico", ["matricula"])

    op.execute(VIEW_INTEGRADO)

    op.execute(FUNCAO_LOTE)
    op.execute(
        "CREATE TRIGGER lote_imutavel BEFORE UPDATE OR DELETE ON lote "
        "FOR EACH ROW EXECUTE FUNCTION lote_fechado_imutavel()"
    )
    op.execute(FUNCAO_FILHAS)
    for tabela in TABELAS_FILHAS:
        op.execute(
            f"CREATE TRIGGER {tabela}_lote_fechado BEFORE INSERT OR UPDATE OR DELETE ON {tabela} "
            "FOR EACH ROW EXECUTE FUNCTION recusa_escrita_em_lote_fechado()"
        )


def downgrade() -> None:
    for tabela in TABELAS_FILHAS:
        op.execute(f"DROP TRIGGER IF EXISTS {tabela}_lote_fechado ON {tabela}")
    op.execute("DROP FUNCTION IF EXISTS recusa_escrita_em_lote_fechado()")
    op.execute("DROP TRIGGER IF EXISTS lote_imutavel ON lote")
    op.execute("DROP FUNCTION IF EXISTS lote_fechado_imutavel()")
    op.execute("DROP VIEW IF EXISTS aluno_integrado")
    op.drop_index("ix_historico_matricula", table_name="historico")
    op.drop_table("historico")
