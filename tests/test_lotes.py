import csv
import hashlib
import io
import zipfile

import httpx
import pytest

import app.api.alunos as rotas_alunos
from sqlalchemy.orm import Session, sessionmaker

from app.core import config
from app.db.engine import Excecao, Ingestao, Usuarios
from app.schemas.alunos import AlunoOut


async def test_criar_lote_cria_diretorio_e_registro(client):
    resposta = await client.post("/lotes", json={
        "id": "2026-09-L01",
        "periodos_cobertos": ["2025.2", "2026.1"],
        "executado_por": "edinaldo",
    })
    assert resposta.status_code == 201, resposta.json()
    corpo = resposta.json()
    assert corpo["id"] == "2026-09-L01"
    assert corpo["periodos_cobertos"] == ["2025.2", "2026.1"]
    assert corpo["ingestoes"] == []
    assert corpo["excecoes_por_motivo"] == {}
    assert (config.RAIZ_LOTES / "2026-09-L01" / "historicos").is_dir()


async def test_criar_lote_duplicado_da_409(client):
    body = {"id": "2026-09-L01", "periodos_cobertos": ["2026.1"]}
    await client.post("/lotes", json=body)
    resposta = await client.post("/lotes", json=body)
    assert resposta.status_code == 409


async def test_criar_lote_com_id_invalido_da_422(client):
    resposta = await client.post("/lotes", json={"id": "../fora", "periodos_cobertos": ["2026.1"]})
    assert resposta.status_code == 422


async def test_listar_e_buscar_lote(client):
    await client.post("/lotes", json={"id": "2026-09-L01", "periodos_cobertos": ["2026.1"]})
    lista = await client.get("/lotes")
    assert [l["id"] for l in lista.json()] == ["2026-09-L01"]
    um = await client.get("/lotes/2026-09-L01")
    assert um.status_code == 200
    assert (await client.get("/lotes/L99")).status_code == 404


async def test_criar_lote_desfaz_diretorio_se_commit_falhar(client):
    """Se o commit falhar depois que a pasta já foi criada, a pasta tem que
    sumir -- senão o id fica preso: toda tentativa seguinte bate no
    FileExistsError e devolve 409 pra sempre, sem nunca ter registro.

    Usa um pytest.MonkeyPatch próprio (não o fixture `monkeypatch`, que é
    compartilhado com o fixture `client` -- um `.undo()` nele desfaria
    também o RAIZ_LOTES apontando pro tmp_path)."""
    lote_id = "2026-09-L02"

    def commit_explode(self):
        raise RuntimeError("falha sintética de commit")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(Session, "commit", commit_explode)
        try:
            resposta = await client.post("/lotes", json={"id": lote_id, "periodos_cobertos": ["2026.1"]})
        except RuntimeError:
            pass
        else:
            assert resposta.status_code >= 500

    assert not (config.RAIZ_LOTES / lote_id).exists()

    resposta = await client.post("/lotes", json={"id": lote_id, "periodos_cobertos": ["2026.1"]})
    assert resposta.status_code == 201, resposta.json()


async def test_listar_excecoes_ordenada_por_passo_matricula_periodo(client, lote, db_engine):
    SessionTeste = sessionmaker(bind=db_engine)
    with SessionTeste() as session:
        ing2 = Ingestao(lote_id=lote, passo=2)
        ing1 = Ingestao(lote_id=lote, passo=1)
        session.add_all([ing1, ing2])
        session.flush()
        session.add_all([
            Excecao(ingestao_id=ing2.id, matricula=100, periodo="2026.1", motivo="sem_academico"),
            Excecao(ingestao_id=ing1.id, matricula=200, periodo="2025.2", motivo="sem_periodo", detalhe="periodo: missing"),
            Excecao(ingestao_id=ing1.id, matricula=100, periodo="2026.1", motivo="matricula_invalida"),
        ])
        session.commit()

    resposta = await client.get(f"/lotes/{lote}/excecoes")
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert [(e["passo"], e["matricula"], e["periodo"]) for e in corpo] == [
        (1, 100, "2026.1"),
        (1, 200, "2025.2"),
        (2, 100, "2026.1"),
    ]
    assert corpo[1]["detalhe"] == "periodo: missing"
    assert corpo[1]["motivo"] == "sem_periodo"


