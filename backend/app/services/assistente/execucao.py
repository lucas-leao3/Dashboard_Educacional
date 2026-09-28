"""Executa o SELECT do compilador com o mínimo de privilégio (spec, Execução)."""
from sqlalchemy import Select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

ROLE = "leitor_assistente"
TIMEOUT_MS = 5000
_CANCELADA = "57014"  # query_canceled: statement_timeout


class ConsultaDemorada(Exception):
    """Passou do statement_timeout: vira 504 na API."""


def executar_select(session: Session, consulta: Select, timeout_ms: int = TIMEOUT_MS) -> list[dict]:
    """Roda `consulta` como leitor_assistente, com timeout, e encerra a transação.

    SET LOCAL vale até o fim da transação; o rollback no finally garante que
    nem a role nem o timeout sobrevivem para a próxima consulta da sessão.
    Não há nada a desfazer: é só leitura."""
    if not isinstance(consulta, Select):
        raise TypeError("O assistente só executa SELECT montado pelo compilador.")
    try:
        session.execute(text(f"SET LOCAL ROLE {ROLE}"))
        session.execute(text(f"SET LOCAL statement_timeout = {int(timeout_ms)}"))
        return [dict(linha) for linha in session.execute(consulta).mappings()]
    except OperationalError as erro:
        if getattr(erro.orig, "sqlstate", None) == _CANCELADA:
            raise ConsultaDemorada() from erro
        raise
    finally:
        session.rollback()
