import csv
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "data" / "crg_historico.csv"


def carregar_dados_do_historico(caminho: Path = CAMINHO_PADRAO) -> dict[int, dict]:
    """Lê o CSV de históricos acadêmicos e devolve um dicionário
    {matricula: {"CRG": ..., "nome": ..., "data_de_nascimento": ...}}.
    """
    dados_por_matricula: dict[int, dict] = {}

    with open(caminho, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        for linha in leitor:
            dados_por_matricula[int(linha["Matricula"])] = {
                "CRG": float(linha["CRG"]),
                "nome": linha["Nome"],
                "data_de_nascimento": linha["Data De Nascimento"],
            }

    return dados_por_matricula
