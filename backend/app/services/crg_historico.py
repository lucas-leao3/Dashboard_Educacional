"""Lê o histórico acadêmico do SIGAA (PDF) e devolve o CRG por semestre
letivo -- é isso que dá o progresso do aluno (docs/governanca_dados.md, 4.6).

Dividido em duas funções de propósito: extrair_texto depende de PDF e
pypdf; interpretar_historico é texto puro e testável sem PDF real.
"""
import re
from datetime import date
from pathlib import Path

from pypdf import PdfReader

_EMISSAO = re.compile(r"Emitido em:\s*(\d{2})/(\d{2})/(\d{4})")
_MATRICULA = re.compile(r"Matrícula:\s*(\d{12})")
_NOME = re.compile(r"Nome:\s*(.+?)\s{2,}Matrícula")
_NASCIMENTO = re.compile(r"Data de Nascimento:\s*(\d{2}/\d{2}/\d{4})")
_TITULO_BLOCO = "Coeficiente de Rendimento por Semestre"
_FIM_BLOCO = "Componentes Curriculares"
_SEMESTRE = re.compile(r"(\d{4})/Sem([12]):\s*([\d.]+)")


def extrair_texto(caminho_pdf: Path) -> str:
    # layout preserva a posição das colunas; sem ele o bloco de semestres
    # se separa do título e 'Nome:' perde o valor (validado nos 56 PDFs).
    leitor = PdfReader(str(caminho_pdf))
    return "\n".join(pagina.extract_text(extraction_mode="layout") or "" for pagina in leitor.pages)


def semestre_da_data(d: date) -> str:
    return f"{d.year}.{1 if d.month <= 6 else 2}"


def aplicar_regra_do_zero(crg_por_semestre: dict[str, float], emitido_em: date) -> dict[str, float | None]:
    """Semestre igual ou posterior ao da emissão ainda não foi apurado: o
    0.00 que o SIGAA imprime ali não é nota. Antes disso, zero é zero."""
    corte = semestre_da_data(emitido_em)
    return {sem: (None if sem >= corte else valor) for sem, valor in crg_por_semestre.items()}


def interpretar_historico(texto: str) -> dict:
    emissao = _EMISSAO.search(texto)
    matricula = _MATRICULA.search(texto)
    if emissao is None or matricula is None:
        raise ValueError("Histórico sem data de emissão ou matrícula")

    inicio = texto.find(_TITULO_BLOCO)
    if inicio < 0:
        raise ValueError("Histórico sem bloco 'Coeficiente de Rendimento por Semestre Letivo'")
    fim = texto.find(_FIM_BLOCO, inicio)
    bloco = texto[inicio: fim if fim > 0 else None]
    semestres = {f"{ano}.{sem}": float(valor) for ano, sem, valor in _SEMESTRE.findall(bloco)}
    if not semestres:
        raise ValueError("Bloco de semestres vazio")

    dia, mes, ano = (int(x) for x in emissao.groups())
    emitido_em = date(ano, mes, dia)
    nome = _NOME.search(texto)
    nascimento = _NASCIMENTO.search(texto)
    return {
        "matricula": int(matricula.group(1)),
        "nome": nome.group(1).strip() if nome else None,
        "data_de_nascimento": nascimento.group(1) if nascimento else None,
        "emitido_em": emitido_em,
        "crg_por_semestre": aplicar_regra_do_zero(semestres, emitido_em),
    }


def ultimo_crg_apurado(crg_por_semestre: dict[str, float | None]) -> float | None:
    apurados = [(sem, v) for sem, v in crg_por_semestre.items() if v is not None]
    return max(apurados)[1] if apurados else None


def carregar_historico(caminho_pdf: Path) -> dict:
    return interpretar_historico(extrair_texto(caminho_pdf))
