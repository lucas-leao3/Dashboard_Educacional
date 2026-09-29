"""Taxa de acerto da interpretação contra o Groq REAL (métrica para a dissertação).

Fora da suíte padrão: rode com
    AVALIAR_LLM=1 GROQ_API_KEY=... pytest tests/test_assistente_avaliacao.py -s
AVALIAR_LLM_MINIMO=0.8 faz o teste falhar abaixo de 80%.

Os `valores` do JSON são os do banco real, gerados como descrito no Step 3 da
Task 12 do plano. Acerto = mesmo tipo, métrica, dimensões e filtros."""
import json
import os
from pathlib import Path

import pytest

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.intencao import interpretar
from app.services.assistente.provedor_llm import provedor_padrao

pytestmark = pytest.mark.skipif(os.getenv("AVALIAR_LLM") != "1", reason="avaliação contra o LLM real: AVALIAR_LLM=1")
ARQUIVO = Path(__file__).with_name("avaliacao_assistente.json")


def _chave(c: ConsultaEstruturada):
    filtros = frozenset((f.campo, json.dumps(f.valor, ensure_ascii=False)) for f in c.filtros)
    return c.tipo, c.metrica, frozenset(c.dimensoes), filtros


def test_taxa_de_acerto_da_interpretacao():
    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    provedor = provedor_padrao()
    acertos, relatorio = 0, []
    for caso in dados["casos"]:
        obtida = interpretar(provedor, caso["pergunta"], dados["valores"])
        ok = obtida is not None and _chave(obtida) == _chave(ConsultaEstruturada(**caso["esperado"]))
        acertos += ok
        relatorio.append(f"{'OK ' if ok else 'ERR'} {caso['pergunta']} -> {obtida.model_dump_json() if obtida else None}")
    taxa = acertos / len(dados["casos"])
    print("\n".join(relatorio), f"\ntaxa de acerto: {taxa:.0%} ({acertos}/{len(dados['casos'])})")
    assert taxa >= float(os.getenv("AVALIAR_LLM_MINIMO", "0"))
