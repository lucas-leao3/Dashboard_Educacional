"""Ambiente do Alembic.

A URL do banco NÃO fica no alembic.ini: vem de app.core.config.DATABASE_URL,
a mesma que a aplicação usa. Assim migração e aplicação nunca apontam para
bancos diferentes, e o segredo continua só no backend/.env.

O target_metadata é o Base.metadata dos modelos -- é contra ele que o
`alembic revision --autogenerate` compara o banco para detectar diferenças.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import DATABASE_URL
from app.db.engine import Base

config = context.config

# Os testes injetam a conexão do PostgreSQL descartável em config.attributes
# (ver app.db.migracoes e tests/conftest.py). Fora deles, vale a URL da
# aplicação.
_CONEXAO_INJETADA = config.attributes.get("connection")
if _CONEXAO_INJETADA is None:
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# As views são criadas por migração (op.execute), não pelo metadata. Sem isto
# o autogenerate as trataria como tabelas estranhas e proporia dropá-las.
_IGNORAR = {"aluno_vigente", "crg_semestre_vigente", "aluno_integrado"}


def include_object(objeto, nome, tipo, reflexo, comparar_com):
    if tipo == "table" and nome in _IGNORAR:
        return False
    return True


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar (alembic upgrade head --sql), pra revisão."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _executar(conexao) -> None:
    context.configure(
        connection=conexao,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        # Sem render_as_batch: ele existia para o SQLite, que não tem ALTER
        # completo. O projeto roda só em PostgreSQL, que tem -- o batch mode
        # recriaria tabela à toa e esconderia o DDL real da revisão.
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if _CONEXAO_INJETADA is not None:
        _executar(_CONEXAO_INJETADA)
        return

    conectavel = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with conectavel.connect() as conexao:
        _executar(conexao)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
