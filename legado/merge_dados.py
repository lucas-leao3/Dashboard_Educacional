import json
from pathlib import Path
from src.database.engine import criando_usuario
import pandas as pd

def merge_dados_json(dados_json):
    dados = Path(__file__).parent.parent / 'src' / 'database' / 'DadosAgrupados.csv'
    df = pd.read_csv(dados)
    #dados_json = json.loads(dados_json.read_text(encoding='utf-8'))
    #df2 = pd.DataFrame(dados_json['dados'])
    #df2.rename(columns={'matricula':'Matricula'}, inplace=True)
    #df2['Matricula'] =pd.to_numeric(df2['Matricula'], errors='coerce')
    #df3 = pd.merge(df, df2, on='Matricula', how='inner')
    dicionario = df.to_dict(orient='records')
    return dicionario
