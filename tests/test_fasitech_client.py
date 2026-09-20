import json

import pytest

from app.services.fasitech_client import congelar_envelope, registros_do_envelope


def test_registros_do_envelope_concatena_paginas():
    envelope = {"paginas": [{"dados": [{"matricula": 1}], "pagina": 1}, {"dados": [{"matricula": 2}], "pagina": 2}]}
    assert registros_do_envelope(envelope) == [{"matricula": 1}, {"matricula": 2}]


def test_registros_do_envelope_formato_inesperado_da_erro():
    with pytest.raises(ValueError):
        registros_do_envelope({"paginas": [{"total": 165, "pagina": 1}]})


def test_congelar_envelope_grava_json_legivel(tmp_path):
    envelope = {"url": "http://x", "params": {"pagina": 1}, "coletado_em": "2026-09-12T00:00:00+00:00", "paginas": [{"dados": [{"nome": "José"}]}]}
    destino = congelar_envelope(envelope, tmp_path / "lote" / "fasitech.json")
    assert destino.exists()
    assert json.loads(destino.read_text(encoding="utf-8")) == envelope
    assert "José" in destino.read_text(encoding="utf-8")  # ensure_ascii=False
