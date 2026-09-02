import httpx

from app.core.config import FASITECH_TOKEN, FASITECH_URL

POR_PAGINA = 100


def buscar_dados_socioeconomicos() -> list[dict]:
    """Busca TODOS os alunos na API do FasiTech, paginando até acabar.

    A URL vem de FASITECH_URL (backend/.env). A resposta de cada página vem
    no formato {"dados": [...], "pagina": N, "total_paginas": M, ...}; a
    função junta os "dados" de todas as páginas antes de devolver.
    """
    if not FASITECH_URL:
        raise RuntimeError(
            "FASITECH_URL não configurada em backend/.env "
            "(ainda não temos a rota correta do FasiTech para dados por aluno)"
        )

    headers = {"Authorization": f"Bearer {FASITECH_TOKEN}"}
    todos_os_registros = []
    pagina = 1

    while True:
        parametros = {
            "pagina": pagina,
            "por_pagina": POR_PAGINA,
            "anonymize_matricula": "false",
        }
        resposta = httpx.get(FASITECH_URL, headers=headers, params=parametros, timeout=10)
        resposta.raise_for_status()
        corpo = resposta.json()

        todos_os_registros.extend(corpo["dados"])

        if pagina >= corpo["total_paginas"]:
            break
        pagina += 1

    return todos_os_registros