async def test_listar_excecoes_de_lote_inexistente_da_404(client):
    assert (await client.get("/lotes/L99/excecoes")).status_code == 404


# ---------------------------------------------------------------------------
# POST /lotes/{id}/historicos: recebe PDFs (soltos ou em zip) para historicos/
# ---------------------------------------------------------------------------

def _pdf(nome: str, conteudo: bytes = b"%PDF-1.4 falso"):
    return ("arquivos", (nome, conteudo, "application/pdf"))


async def test_enviar_pdf_grava_em_historicos(client, lote):
    resposta = await client.post(f"/lotes/{lote}/historicos", files=[_pdf("700001.pdf")])
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert corpo["gravados"] == ["700001.pdf"]
    assert corpo["ja_existiam"] == []
    assert corpo["ignorados"] == []
    assert (config.RAIZ_LOTES / lote / "historicos" / "700001.pdf").read_bytes() == b"%PDF-1.4 falso"


def _zip(entradas: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nome, conteudo in entradas.items():
            z.writestr(nome, conteudo)
    return buffer.getvalue()


async def test_enviar_zip_extrai_so_pdfs_achatando_subpastas(client, lote):
    conteudo = _zip({
        "historicos/700001.pdf": b"pdf um",
        "historicos/sub/700002.PDF": b"pdf dois",
        "__MACOSX/._700001.pdf": b"lixo do mac",
        "historicos/Thumbs.db": b"lixo do windows",
        "leiame.txt": b"texto",
    })
    resposta = await client.post(
        f"/lotes/{lote}/historicos", files=[("arquivos", ("historicos.zip", conteudo, "application/zip"))]
    )
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    # .PDF vira .pdf: o passo 2 faz glob("*.pdf"), sensível a maiúsculas em Linux.
    assert corpo["gravados"] == ["700001.pdf", "700002.pdf"]
    assert sorted(corpo["ignorados"]) == ["__MACOSX/._700001.pdf", "historicos/Thumbs.db", "leiame.txt"]
    pasta = config.RAIZ_LOTES / lote / "historicos"
    assert sorted(p.name for p in pasta.iterdir()) == ["700001.pdf", "700002.pdf"]
    assert (pasta / "700002.pdf").read_bytes() == b"pdf dois"


async def test_reenviar_mesmo_pdf_e_idempotente(client, lote):
    await client.post(f"/lotes/{lote}/historicos", files=[_pdf("700001.pdf")])
    resposta = await client.post(f"/lotes/{lote}/historicos", files=[_pdf("700001.pdf"), _pdf("700002.pdf")])
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert corpo["gravados"] == ["700002.pdf"]
    assert corpo["ja_existiam"] == ["700001.pdf"]


async def test_mesmo_nome_com_conteudo_diferente_da_409_e_nao_sobrescreve(client, lote):
    await client.post(f"/lotes/{lote}/historicos", files=[_pdf("700001.pdf", b"original")])
    resposta = await client.post(f"/lotes/{lote}/historicos", files=[_pdf("700001.pdf", b"outro conteudo")])
    assert resposta.status_code == 409
    assert "700001.pdf" in resposta.json()["detail"]
    assert (config.RAIZ_LOTES / lote / "historicos" / "700001.pdf").read_bytes() == b"original"


async def test_enviar_depois_do_passo_2_da_409(client, lote, db_engine):
    SessionTeste = sessionmaker(bind=db_engine)
    with SessionTeste() as session:
        session.add(Ingestao(lote_id=lote, passo=Ingestao.PASSO_CRG))
        session.commit()
    resposta = await client.post(f"/lotes/{lote}/historicos", files=[_pdf("700001.pdf")])
    assert resposta.status_code == 409
    assert not (config.RAIZ_LOTES / lote / "historicos" / "700001.pdf").exists()


async def test_enviar_para_lote_inexistente_da_400(client):
    resposta = await client.post("/lotes/L99/historicos", files=[_pdf("700001.pdf")])
    assert resposta.status_code == 400


async def test_zip_acima_do_limite_descomprimido_da_413(client, lote, monkeypatch):
    from app.services import lotes as servico
    monkeypatch.setattr(servico, "LIMITE_BYTES_HISTORICOS", 100)
    conteudo = _zip({"700001.pdf": b"x" * 60, "700002.pdf": b"y" * 60})
    resposta = await client.post(
        f"/lotes/{lote}/historicos", files=[("arquivos", ("h.zip", conteudo, "application/zip"))]
    )
    assert resposta.status_code == 413
    assert list((config.RAIZ_LOTES / lote / "historicos").iterdir()) == []


async def test_zip_corrompido_da_400(client, lote):
    resposta = await client.post(
        f"/lotes/{lote}/historicos", files=[("arquivos", ("h.zip", b"isto nao e um zip", "application/zip"))]
    )
    assert resposta.status_code == 400
    assert "h.zip" in resposta.json()["detail"]


# ---------------------------------------------------------------------------
# POST /lotes/{id}/fechar: sela o lote (SHA256SUMS, lote.md, CSVs, fechado_em)
# ---------------------------------------------------------------------------

async def test_lote_novo_nasce_aberto(client, lote):
    corpo = (await client.get(f"/lotes/{lote}")).json()
    assert corpo["fechado_em"] is None


def _lote_rodado(db_engine, lote_id: str) -> None:
    """Estado de um lote depois de `rodar`: ingestões 1 e 2, alunos vigentes e
    exceções dos quatro casos de correspondência (100 completo, 200 sem
    acadêmico, 300 sem socioeconômico, 400 sem nenhum)."""
    SessionTeste = sessionmaker(bind=db_engine)
    with SessionTeste() as session:
        ing1 = Ingestao(lote_id=lote_id, passo=1, registros_lidos=10, registros_aceitos=9, registros_rejeitados=1)
        ing2 = Ingestao(lote_id=lote_id, passo=2, registros_lidos=5, registros_aceitos=4, registros_rejeitados=1)
        session.add_all([ing1, ing2])
        session.flush()
        session.add_all([
            Usuarios(matricula=100, periodo="2026.1", CRG=8.5, nome="Ana", ingestao_id=ing2.id),
            Usuarios(matricula=200, periodo="2026.1", CRG=None, nome="Beto", ingestao_id=ing1.id),
            Excecao(ingestao_id=ing2.id, matricula=200, periodo="2026.1", motivo="sem_academico"),
            Excecao(ingestao_id=ing2.id, matricula=300, motivo="sem_socioeconomico"),
            Excecao(ingestao_id=ing2.id, matricula=400, periodo="2026.1", motivo="sem_academico"),
            Excecao(ingestao_id=ing2.id, matricula=400, motivo="sem_socioeconomico"),
        ])
        session.commit()
    raiz = config.RAIZ_LOTES / lote_id
    (raiz / "historicos" / "700001.pdf").write_bytes(b"pdf falso")
    (raiz / "fasitech.json").write_text('{"ok": true}', encoding="utf-8")


async def test_fechar_sem_os_dois_passos_da_409(client, lote):
    assert (await client.post(f"/lotes/{lote}/fechar")).status_code == 409


async def test_fechar_gera_sha256sums_verificavel_e_marca_fechado_em(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    resposta = await client.post(f"/lotes/{lote}/fechar")
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert corpo["fechado_em"] is not None
    assert (await client.get(f"/lotes/{lote}")).json()["fechado_em"] == corpo["fechado_em"]

    raiz = config.RAIZ_LOTES / lote
    linhas = (raiz / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2
    for linha in linhas:
        hash_esperado, caminho = linha.split("  ", 1)
        assert hashlib.sha256((raiz / caminho).read_bytes()).hexdigest() == hash_esperado


async def test_fechar_gera_lote_md_com_contadores(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    await client.post(f"/lotes/{lote}/fechar")
    conteudo = (config.RAIZ_LOTES / lote / "lote.md").read_text(encoding="utf-8")
    assert f"# Lote {lote}" in conteudo
    assert "| 1 | " in conteudo and "| 10 | 9 | 1 |" in conteudo
    assert "| 2 | " in conteudo and "| 5 | 4 | 1 |" in conteudo
    assert "| sem_academico | 2 |" in conteudo
    assert "| sem_socioeconomico | 2 |" in conteudo
    assert "historicos/700001.pdf" in conteudo
    assert "## Limitações" in conteudo


async def test_fechar_gera_vigente_csv_com_colunas_de_alunoout(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    await client.post(f"/lotes/{lote}/fechar")
    caminho = config.RAIZ_PROCESSADA / lote / "vigente.csv"
    with open(caminho, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        assert leitor.fieldnames == list(AlunoOut.model_fields)
        linhas = list(leitor)
    assert [l["matricula"] for l in linhas] == ["100", "200"]
    assert linhas[0]["CRG"] == "8.5"


async def test_fechar_gera_correspondencia_com_os_quatro_casos(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    await client.post(f"/lotes/{lote}/fechar")
    caminho = config.RAIZ_PROCESSADA / lote / "correspondencia.csv"
    with open(caminho, newline="", encoding="utf-8") as f:
        linhas = {l["Matricula"]: l for l in csv.DictReader(f)}
    assert (linhas["100"]["Academico"], linhas["100"]["SocioEconomico"], linhas["100"]["Dado_Faltando"]) == ("Sim", "Sim", "")
    assert (linhas["200"]["Academico"], linhas["200"]["SocioEconomico"], linhas["200"]["Dado_Faltando"]) == ("Não", "Sim", "Academico")
    assert (linhas["300"]["Academico"], linhas["300"]["SocioEconomico"], linhas["300"]["Dado_Faltando"]) == ("Sim", "Não", "SocioEconomico")
    assert (linhas["400"]["Academico"], linhas["400"]["SocioEconomico"], linhas["400"]["Dado_Faltando"]) == ("Não", "Não", "Ambos")
    assert linhas["100"]["Nome"] == "Ana"


async def test_fechar_devolve_os_caminhos_gerados(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    corpo = (await client.post(f"/lotes/{lote}/fechar")).json()
    assert corpo["arquivos_gerados"] == [
        str(config.RAIZ_LOTES / lote / "SHA256SUMS"),
        str(config.RAIZ_LOTES / lote / "lote.md"),
        str(config.RAIZ_PROCESSADA / lote / "vigente.csv"),
        str(config.RAIZ_PROCESSADA / lote / "correspondencia.csv"),
    ]


async def test_fechar_duas_vezes_da_409(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    await client.post(f"/lotes/{lote}/fechar")
    assert (await client.post(f"/lotes/{lote}/fechar")).status_code == 409


async def test_fechar_lote_inexistente_da_404(client):
    assert (await client.post("/lotes/L99/fechar")).status_code == 404


async def test_enviar_historicos_em_lote_fechado_da_409(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    await client.post(f"/lotes/{lote}/fechar")
    resposta = await client.post(f"/lotes/{lote}/historicos", files=[_pdf("700009.pdf")])
    assert resposta.status_code == 409
    assert not (config.RAIZ_LOTES / lote / "historicos" / "700009.pdf").exists()


# ---------------------------------------------------------------------------
# POST /lotes/{id}/historicos?executar=true: grava e roda os passos 1 e 2
# ---------------------------------------------------------------------------

def _envelope(*registros):
    return {"url": "http://fasitech", "params": {}, "coletado_em": "2026-09-12T00:00:00+00:00",
            "paginas": [{"dados": list(registros), "pagina": 1, "total_paginas": 1}]}


def _falsificar_fontes(monkeypatch, matricula: int):
    from datetime import date
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", lambda: _envelope({"matricula": matricula, "periodo": "2026.1"}))
    monkeypatch.setattr(rotas_alunos, "carregar_historico", lambda caminho: {
        "matricula": matricula, "nome": "ALUNO TESTE", "data_de_nascimento": "01/01/2000",
        "emitido_em": date(2025, 12, 10), "crg_por_semestre": {"2025.1": 7.0, "2025.2": 8.0},
    })


async def test_enviar_com_executar_grava_e_roda_os_dois_passos(client, lote, monkeypatch):
    _falsificar_fontes(monkeypatch, 700001)
    resposta = await client.post(f"/lotes/{lote}/historicos?executar=true", files=[_pdf("700001.pdf")])
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert corpo["gravados"] == ["700001.pdf"]
    assert corpo["sincronizar"]["importados"] == 1
    assert corpo["atualizar_crg"]["pdfs_lidos"] == 1
    assert corpo["atualizar_crg"]["alunos_atualizados"] == 1
    detalhe = (await client.get(f"/lotes/{lote}")).json()
    assert [i["passo"] for i in detalhe["ingestoes"]] == [1, 2]
    assert (await client.get("/alunos/700001")).json()["CRG"] == 8.0


async def test_enviar_sem_executar_nao_roda_nada(client, lote):
    corpo = (await client.post(f"/lotes/{lote}/historicos", files=[_pdf("700001.pdf")])).json()
    assert corpo["sincronizar"] is None
    assert corpo["atualizar_crg"] is None
    assert (await client.get(f"/lotes/{lote}")).json()["ingestoes"] == []


async def test_enviar_com_executar_pula_passo_1_ja_feito(client, lote, monkeypatch):
    _falsificar_fontes(monkeypatch, 700001)
    await client.post(f"/alunos/sincronizar?lote={lote}")

    def nao_deveria():
        raise AssertionError("passo 1 já rodou; não deveria buscar o FasiTech de novo")
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", nao_deveria)

    corpo = (await client.post(f"/lotes/{lote}/historicos?executar=true", files=[_pdf("700001.pdf")])).json()
    assert corpo["sincronizar"] == "ja_executado"
    assert corpo["atualizar_crg"]["pdfs_lidos"] == 1


async def test_enviar_com_executar_mantem_pdfs_se_fasitech_falhar(client, lote, monkeypatch):
    def fora_do_ar():
        raise httpx.ConnectError("FasiTech fora do ar")
    monkeypatch.setattr(rotas_alunos, "buscar_paginas", fora_do_ar)

    resposta = await client.post(f"/lotes/{lote}/historicos?executar=true", files=[_pdf("700001.pdf")])
    assert resposta.status_code == 502  # o mesmo que /alunos/sincronizar devolve
    assert (config.RAIZ_LOTES / lote / "historicos" / "700001.pdf").exists()
    assert (await client.get(f"/lotes/{lote}")).json()["ingestoes"] == []


# ---------------------------------------------------------------------------
# GET /lotes/{id}/correspondencia: a correspondencia.csv como JSON
# ---------------------------------------------------------------------------

async def test_correspondencia_devolve_os_quatro_casos_ordenados(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    resposta = await client.get(f"/lotes/{lote}/correspondencia")
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert [l["matricula"] for l in corpo] == [100, 200, 300, 400]
    assert corpo[0] == {"matricula": 100, "nome": "Ana", "academico": True, "socioeconomico": True, "faltando": ""}
    assert (corpo[1]["academico"], corpo[1]["socioeconomico"], corpo[1]["faltando"]) == (False, True, "Academico")
    assert (corpo[2]["academico"], corpo[2]["socioeconomico"], corpo[2]["faltando"]) == (True, False, "SocioEconomico")
    assert (corpo[3]["academico"], corpo[3]["socioeconomico"], corpo[3]["faltando"]) == (False, False, "Ambos")


async def test_correspondencia_de_lote_inexistente_da_404(client):
    assert (await client.get("/lotes/L99/correspondencia")).status_code == 404
