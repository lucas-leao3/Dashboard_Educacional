"""Testes de scripts/lote.py -- sem rede de verdade: cada teste monta um
httpx.MockTransport com as respostas que a API daria."""
import io
import zipfile

import httpx

from scripts import lote


def _client(handler) -> httpx.Client:
    return httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler))


IMPORTACAO_RESPOSTA = {
    "id": "2026-09-L02",
    "executado_em": "2026-09-25T10:00:00Z",
    "fechado_em": "2026-09-25T10:01:00Z",
    "periodos_cobertos": ["2025.2"],
    "executado_por": "Edinaldo",
    "observacao": None,
    "ingestoes": [],
    "excecoes_por_motivo": {},
    "arquivos": {"gravados": ["a.pdf", "b.pdf"], "ja_existiam": [], "ignorados": ["leiame.txt"]},
    "sincronizar": {"importados": 3, "rejeitados": 0},
    "atualizar_crg": {"pdfs_lidos": 2},
    "arquivos_gerados": ["/data/raw/lotes/2026-09-L02/SHA256SUMS", "/data/processed/2026-09-L02/integrados.csv"],
    "resumo": {"total": 3, "integrados": 2, "nao_integrados": 1, "por_motivo": {"sem_academico": 1},
               "preenchimento_medio_integrados": 80.0},
}


def _captura(recebido: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        recebido["metodo"], recebido["caminho"] = request.method, request.url.path
        recebido["corpo"] = request.read()
        return httpx.Response(201, json=IMPORTACAO_RESPOSTA)
    return handler


def test_importar_envia_responsavel_e_zip_e_imprime_o_resumo(tmp_path, capsys):
    arquivo = tmp_path / "historicos.zip"
    arquivo.write_bytes(b"PK zip falso")
    recebido: dict = {}
    with _client(_captura(recebido)) as client:
        assert lote.importar(client, "Edinaldo", arquivo) == 0

    assert (recebido["metodo"], recebido["caminho"]) == ("POST", "/lotes/importar")
    assert b'name="responsavel"' in recebido["corpo"] and b"Edinaldo" in recebido["corpo"]
    assert b'filename="historicos.zip"' in recebido["corpo"] and b"PK zip falso" in recebido["corpo"]
    saida = capsys.readouterr().out
    assert "2026-09-L02" in saida
    assert "Período (extraído dos históricos): 2025.2" in saida
    assert "Integrados: 2" in saida
    assert "sem_academico: 1" in saida
    assert "leiame.txt" in saida


def test_importar_pasta_compacta_so_os_pdfs(tmp_path):
    pasta = tmp_path / "historicos"
    pasta.mkdir()
    (pasta / "a.pdf").write_bytes(b"a")
    (pasta / "B.PDF").write_bytes(b"b")
    (pasta / "notas.txt").write_bytes(b"x")
    recebido: dict = {}
    with _client(_captura(recebido)) as client:
        assert lote.importar(client, "Edinaldo", pasta) == 0

    corpo = recebido["corpo"]
    inicio = corpo.index(b"PK")
    with zipfile.ZipFile(io.BytesIO(corpo[inicio:])) as z:
        assert sorted(z.namelist()) == ["B.PDF", "a.pdf"]


def test_importar_arquivo_que_nao_e_zip_nem_pasta_nao_chama_a_api(tmp_path, capsys):
    arquivo = tmp_path / "a.pdf"
    arquivo.write_bytes(b"%PDF")

    def handler(request):
        raise AssertionError("não devia chamar a API")

    with _client(handler) as client:
        assert lote.importar(client, "Edinaldo", arquivo) == 1
    assert "não é um .zip" in capsys.readouterr().err


def test_importar_recusada_mostra_o_detalhe_da_api(tmp_path, capsys):
    arquivo = tmp_path / "h.zip"
    arquivo.write_bytes(b"PK")

    def handler(request):
        return httpx.Response(502, json={"detail": "Erro ao consultar o FasiTech: timeout"})

    with _client(handler) as client:
        assert lote.importar(client, "Edinaldo", arquivo) == 1
    erro = capsys.readouterr().err
    assert "nada foi gravado" in erro
    assert "timeout" in erro


def test_relatorio_imprime_integrados_e_nao_integrados(capsys):
    def handler(request):
        assert request.url.path == "/lotes/2026-09-L02/relatorio"
        return httpx.Response(200, json={
            "lote": "2026-09-L02",
            "resumo": IMPORTACAO_RESPOSTA["resumo"],
            "integrados": [{"matricula": 1, "nome": "A", "academico": True, "socioeconomico": True,
                            "status": "Integrado com sucesso", "campos_avaliados": 10,
                            "qtd_campos_sem_resposta": 2, "campos_sem_resposta": ["renda", "trabalho"],
                            "percentual_preenchimento": 80.0}],
            "nao_integrados": [{"matricula": 2, "nome": None, "academico": False, "socioeconomico": True,
                                "motivo": "sem_academico",
                                "motivo_descricao": "Possui socioeconômico e não possui acadêmico",
                                "detalhe": None, "campos_avaliados": 12, "qtd_campos_sem_resposta": 0,
                                "campos_sem_resposta": [], "percentual_preenchimento": 100.0}],
        })

    with _client(handler) as client:
        assert lote.relatorio(client, "2026-09-L02") == 0
    saida = capsys.readouterr().out
    assert "renda, trabalho" in saida
    assert "Possui socioeconômico e não possui acadêmico" in saida
    assert "nenhum" in saida


def test_main_exige_responsavel():
    import pytest
    with pytest.raises(SystemExit):
        lote.main(["importar", "h.zip"])
