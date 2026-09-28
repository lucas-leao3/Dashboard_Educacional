"""POST /lotes/importar: responsável + .zip -> lote processado e fechado.

As fontes externas vêm falsificadas pelo fixture `fontes` (tests/conftest.py):
o FasiTech devolve `fontes.fasitech` e cada PDF do zip é "lido" como
`fontes.historicos[<nome sem .pdf>]`.
"""
import hashlib
import re
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.db.engine import ArquivoFonte, CrgSemestre, Excecao, Historico, Ingestao, Lote, Usuarios
from conftest import historico, zip_de


def _estado_vazio(db_engine) -> bool:
    """Nenhuma linha em nenhuma tabela de dados e nenhuma pasta de lote."""
    with Session(db_engine) as s:
        for modelo in (Lote, Ingestao, ArquivoFonte, Usuarios, CrgSemestre, Excecao, Historico):
            if s.execute(select(modelo)).first() is not None:
                return False
    raiz = config.RAIZ_LOTES
    return not raiz.exists() or not any(raiz.iterdir())


def _cenario_basico(fontes):
    """700001 completo, 700002 só socioeconômico, 700003 só histórico."""
    fontes.fasitech = [
        {"matricula": 700001, "periodo": "2025.(3 e 4)", "genero": "Feminino"},
        {"matricula": 700002, "periodo": "2025.(3 e 4)", "genero": "Masculino"},
    ]
    fontes.historicos = {
        "historico_700001": historico(700001, {"2024.2": 6.0, "2025.1": 7.5, "2025.2": None}),
        "historico_700003": historico(700003, {"2025.1": 8.0}),
    }
    return zip_de(["historico_700001.pdf", "historico_700003.pdf"])


# ---------------------------------------------------------------------------
# Entrada: só responsável e .zip
# ---------------------------------------------------------------------------

async def test_importar_cria_processa_e_fecha_o_lote(importar, fontes, client):
    resposta = await importar(_cenario_basico(fontes))
    assert resposta.status_code == 201, resposta.json()
    corpo = resposta.json()

    assert re.fullmatch(r"\d{4}-\d{2}-L01", corpo["id"])
    assert corpo["executado_por"] == "Edinaldo"
    assert corpo["fechado_em"] is not None
    assert [i["passo"] for i in corpo["ingestoes"]] == [1, 2]
    assert corpo["arquivos"]["gravados"] == ["historico_700001.pdf", "historico_700003.pdf"]
    assert corpo["sincronizar"]["importados"] == 2
    assert corpo["atualizar_crg"]["pdfs_lidos"] == 2
    assert corpo["resumo"]["integrados"] == 1
    assert corpo["resumo"]["por_motivo"] == {"sem_academico": 1, "sem_socioeconomico": 1}

    lote = (await client.get(f"/lotes/{corpo['id']}")).json()
    assert lote["fechado_em"] == corpo["fechado_em"]


async def test_periodo_e_extraido_da_data_de_emissao_dos_historicos(importar, fontes, db_engine):
    """O usuário não informa período: ele sai de 'Emitido em' de cada PDF."""
    fontes.fasitech = [{"matricula": 1, "periodo": "2026.(1 e 2)"}]
    fontes.historicos = {
        "a": historico(1, {"2025.1": 7.0}, emitido_em=date(2025, 12, 10)),   # 2025.2
        "b": historico(2, {"2025.1": 7.0}, emitido_em=date(2026, 3, 2)),     # 2026.1
        "c": historico(3, {"2025.1": 7.0}, emitido_em=date(2026, 5, 30)),    # 2026.1
    }
    corpo = (await importar(zip_de(["a.pdf", "b.pdf", "c.pdf"]))).json()
    assert corpo["periodos_cobertos"] == ["2025.2", "2026.1"]

    with Session(db_engine) as s:
        registrados = {h.matricula: (h.emitido_em, h.periodo) for h in s.execute(select(Historico)).scalars()}
    assert registrados == {
        1: (date(2025, 12, 10), "2025.2"), 2: (date(2026, 3, 2), "2026.1"), 3: (date(2026, 5, 30), "2026.1"),
    }


async def test_importar_sem_responsavel_da_422_e_nao_grava_nada(importar, fontes, db_engine):
    assert (await importar(_cenario_basico(fontes), responsavel=None)).status_code == 422
    assert (await importar(_cenario_basico(fontes), responsavel="   ")).status_code == 422
    assert _estado_vazio(db_engine)


async def test_importar_arquivo_que_nao_e_zip_da_400(importar, fontes, db_engine):
    resposta = await importar(b"%PDF-1.4", nome="historico_700001.pdf")
    assert resposta.status_code == 400
    assert ".zip" in resposta.json()["detail"]
    assert _estado_vazio(db_engine)


async def test_importar_zip_sem_pdf_da_400_e_nao_grava_nada(importar, fontes, db_engine):
    resposta = await importar(zip_de({"leiame.txt": b"oi", "__MACOSX/._a.pdf": b"lixo"}))
    assert resposta.status_code == 400
    assert _estado_vazio(db_engine)


async def test_importar_zip_corrompido_da_400(importar, fontes, db_engine):
    resposta = await importar(b"isto nao e um zip")
    assert resposta.status_code == 400
    assert _estado_vazio(db_engine)


async def test_zip_acima_do_limite_descomprimido_da_413(importar, fontes, db_engine, monkeypatch):
    from app.services import lotes as servico
    monkeypatch.setattr(servico, "LIMITE_BYTES_HISTORICOS", 100)
    resposta = await importar(zip_de({"a.pdf": b"x" * 60, "b.pdf": b"y" * 60}))
    assert resposta.status_code == 413
    assert _estado_vazio(db_engine)


async def test_zip_achata_subpastas_e_ignora_o_que_nao_e_pdf(importar, fontes):
    fontes.fasitech = [{"matricula": 1, "periodo": "2026.(1 e 2)"}]
    fontes.historicos = {"a": historico(1, {"2025.1": 7.0}), "B": historico(2, {"2025.1": 7.0})}
    corpo = (await importar(zip_de({"turma/a.pdf": b"a", "outra/B.PDF": b"b", "leiame.txt": b"x"}))).json()
    # Só a extensão é normalizada (o passo 2 faz glob("*.pdf"), sensível a caixa).
    assert sorted(corpo["arquivos"]["gravados"]) == ["B.pdf", "a.pdf"]
    assert corpo["arquivos"]["ignorados"] == ["leiame.txt"]
    assert (config.RAIZ_LOTES / corpo["id"] / "historicos" / "B.pdf").exists()


async def test_mesmo_nome_com_conteudo_diferente_no_zip_da_409(importar, fontes, db_engine):
    """Antes, o segundo sobrescrevia o primeiro sem aviso."""
    resposta = await importar(zip_de({"x/a.pdf": b"um", "y/a.pdf": b"outro"}))
    assert resposta.status_code == 409
    assert "a.pdf" in resposta.json()["detail"]
    assert _estado_vazio(db_engine)


# ---------------------------------------------------------------------------
# Atomicidade: ou lote fechado, ou nada
# ---------------------------------------------------------------------------

async def test_fasitech_fora_do_ar_da_502_e_desfaz_tudo(importar, fontes, db_engine):
    _cenario_basico(fontes)
    fontes.erro_fasitech = httpx.ConnectError("FasiTech fora do ar")
    resposta = await importar(zip_de(["historico_700001.pdf"]))
    assert resposta.status_code == 502
    assert _estado_vazio(db_engine)


async def test_fasitech_sem_configuracao_da_503(importar, fontes, db_engine):
    _cenario_basico(fontes)
    fontes.erro_fasitech = RuntimeError("FASITECH_URL não configurada")
    assert (await importar(zip_de(["historico_700001.pdf"]))).status_code == 503
    assert _estado_vazio(db_engine)


async def test_fasitech_formato_inesperado_da_502(importar, fontes, db_engine, monkeypatch):
    """Regressão de um bug real: a rota /dashboard do FasiTech devolve um
    objeto sem 'dados'; sem checagem a API quebrava com 500."""
    from app.services import importacao
    _cenario_basico(fontes)
    monkeypatch.setattr(importacao, "buscar_paginas", lambda: {"paginas": [{"total": 165, "pagina": 1}]})
    assert (await importar(zip_de(["historico_700001.pdf"]))).status_code == 502
    assert _estado_vazio(db_engine)


async def test_nenhum_historico_legivel_da_422_porque_nao_ha_periodo(importar, fontes, db_engine):
    fontes.fasitech = [{"matricula": 1, "periodo": "2026.(1 e 2)"}]
    fontes.historicos = {"a": ValueError("Histórico sem data de emissão ou matrícula")}
    resposta = await importar(zip_de(["a.pdf"]))
    assert resposta.status_code == 422
    assert "período" in resposta.json()["detail"]
    assert _estado_vazio(db_engine)


# ---------------------------------------------------------------------------
# Lote fechado: nova importação é lote novo; o anterior fica como estava
# ---------------------------------------------------------------------------

async def test_segunda_importacao_cria_lote_novo_e_preserva_o_anterior(importar, fontes, client):
    primeiro = (await importar(_cenario_basico(fontes))).json()
    raiz = config.RAIZ_LOTES / primeiro["id"]
    lote_md_antes = (raiz / "lote.md").read_bytes()
    relatorio_antes = (await client.get(f"/lotes/{primeiro['id']}/relatorio")).json()

    fontes.fasitech.append({"matricula": 700003, "periodo": "2026.(1 e 2)"})
    fontes.historicos["historico_700002"] = historico(700002, {"2025.1": 5.0})
    segundo = (await importar(zip_de(["historico_700002.pdf"]))).json()

    assert segundo["id"].endswith("-L02")
    assert (await client.get(f"/lotes/{primeiro['id']}")).json()["fechado_em"] == primeiro["fechado_em"]
    assert (raiz / "lote.md").read_bytes() == lote_md_antes
    assert (await client.get(f"/lotes/{primeiro['id']}/relatorio")).json() == relatorio_antes
    assert [l["id"] for l in (await client.get("/lotes")).json()] == [primeiro["id"], segundo["id"]]


async def test_rotas_de_edicao_de_lote_nao_existem_mais(client, lote):
    """Abrir, enviar arquivo, rodar passo e fechar à parte deixaram de existir:
    a única escrita é POST /lotes/importar."""
    tentativas = [
        client.post("/lotes", json={"id": "2026-09-L09", "periodos_cobertos": ["2026.1"]}),
        client.post(f"/lotes/{lote}/historicos", files={"arquivos": ("a.pdf", b"x")}),
        client.post(f"/lotes/{lote}/fechar"),
        client.post(f"/alunos?lote={lote}", json={"matricula": 1, "periodo": "2026.1"}),
        client.post(f"/alunos/sincronizar?lote={lote}"),
        client.post(f"/alunos/atualizar-crg?lote={lote}"),
        client.put(f"/lotes/{lote}", json={}),
        client.delete(f"/lotes/{lote}"),
    ]
    for tentativa in tentativas:
        assert (await tentativa).status_code in (404, 405)


async def test_id_do_lote_pula_pasta_orfa_no_disco(importar, fontes):
    primeiro = (await importar(_cenario_basico(fontes))).json()
    prefixo = primeiro["id"][:-2]
    (config.RAIZ_LOTES / f"{prefixo}07").mkdir()
    fontes.historicos["historico_700002"] = historico(700002, {"2025.1": 5.0})
    segundo = (await importar(zip_de(["historico_700002.pdf"]))).json()
    assert segundo["id"] == f"{prefixo}08"


# ---------------------------------------------------------------------------
# Passo 1 (FasiTech) dentro da importação
# ---------------------------------------------------------------------------

async def test_fasitech_congelado_em_json_com_hash_na_ingestao(importar, fontes):
    corpo = (await importar(_cenario_basico(fontes))).json()
    congelado = config.RAIZ_LOTES / corpo["id"] / "fasitech.json"
    assert "700001" in congelado.read_text(encoding="utf-8")
    passo1 = corpo["ingestoes"][0]
    assert passo1["arquivo_sha256"] == hashlib.sha256(congelado.read_bytes()).hexdigest()


async def test_registros_invalidos_do_fasitech_viram_excecao(importar, fontes):
    fontes.fasitech = [
        {"matricula": 900001, "periodo": "2026.1"},
        {"periodo": "2026.1"},       # sem matrícula
        {"matricula": 900003},       # sem período
    ]
    fontes.historicos = {"h": historico(900001, {"2025.1": 7.0})}
    corpo = (await importar(zip_de(["h.pdf"]))).json()
    assert (corpo["sincronizar"]["importados"], corpo["sincronizar"]["rejeitados"]) == (1, 2)
    assert corpo["excecoes_por_motivo"]["matricula_invalida"] == 1
    assert corpo["excecoes_por_motivo"]["sem_periodo"] == 1
    assert corpo["ingestoes"][0]["registros_lidos"] == 3


async def test_excecao_do_fasitech_nao_guarda_dado_pessoal(importar, fontes, db_engine):
    """LGPD: o detalhe da exceção não pode carregar o valor submetido -- só
    o nome do campo e o tipo do erro (docs/governanca_dados.md)."""
    fontes.fasitech = [{"matricula": "nao-numero", "periodo": "2026.1", "nome": "MARCADOR_SENSIVEL"}]
    fontes.historicos = {"h": historico(1, {"2025.1": 7.0})}
    assert (await importar(zip_de(["h.pdf"]))).status_code == 201
    with Session(db_engine) as s:
        detalhes = [e.detalhe or "" for e in s.execute(select(Excecao).where(Excecao.motivo == "matricula_invalida")).scalars()]
    assert len(detalhes) == 1
    assert "nao-numero" not in detalhes[0]
    assert "MARCADOR_SENSIVEL" not in detalhes[0]
    assert "input_value" not in detalhes[0]


