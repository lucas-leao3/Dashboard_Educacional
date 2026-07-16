from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine, String, Integer, Float, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

pastal_atual = Path(__file__).parent
caminho_DB = pastal_atual / 'BancoDeDados.sqlite'

class Base(DeclarativeBase):
    pass

class Usuarios(Base):
    __tablename__ = 'usuarios'

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str | None] = mapped_column(String(100))
    data_de_nascimento: Mapped[str | None] = mapped_column(String)
    matricula: Mapped[int] = mapped_column(Integer)
    primeiro_ano_eletivo: Mapped[str | None] = mapped_column(String(10))
    CRG: Mapped[float] = mapped_column(Float)
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
    qtd_computador: Mapped[int | None] = mapped_column(Integer)
    qtd_celular: Mapped[int | None] = mapped_column(Integer)
    computador_proprio: Mapped[str | None] = mapped_column(String(5))
    gasto_internet: Mapped[str | None] = mapped_column(String(30))
    acesso_internet: Mapped[str | None] = mapped_column(String(5))
    tipo_moradia: Mapped[str | None] = mapped_column(String(10))
    data_hora: Mapped[str | None] = mapped_column(String(20))

engine = create_engine(f'sqlite:///{caminho_DB}')
Base.metadata.create_all(bind=engine)

def criando_usuario(
        nome: str,
        data_de_nascimento: str,
        matricula: int,
        primeiro_ano_eletivo: str,
        crg: float,
        periodo: str,
        genero: str,
        polo: str,
        cor_etnia: str,
        pcd: str,
        tipo_deficiencia: str,
        renda: str,
        deslocamento: str,
        trabalho: str,
        assistencia_estudantil: str,
        saude_mental: str,
        estresse: str,
        acompanhamento: str,
        escolaridade_pai: str,
        escolaridade_mae: str,
        qtd_computador: int,
        qtd_celular: int,
        computador_proprio: str,
        gasto_internet: str,
        acesso_internet: str,
        tipo_moradia: str,
        data_hora: str,
):

    with Session(bind=engine) as session:
        usuario = Usuarios(
            nome=nome,
            data_de_nascimento=data_de_nascimento,
            matricula=matricula,
            primeiro_ano_eletivo=primeiro_ano_eletivo,
            CRG=crg,
            periodo=periodo,
            genero=genero,
            polo=polo,
            cor_etnia=cor_etnia,
            pcd=pcd,
            tipo_deficiencia=tipo_deficiencia,
            renda=renda,
            deslocamento=deslocamento,
            trabalho=trabalho,
            assistencia_estudantil=assistencia_estudantil,
            saude_mental=saude_mental,
            estresse=estresse,
            acompanhamento=acompanhamento,
            escolaridade_pai=escolaridade_pai,
            escolaridade_mae=escolaridade_mae,
            qtd_computador=qtd_computador,
            qtd_celular=qtd_celular,
            computador_proprio=computador_proprio,
            gasto_internet=gasto_internet,
            acesso_internet=acesso_internet,
            tipo_moradia=tipo_moradia,
            data_hora=data_hora
        )
        session.add(usuario)
        session.commit()