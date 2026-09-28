from datetime import date, datetime, timezone
from typing import Iterator

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
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
    # Extraído dos históricos (semestre letivo da data de emissão de cada
    # PDF), nunca digitado. Ver Historico.periodo.
    periodos_cobertos: Mapped[str] = mapped_column(String(100))        # '2025.2' ou '2025.2;2026.1'
    # O responsável pela importação -- o único dado que o usuário informa.
    executado_por: Mapped[str | None] = mapped_column(String(100))
    # Só lotes anteriores à importação simplificada (o L01) podem ter.
    observacao: Mapped[str | None] = mapped_column(Text)
    # Carimbado ao fim da importação, na mesma transação que grava os dados.
    # Lote fechado é imutável: triggers no banco recusam alterá-lo ou escrever
    # qualquer linha ligada a ele (revisão c5e8a1f3d920).
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


class Historico(Base):
    """Um PDF de histórico lido numa ingestão de passo 2: quem é o aluno e
    de quando é o documento. `periodo` é o semestre letivo da data de emissão
    -- é o período do histórico, e a união deles é lote.periodos_cobertos.

    Presença de histórico não é a regra do cruzamento (quem decide é
    crg_semestre, que o L01 já tem e esta tabela não); aqui fica o que o PDF
    diz sobre identificação e data, inclusive de quem não tem socioeconômico."""
    __tablename__ = "historico"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingestao_id: Mapped[int] = mapped_column(ForeignKey("ingestao.id"))
    arquivo_sha256: Mapped[str | None] = mapped_column(ForeignKey("arquivo_fonte.sha256"))
    matricula: Mapped[int] = mapped_column(BigInteger, index=True)
    nome: Mapped[str | None] = mapped_column(String(100))
    data_de_nascimento: Mapped[str | None] = mapped_column(String)
    emitido_em: Mapped[date] = mapped_column(Date)
    periodo: Mapped[str] = mapped_column(String(6))                     # '2025.2'


class Polo(Base):
    """Código do polo (dígitos 5-8 da matrícula) -> nome (governança §4.8).

    Tabela, e não dicionário no código, porque a view `aluno_vigente` resolve
    o nome por LEFT JOIN: quem consulta o banco por SQL enxerga o mesmo polo
    que o dashboard, sem repetir o mapa. Polo novo é INSERT, não deploy."""
    __tablename__ = "polo"

    codigo: Mapped[str] = mapped_column(String(4), primary_key=True)   # '1604'
    nome: Mapped[str] = mapped_column(String(50))                      # 'Cametá'


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
    # Respostas de questionário: 150 para todas. O vocabulário é do
    # instrumento de pesquisa, não do banco, e muda entre ondas -- larguras
    # apertadas aqui não validam nada, só derrubam a ingestão com 500 quando
    # aparece uma opção legítima mais longa (foi o caso de 'Prefiro não
    # responder', 21 caracteres, em pcd e tipo_moradia no lote 2026-09-L01).
    genero: Mapped[str | None] = mapped_column(String(150))
    polo: Mapped[str | None] = mapped_column(String(15))
    cor_etnia: Mapped[str | None] = mapped_column(String(150))
    pcd: Mapped[str | None] = mapped_column(String(150))
    tipo_deficiencia: Mapped[str | None] = mapped_column(String(150))
    renda: Mapped[str | None] = mapped_column(String(150))
    deslocamento: Mapped[str | None] = mapped_column(String(150))
    trabalho: Mapped[str | None] = mapped_column(String(150))
    assistencia_estudantil: Mapped[str | None] = mapped_column(String(150))
    saude_mental: Mapped[str | None] = mapped_column(String(150))
    estresse: Mapped[str | None] = mapped_column(String(150))
    acompanhamento: Mapped[str | None] = mapped_column(String(150))
    escolaridade_pai: Mapped[str | None] = mapped_column(String(150))
    escolaridade_mae: Mapped[str | None] = mapped_column(String(150))
    # texto, não número -- o FasiTech/CSV manda respostas como "Acima de 3"
    qtd_computador: Mapped[str | None] = mapped_column(String(150))
    qtd_celular: Mapped[str | None] = mapped_column(String(150))
    computador_proprio: Mapped[str | None] = mapped_column(String(150))
    gasto_internet: Mapped[str | None] = mapped_column(String(150))
    acesso_internet: Mapped[str | None] = mapped_column(String(150))
    tipo_moradia: Mapped[str | None] = mapped_column(String(150))
    data_hora: Mapped[str | None] = mapped_column(String(20))


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dependência FastAPI: uma sessão por request. Os testes a substituem
    por uma sessão num PostgreSQL descartável (app.dependency_overrides)."""
    with SessionLocal() as session:
        yield session


# O schema não é mais criado daqui. Quem cria e evolui as tabelas é o Alembic
# (backend/migrations), rodado por `alembic upgrade head`. create_all foi
# removido de propósito: ele cria tabela que falta, mas nunca acrescenta
# coluna a tabela existente -- foi assim que lote.fechado_em ficou de fora de
# um banco já criado. Ver docs/migracoes.md.
