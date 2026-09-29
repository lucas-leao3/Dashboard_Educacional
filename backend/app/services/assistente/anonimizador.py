"""Tira da pergunta o que identifica aluno antes de ela sair para o LLM (spec, D2).

Matrícula (9+ dígitos seguidos, ou em grupos separados por ponto ou hífen) e
nome da base (2+ palavras, comparado sem caixa e sem acento) viram marcadores
⟨A1⟩, ⟨A2⟩... Do nome vale também o primeiro nome com qualquer sobrenome
("Maria Santos" para Maria da Silva Santos), que é como as pessoas escrevem.
O mapa fica na requisição; o LLM usa o marcador como valor do filtro
`matricula` e o pipeline troca de volta. Nome de uma palavra só fica de fora
de propósito: casaria com palavra comum da pergunta. Matrícula separada por
espaço também: "2020 2021 2022" (três turmas) viraria uma matrícula.
"""
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import Historico, Usuarios

_DIGITOS = re.compile(r"\d{9,}")
# Matrícula digitada em grupos ("2020.1604.0001", "2020-1604-0001"). Grupos de
# 3+ dígitos, para "2024.1-2025.2" (intervalo de semestres) não casar.
_DIGITOS_SEPARADOS = re.compile(r"(?<![\d.\-])\d{3,}(?:[.\-]\d{3,})+(?![\d.\-])")
_MARCADOR = re.compile(r"⟨A\d+⟩")
_PARTICULAS = frozenset({"da", "de", "do", "das", "dos", "e"})


def _dobrar(c: str) -> str:
    base = "".join(x for x in unicodedata.normalize("NFKD", c) if not unicodedata.combining(x)).lower()
    return base[:1] or c


def dobrar(texto: str) -> str:
    """Sem acento e em minúscula, caractere a caractere: o resultado tem o mesmo
    tamanho do original, então uma posição achada nele vale no original."""
    return "".join(_dobrar(c) for c in texto)


@dataclass
class Anonimizada:
    texto: str
    marcadores: dict[str, str] = field(default_factory=dict)  # "⟨A1⟩" -> "202016040001"


def nomes_da_base(session: Session) -> dict[str, str]:
    nomes: dict[str, str] = {}
    for tabela in (Historico, Usuarios):
        linhas = session.execute(select(tabela.nome, tabela.matricula).where(tabela.nome.is_not(None)))
        for nome, matricula in linhas:
            chave = " ".join(dobrar(nome).split())
            if len(chave.split()) >= 2:
                nomes.setdefault(chave, str(matricula))
    return nomes


def _parciais(nomes: dict[str, str]) -> dict[str, str | None]:
    """"Maria Santos" para "maria da silva santos": primeiro nome + cada sobrenome
    (sem partículas). Parcial de mais de um aluno fica None: sai da pergunta, mas
    não aponta para ninguém."""
    parciais: dict[str, str | None] = {}
    for nome, matricula in nomes.items():
        palavras = [p for p in nome.split() if p not in _PARTICULAS]
        for sobrenome in palavras[1:]:
            chave = f"{palavras[0]} {sobrenome}"
            if chave in nomes:
                continue
            parciais[chave] = matricula if parciais.get(chave, matricula) == matricula else None
    return parciais


def anonimizar(pergunta: str, nomes: dict[str, str]) -> Anonimizada:
    texto = " ".join(pergunta.split())
    marcadores: dict[str, str] = {}
    por_matricula: dict[str, str] = {}

    def marcar(matricula: str | None, chave: str) -> str:
        """Matrícula None (nome ambíguo): o marcador aponta para si mesmo, e o
        pipeline não o resolve para aluno nenhum."""
        chave_mapa = matricula or f"ambiguo:{chave}"
        if chave_mapa not in por_matricula:
            marcador = f"⟨A{len(por_matricula) + 1}⟩"
            por_matricula[chave_mapa] = marcador
            marcadores[marcador] = matricula or marcador
        return por_matricula[chave_mapa]

    texto = _DIGITOS_SEPARADOS.sub(lambda m: marcar(re.sub(r"\D", "", m.group()), ""), texto)
    texto = _DIGITOS.sub(lambda m: marcar(m.group(), ""), texto)
    dobrado = dobrar(texto)
    trechos: list[tuple[int, int, str]] = []
    # Nomes completos primeiro, do mais longo ao mais curto; depois os parciais.
    candidatos = [*sorted(nomes.items(), key=lambda i: len(i[0]), reverse=True),
                  *sorted(_parciais(nomes).items(), key=lambda i: len(i[0]), reverse=True)]
    for nome, matricula in candidatos:
        for achado in re.finditer(rf"(?<!\w){re.escape(nome)}(?!\w)", dobrado):
            if not any(achado.start() < fim and inicio < achado.end() for inicio, fim, _ in trechos):
                trechos.append((achado.start(), achado.end(), marcar(matricula, nome)))
    for inicio, fim, marcador in sorted(trechos, reverse=True):
        texto = texto[:inicio] + marcador + texto[fim:]
    return Anonimizada(texto, marcadores)


def restaurar(texto: str, marcadores: dict[str, str]) -> str:
    return _MARCADOR.sub(lambda m: marcadores.get(m.group(), m.group()), texto)
