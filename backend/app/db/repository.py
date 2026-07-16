from pathlib import Path
from src.database.engine import Usuarios
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session


caminho_DB = Path(__file__).parent / 'BancoDeDados.sqlite'
engine = create_engine(f'sqlite:///{caminho_DB}')

def crg_medio():
    with Session(engine) as session:
        comando_sql = select(Usuarios.CRG).group_by(Usuarios.matricula).having(Usuarios.CRG > 0)
        resposta = session.execute(comando_sql).all()
        soma = 0
        for i in resposta:
            soma += i[0]
        return round(soma / len(resposta), 4)

def matriculas_unicas():
    with Session(bind=engine) as session:
        comando_sql = select(func.count(Usuarios.matricula.distinct()))
        resposta = session.execute(comando_sql).all()
        return resposta[0][0]

def consulta_por_argumento(argumento, polo= 'todos'):
    if polo == 'todos':
        polo = polo_todos()
    else:
        polo = [polo]
    argumento = parametros_do_select(argumento)
    with Session(bind=engine) as session:
        comando_sql = select(argumento)
        resposta = session.execute(comando_sql).all()
        return resposta

def consulta_longitudinal(argumento, polo='todos'):
    if argumento != 'perido':
        if polo == 'todos':
            polo = polo_todos()
        else:
            polo = [polo]
        argumento = parametros_do_select(argumento)
        with Session(bind=engine) as session:
            comando_sql = select(argumento, Usuarios.matricula, Usuarios.periodo)
            resposta = session.execute(comando_sql).all()
            return resposta
    return Exception

def consulta_bidimensional(primeiro_arg,segundo_arg, polo= 'todos'):
    if polo == 'todos':
        polo = polo_todos()
    else:
        polo = [polo]
    primeiro_arg = parametros_do_select(primeiro_arg)
    segundo_arg = parametros_do_select(segundo_arg)
    with Session(bind=engine) as session:
        comando_sql = select(primeiro_arg, segundo_arg).where(Usuarios.polo.in_(polo))
        resposta = session.execute(comando_sql).all()
    return resposta

def parametros_do_select(parametro):
    match parametro:
        case 'CRG':
            return Usuarios.CRG
        case 'genero':
            return Usuarios.genero
        case 'cor_etnia':
            return Usuarios.cor_etnia
        case 'pcd':
            return Usuarios.pcd
        case 'tipo_deficiencia':
            return Usuarios.tipo_deficiencia
        case 'renda':
            return Usuarios.renda
        case 'descolamento':
            return Usuarios.descolamento
        case 'trabalho':
            return Usuarios.trabalho
        case 'assistencia_estudante':
            return Usuarios.assistencia_estudante
        case 'saude_mental':
            return Usuarios.saude_mental
        case 'estresse':
            return Usuarios.estresse
        case 'acompanhamento':
            return Usuarios.acompanhamento
        case 'escolaridade_pai':
            return Usuarios.escolaridade_pai
        case 'escolaridade_mae':
            return Usuarios.escolaridade_mae
        case 'qtd_computador':
            return Usuarios.qtd_computador
        case 'qtd_celular':
            return Usuarios.qtd_celular
        case 'computador_proprio':
            return Usuarios.computador_proprio
        case 'gasto_internet':
            return Usuarios.gasto_internet
        case 'acesso_internet':
            return Usuarios.acesso_internet
        case 'tipo_moradia':
            return Usuarios.tipo_moradia
    return None

def polo_todos():
    return ['Cameta', 'Limoeiro', 'Oeiras']