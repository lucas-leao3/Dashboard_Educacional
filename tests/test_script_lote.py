"""Testes de scripts/lote.py -- sem rede de verdade: cada teste monta um
httpx.MockTransport com as respostas que a API daria."""
import httpx
import pytest

from scripts import lote


def _client(handler) -> httpx.Client:
    return httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# rodar: sincronizar antes de atualizar-crg; falha no primeiro para o segundo
# ---------------------------------------------------------------------------

def test_rodar_chama_sincronizar_antes_de_atualizar_crg():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/lotes/L01":
            return httpx.Response(200, json={**LOTE_RESPOSTA, "id": "L01", "ingestoes": []})
        chamadas.append(request.url.path)
        if request.url.path == "/alunos/sincronizar":
            return httpx.Response(200, json={"lote": "L01", "ingestao_id": 1, "importados": 5, "rejeitados": 0})
        if request.url.path == "/alunos/atualizar-crg":
            return httpx.Response(200, json={"lote": "L01", "ingestao_id": 2, "alunos_atualizados": 5})
        raise AssertionError(f"rota inesperada: {request.url.path}")

    with _client(handler) as client:
        codigo = lote.rodar(client, "L01")

    assert codigo == 0
    assert chamadas == ["/alunos/sincronizar", "/alunos/atualizar-crg"]


def test_rodar_nao_chama_atualizar_crg_se_sincronizar_falhar():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/lotes/L01":
            return httpx.Response(200, json={**LOTE_RESPOSTA, "id": "L01", "ingestoes": []})
        chamadas.append(request.url.path)
        if request.url.path == "/alunos/sincronizar":
            return httpx.Response(503, json={"detail": "FasiTech fora do ar"})
        raise AssertionError(f"não devia chamar {request.url.path}")

    with _client(handler) as client:
        codigo = lote.rodar(client, "L01")

    assert codigo != 0
    assert chamadas == ["/alunos/sincronizar"]


# ---------------------------------------------------------------------------
# fechar: POST /lotes/{id}/fechar -- a geração dos arquivos é da API
# ---------------------------------------------------------------------------

LOTE_RESPOSTA = {
    "id": "2026-09-L01",
    "executado_em": "2026-09-12T10:00:00Z",
    "fechado_em": None,
    "periodos_cobertos": ["2025.2", "2026.1"],
    "executado_por": "edinaldo",
    "observacao": None,
    "ingestoes": [
        {"id": 1, "passo": 1, "arquivo_sha256": "abc", "executado_em": "2026-09-12T10:00:00Z",
         "registros_lidos": 10, "registros_aceitos": 9, "registros_rejeitados": 1},
        {"id": 2, "passo": 2, "arquivo_sha256": None, "executado_em": "2026-09-12T10:05:00Z",
         "registros_lidos": 5, "registros_aceitos": 4, "registros_rejeitados": 1},
    ],
    "excecoes_por_motivo": {"sem_academico": 1, "sem_socioeconomico": 1},
}


def test_fechar_chama_o_endpoint_e_imprime_os_arquivos_gerados(capsys):
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append((request.method, request.url.path))
        return httpx.Response(200, json={
            **LOTE_RESPOSTA, "fechado_em": "2026-09-12T11:00:00Z",
            "arquivos_gerados": ["/data/raw/lotes/2026-09-L01/SHA256SUMS", "/data/raw/lotes/2026-09-L01/lote.md",
                                 "/data/processed/2026-09-L01/vigente.csv", "/data/processed/2026-09-L01/correspondencia.csv"],
        })

    with _client(handler) as client:
        codigo = lote.fechar(client, "2026-09-L01")

    assert codigo == 0
    assert chamadas == [("POST", "/lotes/2026-09-L01/fechar")]
    saida = capsys.readouterr().out
    assert "2026-09-12T11:00:00Z" in saida
    assert "lote.md" in saida and "correspondencia.csv" in saida


