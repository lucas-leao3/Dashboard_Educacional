import csv
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "data" / "DadosAgrupados.csv"

# CRG fica de fora de propósito: o valor desse CSV antigo está errado pra
# quase todo mundo (comparado ao histórico oficial). CRG só vem do
# crg_historico.csv (ver services/crg_historico.py).
MAPA_COLUNAS = {
    "Nome": "nome",
    "Data De Nascimento": "data_de_nascimento",
    "Primeiro Ano Eletivo": "primeiro_ano_eletivo",
    "Cor/Etnia": "cor_etnia",
    "PCD": "pcd",
    "Tipo de Deficiência": "tipo_deficiencia",
    "Renda": "renda",
    "Deslocamento": "deslocamento",
    "Trabalho": "trabalho",
    "Assistência Estudantil": "assistencia_estudantil",
    "Saúde Mental": "saude_mental",
    "Estresse": "estresse",
    "Acompanhamento": "acompanhamento",
    "Escolaridade Pai": "escolaridade_pai",
    "Escolaridade Mãe": "escolaridade_mae",
    "Qtd Computador": "qtd_computador",
    "Qtd Celular": "qtd_celular",
    "Computador Próprio": "computador_proprio",
    "Gasto Internet": "gasto_internet",
    "Acesso Internet": "acesso_internet",
    "Tipo Moradia": "tipo_moradia",
    "Data/Hora": "data_hora",
    "Genero": "genero",
    "Polo": "polo",
}


def carregar_dados_legado(caminho: Path = CAMINHO_PADRAO) -> dict[tuple[int, str], dict]:
    """Lê o DadosAgrupados.csv (a planilha manual usada antes da integração
    com o FasiTech) e devolve {(matricula, periodo): {campo: valor}} --
    sem a coluna CRG, que não é confiável nesse CSV.
    """
    dados: dict[tuple[int, str], dict] = {}

    with open(caminho, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        for linha in leitor:
            matricula = linha.get("Matricula")
            periodo = linha.get("Periodo")
            if not matricula or not periodo:
                continue

            chave = (int(matricula), periodo)
            dados[chave] = {
                campo: (linha.get(coluna) or None)
                for coluna, campo in MAPA_COLUNAS.items()
            }

    return dados
