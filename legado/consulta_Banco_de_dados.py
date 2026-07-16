from src.database import repository as consulta
import pandas as pd

print(f'''\nMatriculas unicas: {consulta.matriculas_unicas()}
\nCRG Medio: {consulta.crg_medio()}
''')


print('consulta bidimensional')

arg1 = 'cor_etnia'
arg2 = 'CRG'
resposta = consulta.consulta_bidimensional(primeiro_arg=arg1, segundo_arg=arg2)
df = pd.DataFrame(resposta)
print(df.groupby([arg1])[arg2].describe())


print('\nconsulta por argumento')

arg1 = 'renda'
resposta = consulta.consulta_por_argumento(arg1)
df = pd.DataFrame(resposta)
print(df.groupby([arg1]).size())


print('\nconsulta longitudinal')

arg1 = 'CRG'
resposta = consulta.consulta_longitudinal(arg1)
df = pd.DataFrame(resposta)
print(df.groupby(['periodo'])[arg1].describe())