def test_fechar_repassa_recusa_da_api(capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Lote '2026-09-L01' está fechado desde ..."})

    with _client(handler) as client:
        codigo = lote.fechar(client, "2026-09-L01")

    assert codigo != 0
    assert "está fechado" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# enviar: pasta, zip ou PDFs soltos -> POST /lotes/{id}/historicos
# ---------------------------------------------------------------------------

def _handler_enviar(recebidos: list):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/lotes/2026-09-L01/historicos"
        assert request.headers["content-type"].startswith("multipart/form-data")
        recebidos.append(request.content)
        return httpx.Response(200, json={"lote": "2026-09-L01", "gravados": ["700001.pdf", "700002.pdf"],
                                         "ja_existiam": [], "ignorados": ["leiame.txt"]})
    return handler


def test_enviar_pasta_manda_so_os_pdfs(tmp_path, capsys):
    pasta = tmp_path / "historicos"
    pasta.mkdir()
    (pasta / "700001.pdf").write_bytes(b"um")
    (pasta / "700002.PDF").write_bytes(b"dois")
    (pasta / "leiame.txt").write_bytes(b"nao vai")
    recebidos: list[bytes] = []

    with _client(_handler_enviar(recebidos)) as client:
        codigo = lote.enviar(client, "2026-09-L01", [pasta])

    assert codigo == 0
    corpo = recebidos[0]
    assert b'filename="700001.pdf"' in corpo
    assert b'filename="700002.PDF"' in corpo
    assert b"leiame.txt" not in corpo
    saida = capsys.readouterr().out
    assert "gravados=2" in saida and "ignorados=1" in saida


def test_enviar_zip_e_pdf_soltos_vao_como_estao(tmp_path):
    zip_ = tmp_path / "historicos.zip"
    zip_.write_bytes(b"PK zip falso")
    pdf = tmp_path / "700003.pdf"
    pdf.write_bytes(b"tres")
    recebidos: list[bytes] = []

    with _client(_handler_enviar(recebidos)) as client:
        codigo = lote.enviar(client, "2026-09-L01", [zip_, pdf])

    assert codigo == 0
    corpo = recebidos[0]
    assert b'filename="historicos.zip"' in corpo
    assert b'filename="700003.pdf"' in corpo


def test_enviar_sem_nenhum_pdf_falha_sem_chamar_a_api(tmp_path):
    vazia = tmp_path / "vazia"
    vazia.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("não devia chamar a API sem arquivos")

    with _client(handler) as client:
        codigo = lote.enviar(client, "2026-09-L01", [vazia])

    assert codigo != 0


def test_enviar_repassa_erro_da_api(tmp_path):
    pdf = tmp_path / "700001.pdf"
    pdf.write_bytes(b"um")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Passo 2 já foi executado"})

    with _client(handler) as client:
        codigo = lote.enviar(client, "2026-09-L01", [pdf])

    assert codigo != 0


# ---------------------------------------------------------------------------
# rodar pula passo já executado (reexecução depois de falha no passo 2)
# ---------------------------------------------------------------------------

def test_rodar_pula_passo_1_se_ja_executou_e_roda_o_2():
    chamadas = []
    so_passo_1 = {**LOTE_RESPOSTA, "ingestoes": [LOTE_RESPOSTA["ingestoes"][0]]}

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request.url.path)
        if request.url.path == "/lotes/2026-09-L01":
            return httpx.Response(200, json=so_passo_1)
        if request.url.path == "/alunos/atualizar-crg":
            return httpx.Response(200, json={"lote": "2026-09-L01", "ingestao_id": 2, "alunos_atualizados": 5})
        raise AssertionError(f"não devia chamar {request.url.path}")

    with _client(handler) as client:
        codigo = lote.rodar(client, "2026-09-L01")

    assert codigo == 0
    assert "/alunos/sincronizar" not in chamadas
    assert "/alunos/atualizar-crg" in chamadas


def test_rodar_com_os_dois_passos_feitos_nao_chama_nada_e_devolve_0():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request.url.path)
        if request.url.path == "/lotes/2026-09-L01":
            return httpx.Response(200, json=LOTE_RESPOSTA)
        raise AssertionError(f"não devia chamar {request.url.path}")

    with _client(handler) as client:
        codigo = lote.rodar(client, "2026-09-L01")

    assert codigo == 0
    assert chamadas == ["/lotes/2026-09-L01"]


# ---------------------------------------------------------------------------
# executar: abrir -> enviar -> rodar; fechar fica de fora de propósito
# ---------------------------------------------------------------------------

def _handler_executar(chamadas: list, abrir_status: int = 201, enviar_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append((request.method, request.url.path))
        if request.url.path == "/lotes" and request.method == "POST":
            return httpx.Response(abrir_status, json={"detail": "já existe"} if abrir_status >= 400 else {**LOTE_RESPOSTA, "ingestoes": []})
        if request.url.path == "/lotes/2026-09-L01/historicos":
            return httpx.Response(enviar_status, json={"detail": "erro"} if enviar_status >= 400 else
                                  {"lote": "2026-09-L01", "gravados": ["700001.pdf"], "ja_existiam": [], "ignorados": []})
        if request.url.path == "/lotes/2026-09-L01":
            return httpx.Response(200, json={**LOTE_RESPOSTA, "ingestoes": []})
        if request.url.path == "/alunos/sincronizar":
            return httpx.Response(200, json={"lote": "2026-09-L01", "ingestao_id": 1, "importados": 5, "rejeitados": 0})
        if request.url.path == "/alunos/atualizar-crg":
            return httpx.Response(200, json={"lote": "2026-09-L01", "ingestao_id": 2, "alunos_atualizados": 5})
        raise AssertionError(f"rota inesperada: {request.method} {request.url.path}")
    return handler


def test_executar_encadeia_abrir_enviar_rodar(tmp_path):
    pdf = tmp_path / "700001.pdf"
    pdf.write_bytes(b"um")
    chamadas: list = []

    with _client(_handler_executar(chamadas)) as client:
        codigo = lote.executar(client, tmp_path, "2026-09-L01", ["2025.2", "2026.1"], "edinaldo", None, [pdf])

    assert codigo == 0
    assert [c[1] for c in chamadas] == [
        "/lotes", "/lotes/2026-09-L01/historicos", "/lotes/2026-09-L01",
        "/alunos/sincronizar", "/alunos/atualizar-crg",
    ]


def test_executar_segue_se_lote_ja_estava_aberto(tmp_path):
    pdf = tmp_path / "700001.pdf"
    pdf.write_bytes(b"um")
    chamadas: list = []

    with _client(_handler_executar(chamadas, abrir_status=409)) as client:
        codigo = lote.executar(client, tmp_path, "2026-09-L01", ["2026.1"], None, None, [pdf])

    assert codigo == 0
    assert ("POST", "/lotes/2026-09-L01/historicos") in chamadas
    assert ("POST", "/alunos/atualizar-crg") in chamadas


def test_executar_para_se_enviar_falhar(tmp_path):
    pdf = tmp_path / "700001.pdf"
    pdf.write_bytes(b"um")
    chamadas: list = []

    with _client(_handler_executar(chamadas, enviar_status=409)) as client:
        codigo = lote.executar(client, tmp_path, "2026-09-L01", ["2026.1"], None, None, [pdf])

    assert codigo != 0
    assert ("POST", "/alunos/sincronizar") not in chamadas
