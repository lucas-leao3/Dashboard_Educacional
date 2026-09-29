"""Tudo o que o usuário lê: explicação, textos, tabela, 'não entendi'.
Texto sai de template preenchido com o resultado; o resultado nunca volta ao LLM."""
from app.schemas.assistente import (BlocoNaoEntendi, BlocoTabela, BlocoTexto, Coluna, ConsultaEstruturada,
                                    FiltroAplicado)
from app.services.assistente.catalogo import DIMENSOES, METRICAS, ROTULOS_RESPOSTA
from app.services.assistente.compilador import Resultado

SUGESTOES = [
    "Quantos alunos existem por polo?",
    "Qual a distribuição de renda familiar dos alunos?",
    "Compare renda familiar por polo",
    "Mostre a evolução do CRG por semestre",
    "Liste os alunos com dados incompletos",
]
ROTULOS_COLUNA = {
    "matricula": "Matrícula", "nome": "Nome", "polo": "Polo", "turma": "Turma", "periodo": "Período",
    "crg": "CRG", "campos_sem_resposta": "Campos sem resposta", "preenchimento": "% preenchido",
    "motivo": "Motivo", "detalhe": "Detalhe", **ROTULOS_RESPOSTA,
}


def _num(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def filtros_aplicados(consulta: ConsultaEstruturada) -> list[FiltroAplicado]:
    aplicados = []
    for f in consulta.filtros:
        valores = [str(v) for v in (f.valor if isinstance(f.valor, list) else [f.valor])]
        texto = f"{valores[0]} a {valores[1]}" if f.op == "entre" else ", ".join(valores)
        aplicados.append(FiltroAplicado(rotulo=DIMENSOES[f.campo].rotulo, valor=texto))
    return aplicados


def _sufixo(consulta: ConsultaEstruturada) -> str:
    aplicados = filtros_aplicados(consulta)
    return " com " + ", ".join(f"{f.rotulo}: {f.valor}" for f in aplicados) if aplicados else ""


def descrever(consulta: ConsultaEstruturada) -> str:
    """O que foi executado, descrito a partir da consulta, e não da paráfrase do LLM."""
    if consulta.tipo == "fora_do_catalogo":
        return consulta.interpretacao or "Pergunta fora do que o assistente sabe consultar."
    texto = METRICAS[consulta.metrica].rotulo
    if consulta.dimensoes:
        texto += " por " + " e ".join(DIMENSOES[d].rotulo for d in consulta.dimensoes)
    return texto + _sufixo(consulta)


def texto_para(consulta: ConsultaEstruturada, resultado: Resultado) -> BlocoTexto:
    if not resultado.linhas:
        vazio = "Nenhum lote importado ainda." if consulta.tipo == "operacional" else "Nenhum aluno com esses filtros."
        return BlocoTexto(mensagem=vazio)
    linha = resultado.linhas[0]
    if consulta.metrica == "resumo_ultimo_lote":
        return BlocoTexto(
            mensagem=(f"No lote {linha['lote']} foram lidos {linha['registros_lidos']} registros e aceitos "
                      f"{linha['registros_aceitos']}. Na base consolidada até ele, {linha['integrados']} aluno(s) "
                      f"estão integrados e {linha['nao_integrados']} não integrados."),
            valor=linha["integrados"])
    sufixo = _sufixo(consulta)
    if consulta.metrica == "contagem_alunos":
        if not linha["valor"]:
            return BlocoTexto(mensagem="Nenhum aluno com esses filtros.", valor=0, n=0)
        return BlocoTexto(mensagem=f"{linha['valor']} aluno(s) integrado(s){sufixo}.", valor=linha["valor"], n=linha["n"])
    if linha["valor"] is None:
        return BlocoTexto(mensagem=f"Nenhum aluno com CRG apurado{sufixo}.", n=0)
    return BlocoTexto(mensagem=f"CRG médio de {_num(linha['valor'])}{sufixo}, sobre {linha['n']} aluno(s) com CRG apurado.",
                      valor=linha["valor"], n=linha["n"])


def tabela_para(resultado: Resultado) -> BlocoTabela:
    colunas = [Coluna(id=c, rotulo=ROTULOS_COLUNA.get(c, c)) for c in resultado.colunas]
    total = resultado.total if resultado.total is not None else len(resultado.linhas)
    return BlocoTabela(colunas=colunas, linhas=resultado.linhas, total=total)


def nao_entendi(motivo: str) -> BlocoNaoEntendi:
    return BlocoNaoEntendi(motivo=motivo, sugestoes=SUGESTOES)
