"""Schema: as migrações produzem o que os modelos declaram, e a view
aluno_vigente resolve, por (matricula, periodo), a linha da ingestão mais
recente -- é ela que o dashboard lê (governança, seção 4.5)."""
from datetime import datetime, timezone

from sqlalchemy import String, inspect, select
from sqlalchemy.orm import Session

from app.db.engine import Base, CrgSemestre, Ingestao, Lote, Usuarios
from app.db.migracoes import aplicar_migracoes
from app.db.vigente import aluno_vigente


# O banco vem do fixture `db_engine` (tests/conftest.py): um PostgreSQL
# descartável, migrado, um por teste. Estes testes já montaram o próprio
# SQLite; não montam mais -- schema só vale verificado no banco de verdade.


async def test_migracoes_criam_tabelas_e_view(db_engine):
    inspector = inspect(db_engine)
    assert {"lote", "arquivo_fonte", "ingestao", "excecao", "crg_semestre", "usuarios", "polo"} <= set(inspector.get_table_names())
    assert "aluno_vigente" in inspector.get_view_names()


async def test_migracoes_sao_idempotentes(db_engine):
    aplicar_migracoes(db_engine)  # segunda chamada não pode falhar por já estar em head
    assert "aluno_vigente" in inspect(db_engine).get_view_names()


async def test_migracoes_cobrem_todas_as_colunas_dos_modelos(db_engine):
    """Regressão: modelo que ganha coluna sem revisão do Alembic quebra aqui,
    e não em produção. Foi o que aconteceu com lote.fechado_em -- create_all
    via a tabela já existente e nunca acrescentava a coluna."""
    inspector = inspect(db_engine)
    faltando = {}
    for nome, tabela in Base.metadata.tables.items():
        colunas_no_banco = {c["name"] for c in inspector.get_columns(nome)}
        ausentes = {c.name for c in tabela.columns} - colunas_no_banco
        if ausentes:
            faltando[nome] = sorted(ausentes)
    assert not faltando, f"colunas no modelo sem migração correspondente: {faltando}"


async def test_vigente_resolve_pela_ingestao_mais_recente(db_engine):
    with Session(db_engine) as s:
        lote = Lote(id="2026-09-L01", periodos_cobertos="2026.1", executado_em=datetime.now(timezone.utc))
        s.add(lote)
        # Flush do pai antes do filho, de propósito. Os modelos não declaram
        # `relationship()`, e sem isso o SQLAlchemy não garante a ordem de
        # flush entre mappers -- aqui ele emitia `ingestao` antes de `lote`.
        # No SQLite isso passava despercebido (ele não valida foreign key por
        # padrão); o PostgreSQL recusa com ForeignKeyViolation. O código de
        # produção já grava nesta ordem (exigir_lote -> abrir_ingestao ->
        # _inserir_snapshot); era só este teste que dependia da sorte.
        s.flush()
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


# Respostas de questionário: toda coluna que guarda uma tem que caber numa
# opção longa. "Prefiro não responder" tem 21 caracteres e derrubou o passo 1
# do lote 2026-09-L01 em pcd (varchar(5)) e tipo_moradia (varchar(10)).
LARGURA_MINIMA_RESPOSTA = 150
COLUNAS_DE_RESPOSTA = {
    "genero", "cor_etnia", "pcd", "tipo_deficiencia", "renda", "deslocamento",
    "trabalho", "assistencia_estudantil", "saude_mental", "estresse",
    "acompanhamento", "escolaridade_pai", "escolaridade_mae", "qtd_computador",
    "qtd_celular", "computador_proprio", "gasto_internet", "acesso_internet",
    "tipo_moradia",
}


def test_colunas_de_resposta_cabem_respostas_longas():
    """Verificação estática do modelo, mais barata e mais explícita que um
    insert. A suíte roda em PostgreSQL, então uma coluna estreita demais também
    falharia num insert longo -- mas aqui o erro diz qual coluna e quanto falta,
    em vez de estourar no meio de um lote como aconteceu no 2026-09-L01."""
    estreitas = {
        c.name: c.type.length
        for c in Usuarios.__table__.columns
        if c.name in COLUNAS_DE_RESPOSTA
        and isinstance(c.type, String)
        and c.type.length is not None
        and c.type.length < LARGURA_MINIMA_RESPOSTA
    }
    assert not estreitas, (
        f"colunas de resposta estreitas demais (mínimo {LARGURA_MINIMA_RESPOSTA}): {estreitas}"
    )
