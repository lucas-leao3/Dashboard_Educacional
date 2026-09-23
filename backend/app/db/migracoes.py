"""Aplicar as migrações do Alembic a partir do código.

Existe para os testes: eles montam um PostgreSQL descartável em contêiner e
precisam do mesmo schema que roda em produção. Rodando as migrações (em vez de
um create_all paralelo) a suíte inteira passa a exercitar o histórico de
migrações -- se alguém mudar um modelo sem gerar a revisão, os testes quebram
na hora.

Em produção quem chama é o `alembic upgrade head` do docker-compose, não isto.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config

# backend/ no repositório, /app no container -- nos dois casos é onde ficam
# alembic.ini e migrations/.
_RAIZ = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _RAIZ / "alembic.ini"


def config_alembic() -> Config:
    config = Config(str(_ALEMBIC_INI))
    # script_location no .ini é relativo ao diretório de trabalho; aqui
    # resolvemos para caminho absoluto, já que o chamador pode estar em
    # qualquer lugar (pytest roda da raiz do repositório).
    config.set_main_option("script_location", str(_RAIZ / "migrations"))
    return config


def aplicar_migracoes(engine) -> None:
    """Leva `engine` até a última revisão. Idempotente."""
    config = config_alembic()
    with engine.begin() as conexao:
        config.attributes["connection"] = conexao
        command.upgrade(config, "head")
