from pathlib import Path
from sqlalchemy.orm import Session
from src.database.engine import Usuarios
from sqlalchemy import create_engine, select
from src.models.shemas import validacao

caminho_DB = Path(__file__).parent.parent / 'database' / 'BancoDeDados.sqlite'
engine = create_engine(f'sqlite:///{caminho_DB}')


def verificacao(matricula: int, periodo: str, crg: float) -> bool:
    validacao(matricula=matricula, periodo=periodo, crg=crg)
    with Session(bind=engine) as session:
        comando_sql = select(Usuarios).filter_by(matricula=matricula, periodo=periodo)
        usario = session.execute(comando_sql).fetchall()
        if usario == []:
            return True
        return False