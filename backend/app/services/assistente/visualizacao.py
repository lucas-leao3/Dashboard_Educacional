"""Escolhe o gráfico pela forma do resultado (spec, Regras de visualização).
Determinístico: a mesma consulta dá sempre o mesmo gráfico."""
import re

from app.schemas.assistente import BlocoDinamico, ConsultaEstruturada, Grafico, Kpi
from app.services.assistente.catalogo import DIMENSOES, METRICAS
from app.services.assistente.compilador import Resultado

MAX_FATIAS_ROSCA = 5
ROTULO_VALOR = {
    "contagem_alunos": "Alunos", "crg_medio": "CRG médio", "crg_medio_semestre": "CRG médio",
    "distribuicao_crg": "Alunos", "campos_sem_resposta": "Alunos sem resposta",
}


def chave_renda(valor: str) -> float:
    """Ordem natural das faixas: 'Até 1' < 'De 1 a 2' < 'Acima de 3'; sem número no fim."""
    texto = str(valor).lower()
    achado = re.search(r"\d+(?:[.,]\d+)?", texto)
    if not achado:
        return float("inf")
    numero = float(achado.group().replace(",", "."))
    if texto.startswith("até"):
        return numero - 0.5
    if texto.startswith(("acima", "mais de")):
        return numero + 0.5
    return numero


def _eh_ordinal(dimensao: str | None) -> bool:
    return bool(dimensao) and dimensao in DIMENSOES and DIMENSOES[dimensao].ordinal


def _chave(dimensao: str | None):
    """Chave de ordenação de uma categoria: ausência ('Sem ...') sempre no fim."""
    if dimensao == "renda":
        return lambda v: (chave_renda(v), str(v))
    return lambda v: (str(v).startswith("Sem "), str(v))


def _ordenar(linhas: list[dict], eixo: str, serie: str | None) -> list[dict]:
    chave_serie = _chave(serie)

    def pela_serie(linha):
        return chave_serie(linha[serie]) if serie else (False, "")

    if _eh_ordinal(eixo):
        chave_eixo = _chave(eixo)
        return sorted(linhas, key=lambda l: (chave_eixo(l[eixo]), pela_serie(l)))
    totais: dict = {}
    for l in linhas:
        totais[l[eixo]] = totais.get(l[eixo], 0) + (l["valor"] or 0)
    return sorted(linhas, key=lambda l: (str(l[eixo]).startswith("Sem "), -totais[l[eixo]], str(l[eixo]), pela_serie(l)))


def _com_percentual(linhas: list[dict], eixo: str | None) -> list[dict]:
    totais: dict = {}
    for l in linhas:
        k = l[eixo] if eixo else None
        totais[k] = totais.get(k, 0) + (l["valor"] or 0)
    return [{**l, "percentual": round(100 * (l["valor"] or 0) / totais[l[eixo] if eixo else None], 1)
             if totais[l[eixo] if eixo else None] else None} for l in linhas]


def titulo_de(consulta: ConsultaEstruturada) -> str:
    titulo = METRICAS[consulta.metrica].rotulo
    if consulta.dimensoes:
        titulo += " por " + " e ".join(DIMENSOES[d].rotulo for d in consulta.dimensoes)
    return titulo


def montar_dinamico(consulta: ConsultaEstruturada, resultado: Resultado) -> BlocoDinamico:
    metrica, linhas = consulta.metrica, resultado.linhas
    rotulo, titulo = ROTULO_VALOR[metrica], titulo_de(consulta)
    ordenar = (lambda ls, e, s: ls) if consulta.ordem else _ordenar  # ranking pedido: vale a ordem do SQL

    def grafico(tipo: str, eixo: str, dados: list[dict], serie: str | None = None) -> BlocoDinamico:
        series = sorted({str(d[serie]) for d in dados}, key=_chave(serie)) if serie else []
        return BlocoDinamico(graficos=[Grafico(
            tipo=tipo, titulo=titulo, eixo=eixo, serie=serie, series=series,
            serie_ordinal=_eh_ordinal(serie), rotulo_valor=rotulo, dados=dados)])

    if metrica == "distribuicao_crg":
        return grafico("histograma", "faixa", linhas)
    if metrica == "campos_sem_resposta":
        return grafico("barras", "campo", linhas)
    dims = list(consulta.dimensoes)
    if not dims:
        return BlocoDinamico(kpis=[Kpi(rotulo=rotulo, valor=linhas[0]["valor"], n=linhas[0]["n"])])
    temporais = [d for d in dims if DIMENSOES[d].temporal]
    if temporais:
        eixo = temporais[0]
        serie = next((d for d in dims if d != eixo), None)
        return grafico("linha", eixo, ordenar(linhas, eixo, serie), serie)
    if len(dims) == 2:
        eixo, serie = dims
        if metrica == "contagem_alunos":
            return grafico("barras_empilhadas", eixo, ordenar(_com_percentual(linhas, eixo), eixo, serie), serie)
        return grafico("barras_agrupadas", eixo, ordenar(linhas, eixo, serie), serie)
    eixo = dims[0]
    if metrica == "contagem_alunos" and not _eh_ordinal(eixo) and len(linhas) <= MAX_FATIAS_ROSCA:
        return grafico("rosca", eixo, ordenar(_com_percentual(linhas, None), eixo, None))
    return grafico("barras", eixo, ordenar(linhas, eixo, None))
