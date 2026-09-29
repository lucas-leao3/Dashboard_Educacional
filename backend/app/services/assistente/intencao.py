"""Pergunta (já anonimizada) -> ConsultaEstruturada, com uma chamada ao LLM.

O prompt leva o catálogo inteiro: métricas, dimensões e os valores válidos de
cada uma (opções do questionário, polos, turmas, períodos). Nenhuma linha de
aluno. Se a resposta não validar, o erro volta ao modelo uma vez."""
import json
import re

from pydantic import ValidationError

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.catalogo import DIMENSOES, METRICAS, ConsultaInvalida, validar
from app.services.assistente.provedor_llm import ProvedorLLM

SISTEMA = """Você traduz perguntas sobre alunos de um curso de graduação para uma consulta estruturada.
Responda APENAS um objeto JSON com as chaves:
  tipo: "agregado" | "lista" | "operacional" | "fora_do_catalogo"
  metrica: id de métrica do catálogo (null se fora_do_catalogo)
  dimensoes: lista de ids de dimensão para agrupar (0 a 2)
  filtros: lista de {"campo": id, "op": "=" | "in" | "entre", "valor": valor ou lista}
  ordem: {"campo": "valor" ou id de dimensão, "direcao": "asc" | "desc"} ou null
  limite: inteiro ou null
  interpretacao: uma frase em português dizendo o que você entendeu
Regras:
- Use só ids e valores que aparecem no catálogo, com a grafia exata.
- Marcadores como ⟨A1⟩ representam um aluno: use-os como valor do campo "matricula".
- "Mostre/liste alunos" é tipo "lista" com metrica "alunos". "Quantos" sem agrupamento é "agregado" sem dimensões.
- Turma é o ano de ingresso: "ingressaram em 2020" é o filtro turma = "2020".
- Se a pergunta pede algo que o catálogo não tem, use tipo "fora_do_catalogo" e diga em interpretacao o que falta."""


def descrever_catalogo(valores: dict[str, list[str]]) -> str:
    linhas = ["MÉTRICAS (id [tipo]: descrição; dimensões aceitas; filtros aceitos):"]
    for m in METRICAS.values():
        linhas.append(f"- {m.id} [{m.tipo}]: {m.rotulo}; dimensões: {', '.join(sorted(m.dimensoes)) or 'nenhuma'}; "
                      f"filtros: {', '.join(sorted(m.filtros)) or 'nenhum'}")
    linhas.append("DIMENSÕES (id (rótulo): valores válidos):")
    for d in DIMENSOES.values():
        if d.id == "matricula":
            linhas.append("- matricula (Matrícula): só marcadores ⟨An⟩ presentes na pergunta")
        else:
            linhas.append(f"- {d.id} ({d.rotulo}): {json.dumps(valores.get(d.id, []), ensure_ascii=False)}")
    return "\n".join(linhas)


def montar_mensagens(pergunta: str, valores: dict[str, list[str]]) -> list[dict]:
    return [{"role": "system", "content": f"{SISTEMA}\n\nCATÁLOGO\n{descrever_catalogo(valores)}"},
            {"role": "user", "content": pergunta}]


def _extrair_json(texto: str) -> str:
    """Alguns modelos embrulham o JSON em ```json ... ``` mesmo em JSON mode."""
    achado = re.search(r"\{.*\}", texto, re.DOTALL)
    return achado.group() if achado else texto


def interpretar(provedor: ProvedorLLM, pergunta: str, valores: dict[str, list[str]]) -> ConsultaEstruturada | None:
    mensagens = montar_mensagens(pergunta, valores)
    for _ in range(2):
        texto = provedor.completar(mensagens)
        try:
            return validar(ConsultaEstruturada.model_validate_json(_extrair_json(texto)), valores)
        except (ValidationError, ConsultaInvalida) as erro:
            mensagens = [*mensagens, {"role": "assistant", "content": texto},
                         {"role": "user", "content": f"Resposta inválida: {erro}. Corrija e responda só o JSON."}]
    return None
