"""Lote fechado é imutável no BANCO (revisão c5e8a1f3d920), não só na API.

A API já não tem rota que altere lote. Estes testes vão por SQL direto --
o caminho de quem tentasse contornar a API -- e provam que os triggers
recusam: reabrir, editar ou apagar o lote; acrescentar ingestão, arquivo ou
exceção; editar ou apagar qualquer linha gravada por ele.
"""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.engine import ArquivoFonte, CrgSemestre, Excecao, Historico, Ingestao, Lote, Usuarios
from conftest import historico, zip_de


@pytest.fixture()
async def fechado(importar, fontes) -> dict:
    fontes.fasitech = [{"matricula": 1, "periodo": "2026.1", "renda": "A"}]
    fontes.historicos = {"h1": historico(1, {"2025.1": 7.0})}
    corpo = (await importar(zip_de(["h1.pdf"]))).json()
    assert corpo["fechado_em"] is not None
    return corpo


def _recusa(db_engine, instrucao) -> None:
    with Session(db_engine) as s:
        with pytest.raises(DBAPIError, match="está fechado"):
            s.execute(instrucao)
            s.flush()


def _ingestao_id(corpo: dict, passo: int) -> int:
    return next(i["id"] for i in corpo["ingestoes"] if i["passo"] == passo)


async def test_lote_fechado_nao_reabre_nem_muda_nem_some(fechado, db_engine):
    lote_id = fechado["id"]
    _recusa(db_engine, update(Lote).where(Lote.id == lote_id).values(fechado_em=None))
    _recusa(db_engine, update(Lote).where(Lote.id == lote_id).values(periodos_cobertos="2030.1"))
    _recusa(db_engine, update(Lote).where(Lote.id == lote_id).values(executado_por="Outra pessoa"))
    _recusa(db_engine, delete(Lote).where(Lote.id == lote_id))


async def test_lote_fechado_nao_recebe_ingestao_nem_arquivo(fechado, db_engine):
    lote_id = fechado["id"]
    _recusa(db_engine, Ingestao.__table__.insert().values(lote_id=lote_id, passo=3,
                                                            executado_em=datetime.now(timezone.utc),
                                                            registros_lidos=0, registros_aceitos=0, registros_rejeitados=0))
    _recusa(db_engine, ArquivoFonte.__table__.insert().values(sha256="f" * 64, lote_id=lote_id, nome_original="x.pdf",
                                                                tipo="pdf_historico", tamanho_bytes=1))


async def test_linhas_do_lote_fechado_nao_se_editam_nem_se_apagam(fechado, db_engine):
    passo1, passo2 = _ingestao_id(fechado, 1), _ingestao_id(fechado, 2)
    _recusa(db_engine, update(Usuarios).where(Usuarios.ingestao_id == passo1).values(renda="B"))
    _recusa(db_engine, delete(Usuarios).where(Usuarios.ingestao_id == passo2))
    _recusa(db_engine, update(CrgSemestre).where(CrgSemestre.ingestao_id == passo2).values(crg=10.0))
    _recusa(db_engine, update(Historico).where(Historico.ingestao_id == passo2).values(periodo="2030.1"))
    _recusa(db_engine, delete(Ingestao).where(Ingestao.id == passo1))
    _recusa(db_engine, Usuarios.__table__.insert().values(matricula=99, periodo="2026.1", ingestao_id=passo1))
    _recusa(db_engine, Excecao.__table__.insert().values(ingestao_id=passo2, motivo="sem_academico", matricula=99))
    _recusa(db_engine, CrgSemestre.__table__.insert().values(matricula=99, semestre="2025.1", crg=1.0, ingestao_id=passo2))
    _recusa(db_engine, Historico.__table__.insert().values(ingestao_id=passo2, matricula=99, emitido_em=date(2025, 12, 10), periodo="2025.2"))


async def test_lote_aberto_ainda_aceita_escrita_e_pode_ser_fechado(lote, db_engine):
    """Os triggers só mordem lote fechado: a importação grava tudo com o lote
    aberto e o fecha no fim da mesma transação."""
    with Session(db_engine) as s:
        s.add(Ingestao(lote_id=lote, passo=1))
        s.execute(update(Lote).where(Lote.id == lote).values(fechado_em=datetime.now(timezone.utc)))
        s.commit()
    _recusa(db_engine, update(Lote).where(Lote.id == lote).values(fechado_em=None))


async def test_triggers_existem_no_banco(db_engine):
    with db_engine.connect() as conexao:
        nomes = set(conexao.execute(text(
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
        )).scalars())
    assert {"lote_imutavel", "ingestao_lote_fechado", "arquivo_fonte_lote_fechado", "usuarios_lote_fechado",
            "crg_semestre_lote_fechado", "excecao_lote_fechado", "historico_lote_fechado"} <= nomes
