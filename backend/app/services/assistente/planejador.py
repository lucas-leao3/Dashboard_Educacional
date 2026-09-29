"""Decide a forma da resposta (spec, planejador). Regras, nesta ordem:
fora do catálogo -> não entendi; cabe num dashboard -> dashboard; lista ->
tabela; um número só -> texto; o resto -> dashboard dinâmico."""
from dataclasses import dataclass

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.catalogo import DASHBOARDS, Dashboard


@dataclass(frozen=True)
class Plano:
    forma: str
    dashboard: Dashboard | None = None


def _dashboard_para(consulta: ConsultaEstruturada) -> Dashboard | None:
    if consulta.ordem is not None or consulta.limite is not None:
        return None  # dashboard não ordena nem corta: a pergunta pede um ranking
    campos = [f.campo for f in consulta.filtros]
    if len(set(campos)) != len(campos) or any(f.op != "=" for f in consulta.filtros):
        return None  # a URL das telas leva um valor por filtro
    for d in DASHBOARDS:
        if (consulta.tipo == d.tipo and consulta.metrica in d.metricas
                and frozenset(consulta.dimensoes) in d.dimensoes
                and d.obrigatorios <= set(campos) <= d.obrigatorios | d.opcionais):
            return d
    return None


def planejar(consulta: ConsultaEstruturada) -> Plano:
    if consulta.tipo == "fora_do_catalogo":
        return Plano("nao_entendi")
    dashboard = _dashboard_para(consulta)
    if dashboard:
        return Plano("dashboard", dashboard)
    if consulta.tipo == "lista":
        return Plano("tabela")
    if consulta.metrica == "resumo_ultimo_lote":
        return Plano("texto")
    if consulta.tipo == "agregado" and not consulta.dimensoes and consulta.metrica != "distribuicao_crg":
        return Plano("texto")
    return Plano("dinamico")


def params_do_dashboard(dashboard: Dashboard, consulta: ConsultaEstruturada) -> dict[str, str]:
    params = {f.campo: str(f.valor) for f in consulta.filtros}
    if dashboard.param_dimensao:
        params[dashboard.param_dimensao] = consulta.dimensoes[0]
    return params
