from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
import pytest

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


def test_exigir_lote_inexistente_da_400(sessao):
    assert lotes.exigir_lote(sessao, "L01").id == "L01"
    with pytest.raises(HTTPException) as erro:
        lotes.exigir_lote(sessao, "L99")
    assert erro.value.status_code == 400


def test_abrir_e_fechar_ingestao(sessao):
    ingestao = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_SINCRONIZAR)
    lotes.fechar_ingestao(sessao, ingestao, lidos=3, aceitos=2, rejeitados=1)
    gravada = sessao.get(Ingestao, ingestao.id)
    assert (gravada.registros_lidos, gravada.registros_aceitos, gravada.registros_rejeitados) == (3, 2, 1)


def test_abrir_ingestao_manual_reaproveita(sessao):
    a = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_MANUAL)
    b = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_MANUAL)
    assert a.id == b.id


def test_abrir_ingestao_repetida_do_mesmo_passo_da_409(sessao):
    lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    with pytest.raises(HTTPException) as erro:
        lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    assert erro.value.status_code == 409


def test_exigir_passo_livre(sessao):
    assert lotes.exigir_passo_livre(sessao, "L01", Ingestao.PASSO_CRG) is None
    lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    with pytest.raises(HTTPException) as erro:
        lotes.exigir_passo_livre(sessao, "L01", Ingestao.PASSO_CRG)
    assert erro.value.status_code == 409


def test_registrar_excecao(sessao):
    ingestao = lotes.abrir_ingestao(sessao, "L01", Ingestao.PASSO_CRG)
    lotes.registrar_excecao(sessao, ingestao, "sem_academico", matricula=123, periodo="2026.1")
    sessao.commit()
    excecoes = sessao.execute(select(Excecao)).scalars().all()
    assert [(e.motivo, e.matricula, e.periodo) for e in excecoes] == [("sem_academico", 123, "2026.1")]
