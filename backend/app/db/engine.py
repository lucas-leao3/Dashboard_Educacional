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
    nome: Mapped[str] = mapped_column(String(100),nullable=True)
    data_de_nascimento: Mapped[str] = mapped_column(String,nullable=True)
    matricula: Mapped[int] = mapped_column(Integer, nullable=False)
    primeiro_ano_eletivo: Mapped[str] = mapped_column(String(10),nullable=True)
    CRG: Mapped[float] = mapped_column(Float,nullable=False)
    periodo: Mapped[str] = mapped_column(String(15), nullable=False)
    genero: Mapped[str] = mapped_column(String(20),nullable=True)
    polo: Mapped[str] = mapped_column(String(15),nullable=True)
    cor_etnia: Mapped[str] = mapped_column(String(10),nullable=True)
    pcd: Mapped[str] = mapped_column(String(5),nullable=True)
    tipo_deficiencia: Mapped[str] = mapped_column(String(100),nullable=True)
    renda: Mapped[str] = mapped_column(String(150),nullable=True)
    deslocamento: Mapped[str] = mapped_column(String(150),nullable=True)
    trabalho: Mapped[str] = mapped_column(String(150),nullable=True)
    assistencia_estudantil: Mapped[str] = mapped_column(String(5),nullable=True)
    saude_mental: Mapped[str] = mapped_column(String(10),nullable=True)
    estresse: Mapped[str] = mapped_column(String(50),nullable=True)
    acompanhamento: Mapped[str] = mapped_column(String(20),nullable=True)
    escolaridade_pai: Mapped[str] = mapped_column(String(20),nullable=True)
    escolaridade_mae: Mapped[str] = mapped_column(String(20),nullable=True)
    qtd_computador: Mapped[int] = mapped_column(Integer,nullable=True)
    qtd_celular: Mapped[int] = mapped_column(Integer,nullable=True)
    computador_proprio: Mapped[str] = mapped_column(String(5),nullable=True)
    gasto_internet: Mapped[str] = mapped_column(String(30),nullable=True)
    acesso_internet: Mapped[str] = mapped_column(String(5),nullable=True)
    tipo_moradia: Mapped[str] = mapped_column(String(10),nullable=True)
    data_hora: Mapped[str] = mapped_column(String(20),nullable=True)

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