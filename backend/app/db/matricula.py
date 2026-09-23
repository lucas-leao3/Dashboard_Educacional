"""Turma e polo saem da matrícula (docs/governanca_dados.md, §4.8).

A matrícula tem 12 dígitos com estrutura fixa:

    2020 1604 0002
    │    │    └── sequencial do aluno
    │    └─────── polo
    └──────────── turma (ano de ingresso)

Não é conveniência: verificado contra a API do FasiTech, `polo` volta nulo em
187 de 187 registros e `primeiro_ano_eletivo` não existe no payload. A
matrícula é a única origem dos dois.

A derivação de verdade acontece no BANCO, na view `aluno_vigente` (ver
app/db/vigente.py) -- assim quem consulta por SQL, quem lê o `vigente.csv` e
quem chama a API enxergam o mesmo valor, sem cada um refazer a conta. Este
módulo guarda a regra em Python para o que o SQL não alcança: semear a tabela
`polo` e conferir a derivação nos testes.
"""

TAMANHO_MATRICULA = 12

#: Dígitos 5-8 -> nome do polo. Validado em 120/120 linhas reais, sem exceção.
#: É a origem das linhas da tabela `polo`; mudar aqui exige uma migração nova.
POLOS_POR_CODIGO: dict[str, str] = {
    "1604": "Cametá",
    "8564": "Limoeiro",
    "8594": "Oeiras",
}

# Fragmentos SQL da derivação. O CASE devolve NULL para matrícula fora do
# padrão, em vez de fatiar lixo silenciosamente -- é o que a §4.8 exige.
_DIGITOS = "CAST({t}.matricula AS TEXT)"


def sql_turma(tabela: str) -> str:
    d = _DIGITOS.format(t=tabela)
    return f"CASE WHEN length({d}) = {TAMANHO_MATRICULA} THEN substr({d}, 1, 4) END"


def sql_codigo_polo(tabela: str) -> str:
    d = _DIGITOS.format(t=tabela)
    return f"CASE WHEN length({d}) = {TAMANHO_MATRICULA} THEN substr({d}, 5, 4) END"


def digitos_da_matricula(matricula) -> str | None:
    """Os 12 dígitos, ou None se a matrícula não estiver no padrão."""
    if matricula is None:
        return None
    texto = str(matricula).strip()
    return texto if len(texto) == TAMANHO_MATRICULA and texto.isdigit() else None


def turma_da_matricula(matricula) -> str | None:
    digitos = digitos_da_matricula(matricula)
    return digitos[:4] if digitos else None


def codigo_de_polo(matricula) -> str | None:
    digitos = digitos_da_matricula(matricula)
    return digitos[4:8] if digitos else None


def polo_da_matricula(matricula) -> str | None:
    """Nome do polo, ou None se a matrícula não servir. Código fora da tabela
    devolve None aqui -- quem exibe decide se mostra o código cru."""
    codigo = codigo_de_polo(matricula)
    return POLOS_POR_CODIGO.get(codigo) if codigo else None
