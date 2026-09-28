"""Contratos do assistente (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md).

`ConsultaEstruturada` é o que o LLM devolve e o que o histórico guarda: ela é
reexecutável sem LLM por POST /assistente/executar."""
from typing import Any, Literal

from pydantic import BaseModel, Field

Forma = Literal["dashboard", "dinamico", "tabela", "texto", "nao_entendi"]


class Filtro(BaseModel):
    campo: str
    op: Literal["=", "in", "entre"] = "="
    valor: Any


class Ordem(BaseModel):
    campo: str  # "valor" ou uma dimensão da consulta
    direcao: Literal["asc", "desc"] = "desc"


class ConsultaEstruturada(BaseModel):
    tipo: Literal["agregado", "lista", "operacional", "fora_do_catalogo"]
    metrica: str | None = None
    dimensoes: list[str] = Field(default_factory=list, max_length=2)
    filtros: list[Filtro] = Field(default_factory=list)
    ordem: Ordem | None = None
    limite: int | None = Field(default=None, ge=1, le=1000)
    interpretacao: str = ""


class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)


class ExecutarIn(BaseModel):
    consulta: ConsultaEstruturada


class FiltroAplicado(BaseModel):
    rotulo: str
    valor: str


class Explicacao(BaseModel):
    consulta_interpretada: str
    filtros_aplicados: list[FiltroAplicado]
    fontes: list[str]
    forma: Forma


class BlocoDashboard(BaseModel):
    id: str
    params: dict[str, str]


class Kpi(BaseModel):
    rotulo: str
    valor: float | None
    n: int


class Grafico(BaseModel):
    tipo: Literal["barras", "barras_empilhadas", "barras_agrupadas", "linha", "rosca", "histograma"]
    titulo: str
    eixo: str
    serie: str | None = None
    #: valores da série na ordem de exibição (natural, se ordinal)
    series: list[str] = Field(default_factory=list)
    serie_ordinal: bool = False
    rotulo_valor: str
    dados: list[dict[str, Any]]


class BlocoDinamico(BaseModel):
    kpis: list[Kpi] = Field(default_factory=list)
    graficos: list[Grafico] = Field(default_factory=list)


class Coluna(BaseModel):
    id: str
    rotulo: str


class BlocoTabela(BaseModel):
    colunas: list[Coluna]
    linhas: list[dict[str, Any]]
    total: int


class BlocoTexto(BaseModel):
    mensagem: str
    valor: float | None = None
    n: int | None = None


class BlocoNaoEntendi(BaseModel):
    motivo: str
    sugestoes: list[str]


class RespostaAssistente(BaseModel):
    id: str
    pergunta: str | None
    consulta: ConsultaEstruturada | None
    forma: Forma
    explicacao: Explicacao
    dashboard: BlocoDashboard | None = None
    dinamico: BlocoDinamico | None = None
    tabela: BlocoTabela | None = None
    texto: BlocoTexto | None = None
    nao_entendi: BlocoNaoEntendi | None = None
