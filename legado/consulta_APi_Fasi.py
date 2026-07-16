from cmath import nan
from datetime import datetime
from src.database.engine import criando_usuario
from src.utils.validação_de_dados import verificacao
from merge_dados import merge_dados_json as merge
import pandas as pd
import os
import requests
import dotenv


dotenv.load_dotenv()

token = os.getenv("token_fasi")

base_url = "https://www.fasitech.com.br/api/v1/_dev/raw-social-data"
headers = {
    "Authorization": f"Bearer {token}"
}
for i in range(1,2):
    params = {
        "pagina": i,
        "por_pagina": 100
    }
    response = requests.get(base_url, headers=headers, params=params)

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f'Erro no request: {e}')
    else:
        response_json = response.json()
        todos_os_dados = merge(response_json)
        if todos_os_dados is not None:
            for registros in todos_os_dados:
                if valido := verificacao(matricula=registros['Matricula'],
                                         periodo=registros['Periodo'],
                                         crg=registros['CRG']):
                    if pd.isna(registros['Data/Hora']):
                        pass
                    else:
                        registros['Data/Hora'] = datetime.fromisoformat(registros['Data/Hora'])
                    criando_usuario(
                        nome=registros['Nome'],
                        data_de_nascimento=registros['Data De Nascimento'],
                        matricula=registros['Matricula'],
                        primeiro_ano_eletivo=registros['Primeiro Ano Eletivo'],
                        crg=registros['CRG'],
                        periodo=registros['Periodo'],
                        genero=registros['Genero'],
                        polo=registros['Polo'],
                        cor_etnia=registros['Cor/Etnia'],
                        pcd=registros['PCD'],
                        tipo_deficiencia=registros['Tipo de Deficiência'],
                        renda=registros['Renda'],
                        deslocamento=registros['Deslocamento'],
                        trabalho=registros['Trabalho'],
                        assistencia_estudantil=registros['Assistência Estudantil'],
                        saude_mental=registros['Saúde Mental'],
                        estresse=registros['Estresse'],
                        acompanhamento=registros['Acompanhamento'],
                        escolaridade_pai=registros['Escolaridade Pai'],
                        escolaridade_mae=registros['Escolaridade Mãe'],
                        qtd_computador=registros['Qtd Computador'],
                        qtd_celular=registros['Qtd Celular'],
                        computador_proprio=registros['Computador Próprio'],
                        gasto_internet=registros['Gasto Internet'],
                        acesso_internet=registros['Acesso Internet'],
                        tipo_moradia=registros['Tipo Moradia'],
                        data_hora=registros['Data/Hora']
                        )
