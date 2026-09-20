from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker

from app.core.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Lote(Base):
    """Uma rodada completa das rotas (governança, seção 3.1). Espelha
    raw/lotes/<id>/ no banco."""
    __tablename__ = "lote"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)       # 2026-09-L01
    executado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora)
    periodos_cobertos: Mapped[str] = mapped_column(String(100))        # '2025.2;2026.1'
    executado_por: Mapped[str | None] = mapped_column(String(100))
    observacao: Mapped[str | None] = mapped_column(Text)
    # Preenchido por POST /lotes/{id}/fechar. Lote fechado não recebe mais
    # insumo nem se reabre.
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArquivoFonte(Base):
    """De onde veio: um arquivo bruto do lote, identificado pelo hash."""
    __tablename__ = "arquivo_fonte"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    lote_id: Mapped[str] = mapped_column(ForeignKey("lote.id"))
    nome_original: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(30))   # pdf_historico | csv_legado | api_fasitech
    tamanho_bytes: Mapped[int] = mapped_column(Integer)


class Ingestao(Base):
    """Um passo do lote. Toda escrita em usuarios/crg_semestre/excecao
    referencia uma ingestão -- é o que torna 'rodei o endpoint' rastreável."""
    __tablename__ = "ingestao"
    __table_args__ = (UniqueConstraint("lote_id", "passo", name="ux_ingestao_lote_passo"),)

    PASSO_MANUAL = 0
    PASSO_SINCRONIZAR = 1
    PASSO_CRG = 2

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[str] = mapped_column(ForeignKey("lote.id"))
    passo: Mapped[int] = mapped_column(Integer)
    arquivo_sha256: Mapped[str | None] = mapped_column(ForeignKey("arquivo_fonte.sha256"))
    executado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora)
    registros_lidos: Mapped[int] = mapped_column(Integer, default=0)
    registros_aceitos: Mapped[int] = mapped_column(Integer, default=0)
    registros_rejeitados: Mapped[int] = mapped_column(Integer, default=0)


class Excecao(Base):
    """O que não casou, com motivo. Substitui os contadores que somiam."""
    __tablename__ = "excecao"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingestao_id: Mapped[int] = mapped_column(ForeignKey("ingestao.id"))
    matricula: Mapped[int | None] = mapped_column(BigInteger)
    periodo: Mapped[str | None] = mapped_column(String(15))
    motivo: Mapped[str] = mapped_column(String(30))  # sem_academico | sem_socioeconomico | matricula_invalida | sem_periodo | duplicado
    detalhe: Mapped[str | None] = mapped_column(Text)


class CrgSemestre(Base):
    """CRG por semestre letivo, extraído do PDF do SIGAA (governança, 4.6).
    crg NULL = semestre ainda não apurado na data de emissão."""
    __tablename__ = "crg_semestre"

    matricula: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    semestre: Mapped[str] = mapped_column(String(6), primary_key=True)   # '2024.1'
    ingestao_id: Mapped[int] = mapped_column(ForeignKey("ingestao.id"), primary_key=True)
    crg: Mapped[float | None] = mapped_column(Float)


class Usuarios(Base):
    __tablename__ = 'usuarios'

    id: Mapped[int] = mapped_column(primary_key=True)
    ingestao_id: Mapped[int] = mapped_column(ForeignKey("ingestao.id"))
    nome: Mapped[str | None] = mapped_column(String(100))
    data_de_nascimento: Mapped[str | None] = mapped_column(String)
    matricula: Mapped[int] = mapped_column(BigInteger)
    primeiro_ano_eletivo: Mapped[str | None] = mapped_column(String(10))
    CRG: Mapped[float | None] = mapped_column(Float)
    periodo: Mapped[str] = mapped_column(String(15))
    genero: Mapped[str | None] = mapped_column(String(20))
    polo: Mapped[str | None] = mapped_column(String(15))
    cor_etnia: Mapped[str | None] = mapped_column(String(10))
    pcd: Mapped[str | None] = mapped_column(String(5))
    tipo_deficiencia: Mapped[str | None] = mapped_column(String(100))
    renda: Mapped[str | None] = mapped_column(String(150))
    deslocamento: Mapped[str | None] = mapped_column(String(150))
    trabalho: Mapped[str | None] = mapped_column(String(150))
    assistencia_estudantil: Mapped[str | None] = mapped_column(String(5))
    saude_mental: Mapped[str | None] = mapped_column(String(10))
    estresse: Mapped[str | None] = mapped_column(String(50))
    acompanhamento: Mapped[str | None] = mapped_column(String(20))
    escolaridade_pai: Mapped[str | None] = mapped_column(String(20))
    escolaridade_mae: Mapped[str | None] = mapped_column(String(20))
    # texto, não número -- o FasiTech/CSV manda respostas como "Acima de 3"
    qtd_computador: Mapped[str | None] = mapped_column(String(20))
    qtd_celular: Mapped[str | None] = mapped_column(String(20))
    computador_proprio: Mapped[str | None] = mapped_column(String(5))
    gasto_internet: Mapped[str | None] = mapped_column(String(30))
    acesso_internet: Mapped[str | None] = mapped_column(String(5))
    tipo_moradia: Mapped[str | None] = mapped_column(String(10))
    data_hora: Mapped[str | None] = mapped_column(String(20))


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dependência FastAPI: uma sessão por request. Os testes a substituem
    por uma sessão num SQLite temporário (app.dependency_overrides)."""
    with SessionLocal() as session:
        yield session


def criar_schema(engine_alvo) -> None:
    """Cria tabelas e a view aluno_vigente que faltam. Chamado no lifespan,
    nunca no import. Idempotente: pode rodar a cada subida."""
    from app.db.vigente import VIEW_SQL, aluno_vigente

    Base.metadata.create_all(bind=engine_alvo)
    if aluno_vigente.name not in inspect(engine_alvo).get_view_names():
        with engine_alvo.begin() as conexao:
            conexao.execute(text(VIEW_SQL))
