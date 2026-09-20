"""Coleta do FasiTech em dois tempos (docs/governanca_dados.md, 3.2):
buscar_paginas devolve a resposta como veio, num envelope com metadados;
congelar_envelope grava isso em raw/lotes/<id>/fasitech.json ANTES de
qualquer escrita no banco; registros_do_envelope é o que a rota importa."""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.core.config import FASITECH_TOKEN, FASITECH_URL

POR_PAGINA = 100


def buscar_paginas() -> dict:
    """Busca TODAS as páginas da API e devolve um envelope:
    {"url", "params", "coletado_em", "paginas": [corpo de cada página]}."""
    if not FASITECH_URL:
        raise RuntimeError(
            "FASITECH_URL não configurada em backend/.env "
            "(ainda não temos a rota correta do FasiTech para dados por aluno)"
        )

    headers = {"Authorization": f"Bearer {FASITECH_TOKEN}"}
    parametros_base = {"por_pagina": POR_PAGINA, "anonymize_matricula": "false"}
    paginas = []
    pagina = 1
    while True:
        resposta = httpx.get(FASITECH_URL, headers=headers, params={**parametros_base, "pagina": pagina}, timeout=10)
        resposta.raise_for_status()
        corpo = resposta.json()
        paginas.append(corpo)
        if not isinstance(corpo, dict) or pagina >= int(corpo.get("total_paginas", 1)):
            break
        pagina += 1

    return {
        "url": FASITECH_URL,
        "params": parametros_base,
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "paginas": paginas,
    }


def registros_do_envelope(envelope: dict) -> list[dict]:
    registros: list[dict] = []
    for corpo in envelope["paginas"]:
        dados = corpo.get("dados") if isinstance(corpo, dict) else None
        if not isinstance(dados, list):
            raise ValueError("Resposta do FasiTech não é uma lista de alunos (formato inesperado)")
        registros.extend(dados)
    return registros


def congelar_envelope(envelope: dict, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino
