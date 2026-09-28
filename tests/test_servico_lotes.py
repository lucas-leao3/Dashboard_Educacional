from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.core import config
from app.db.engine import ArquivoFonte, Excecao, Ingestao, Lote
from app.services import lotes


@pytest.fixture()
def sessao(tmp_path, monkeypatch, db_engine):
    """Sessão num PostgreSQL descartável e migrado (fixture `db_engine`)."""
    monkeypatch.setattr(config, "RAIZ_LOTES", tmp_path / "lotes")
    with Session(db_engine) as s:
        s.add(Lote(id="L01", periodos_cobertos="2026.1"))
        s.commit()
        yield s


def test_criar_diretorio_cria_historicos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ_LOTES", tmp_path / "lotes")
    caminho = lotes.criar_diretorio("2026-09-L01")
    assert caminho == tmp_path / "lotes" / "2026-09-L01"
    assert (caminho / "historicos").is_dir()
    with pytest.raises(FileExistsError):
        lotes.criar_diretorio("2026-09-L01")


def test_registrar_arquivo_grava_hash_e_detecta_duplicado(sessao, tmp_path):
    arquivo = tmp_path / "a.pdf"
    arquivo.write_bytes(b"conteudo")
    registro = lotes.registrar_arquivo(sessao, "L01", arquivo, "pdf_historico")
    assert registro.sha256 == lotes.sha256_de(arquivo)
    assert registro.tamanho_bytes == 8
    assert registro.nome_original == "a.pdf"
    assert lotes.registrar_arquivo(sessao, "L01", arquivo, "pdf_historico") is None


def test_abrir_e_fechar_ingestao(sessao):
    ingestao = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_SINCRONIZAR)
    lotes.fechar_ingestao(sessao, ingestao, lidos=3, aceitos=2, rejeitados=1)
    gravada = sessao.get(Ingestao, ingestao.id)
    assert (gravada.registros_lidos, gravada.registros_aceitos, gravada.registros_rejeitados) == (3, 2, 1)


def test_abrir_ingestao_repetida_do_mesmo_passo_e_recusada_pelo_banco(sessao):
    lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    with pytest.raises(IntegrityError):
        lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)


def test_proximo_id_segue_a_sequencia_do_mes(sessao):
    assert lotes.proximo_id(sessao, date(2026, 10, 3)) == "2026-10-L01"
    sessao.add(Lote(id="2026-10-L01", periodos_cobertos="2026.2"))
    sessao.add(Lote(id="2026-10-L02", periodos_cobertos="2026.2"))
    sessao.add(Lote(id="2026-11-L05", periodos_cobertos="2026.2"))
    sessao.commit()
    assert lotes.proximo_id(sessao, date(2026, 10, 30)) == "2026-10-L03"
    assert lotes.proximo_id(sessao, date(2026, 11, 1)) == "2026-11-L06"


def test_proximo_id_considera_pasta_orfa_em_disco(sessao):
    (config.RAIZ_LOTES / "2026-10-L04").mkdir(parents=True)
    assert lotes.proximo_id(sessao, date(2026, 10, 3)) == "2026-10-L05"


def test_registrar_excecao(sessao):
    ingestao = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    lotes.registrar_excecao(sessao, ingestao, "sem_academico", matricula=123, periodo="2026.1")
    sessao.commit()
    excecoes = sessao.execute(select(Excecao)).scalars().all()
    assert [(e.motivo, e.matricula, e.periodo) for e in excecoes] == [("sem_academico", 123, "2026.1")]