async def test_correcao_na_fonte_chega_no_lote_seguinte(importar, fontes, client):
    """Correção na fonte vira linha nova no lote seguinte; a leitura passa a
    mostrar o valor novo e o antigo continua no banco."""
    fontes.fasitech = [{"matricula": 3, "periodo": "2026.1", "renda": "A"}]
    fontes.historicos = {"h3": historico(3, {"2025.1": 7.0})}
    await importar(zip_de(["h3.pdf"]))
    fontes.fasitech = [{"matricula": 3, "periodo": "2026.1", "renda": "B"}]
    await importar(zip_de({"h3.pdf": b"outro pdf do mesmo aluno"}))
    assert (await client.get("/alunos/3")).json()["renda"] == "B"


# ---------------------------------------------------------------------------
# Passo 2 (históricos) dentro da importação
# ---------------------------------------------------------------------------

async def test_historico_grava_semestres_e_atualiza_o_vigente(importar, fontes, client):
    fontes.fasitech = [{"matricula": 700001, "periodo": "2026.1", "renda": "A"}]
    fontes.historicos = {"h": historico(700001, {"2024.2": 6.0, "2025.1": 7.5, "2025.2": None})}
    corpo = (await importar(zip_de(["h.pdf"]))).json()
    assert corpo["atualizar_crg"]["semestres_gravados"] == 3
    assert corpo["atualizar_crg"]["alunos_atualizados"] == 1

    aluno = (await client.get("/alunos/700001")).json()
    assert aluno["CRG"] == 7.5               # último semestre apurado
    assert aluno["nome"] == "ALUNO TESTE"
    assert aluno["renda"] == "A"             # linha nova copia o vigente


async def test_historico_atualiza_todos_os_periodos_da_matricula(importar, fontes, client):
    fontes.fasitech = [{"matricula": 700004, "periodo": "2025.2"}, {"matricula": 700004, "periodo": "2026.1"}]
    fontes.historicos = {"h": historico(700004, {"2025.1": 6.5})}
    corpo = (await importar(zip_de(["h.pdf"]))).json()
    assert corpo["atualizar_crg"]["alunos_atualizados"] == 2
    assert [a["CRG"] for a in (await client.get("/alunos")).json()] == [6.5, 6.5]


async def test_historico_sem_socioeconomico_guarda_semestres_e_vira_excecao(importar, fontes):
    fontes.fasitech = [{"matricula": 1, "periodo": "2026.1"}]
    fontes.historicos = {"h1": historico(1, {"2025.1": 7.0}), "h3": historico(700003, {"2025.1": 8.0})}
    corpo = (await importar(zip_de(["h1.pdf", "h3.pdf"]))).json()
    assert corpo["atualizar_crg"]["sem_socioeconomico"] == 1
    assert corpo["atualizar_crg"]["semestres_gravados"] == 2
    assert corpo["excecoes_por_motivo"]["sem_socioeconomico"] == 1


async def test_mesmo_pdf_em_lote_novo_e_duplicado_mas_conta_a_matricula(importar, fontes):
    fontes.fasitech = [{"matricula": 700005, "periodo": "2026.1"}]
    fontes.historicos = {"h": historico(700005, {"2025.1": 9.0})}
    await importar(zip_de(["h.pdf"]))
    corpo = (await importar(zip_de(["h.pdf"]))).json()   # mesmo conteúdo -> mesmo hash
    assert corpo["atualizar_crg"]["duplicados"] == 1
    assert corpo["atualizar_crg"]["semestres_gravados"] == 0
    assert corpo["atualizar_crg"]["sem_academico"] == 0
    assert corpo["periodos_cobertos"] == ["2025.2"]
    assert corpo["resumo"]["integrados"] == 1


async def test_pdf_ilegivel_vira_falha_de_identificacao_e_conta_como_rejeitado(importar, fontes):
    """PDF que quebra em carregar_historico não pode sumir dos contadores:
    registros_lidos tem que bater com aceitos + rejeitados."""
    fontes.fasitech = [{"matricula": 1, "periodo": "2026.1"}]
    fontes.historicos = {"bom": historico(1, {"2025.1": 7.0}), "ruim": ValueError("Histórico sem matrícula")}
    corpo = (await importar(zip_de(["bom.pdf", "ruim.pdf"]))).json()
    assert corpo["atualizar_crg"]["ilegiveis"] == 1
    assert corpo["excecoes_por_motivo"]["falha_identificacao"] == 1
    passo2 = corpo["ingestoes"][1]
    assert (passo2["registros_lidos"], passo2["registros_aceitos"], passo2["registros_rejeitados"]) == (2, 1, 1)
