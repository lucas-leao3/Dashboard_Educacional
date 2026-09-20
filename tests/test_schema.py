"""A view aluno_vigente resolve, por (matricula, periodo), a linha da
ingestão mais recente -- é ela que o dashboard lê (governança, seção 4.5)."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.db.engine import CrgSemestre, Ingestao, Lote, Usuarios, criar_schema
from app.db.vigente import aluno_vigente


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.sqlite'}")
    criar_schema(engine)
    return engine


def test_criar_schema_cria_tabelas_e_view(tmp_path):
    engine = _engine(tmp_path)
    inspector = inspect(engine)
    assert {"lote", "arquivo_fonte", "ingestao", "excecao", "crg_semestre", "usuarios"} <= set(inspector.get_table_names())
    assert "aluno_vigente" in inspector.get_view_names()


def test_criar_schema_e_idempotente(tmp_path):
    engine = _engine(tmp_path)
    criar_schema(engine)  # segunda chamada não pode falhar por view já existir
    assert "aluno_vigente" in inspect(engine).get_view_names()


def test_vigente_resolve_pela_ingestao_mais_recente(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        lote = Lote(id="2026-09-L01", periodos_cobertos="2026.1", executado_em=datetime.now(timezone.utc))
        s.add(lote)
        i1 = Ingestao(lote_id=lote.id, passo=1, registros_lidos=0, registros_aceitos=0, registros_rejeitados=0)
        i2 = Ingestao(lote_id=lote.id, passo=2, registros_lidos=0, registros_aceitos=0, registros_rejeitados=0)
        s.add_all([i1, i2])
        s.flush()
        s.add(Usuarios(matricula=1, periodo="2026.1", renda="A", ingestao_id=i1.id))
        s.add(Usuarios(matricula=1, periodo="2026.1", renda="B", ingestao_id=i2.id))
        s.add(Usuarios(matricula=2, periodo="2026.1", renda="C", ingestao_id=i1.id))
        s.add(CrgSemestre(matricula=1, semestre="2025.1", crg=7.5, ingestao_id=i2.id))
        s.commit()

        linhas = s.execute(select(aluno_vigente).order_by(aluno_vigente.c.matricula)).all()
        assert [(l.matricula, l.renda, l.ingestao_id) for l in linhas] == [(1, "B", i2.id), (2, "C", i1.id)]
