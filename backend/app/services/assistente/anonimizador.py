"""Tira da pergunta o que identifica aluno antes de ela sair para o LLM (spec, D2).

Matrícula (qualquer sequência de 9+ dígitos) e nome da base (2+ palavras,
comparado sem caixa e sem acento) viram marcadores ⟨A1⟩, ⟨A2⟩... O mapa fica
na requisição; o LLM usa o marcador como valor do filtro `matricula` e o
pipeline troca de volta. Nome de uma palavra só fica de fora de propósito:
casaria com palavra comum da pergunta.
"""
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import Historico, Usuarios

_DIGITOS = re.compile(r"\d{9,}")
_MARCADOR = re.compile(r"⟨A\d+⟩")


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


def anonimizar(pergunta: str, nomes: dict[str, str]) -> Anonimizada:
    texto = " ".join(pergunta.split())
    marcadores: dict[str, str] = {}
    por_matricula: dict[str, str] = {}

    def marcar(matricula: str) -> str:
        if matricula not in por_matricula:
            por_matricula[matricula] = f"⟨A{len(por_matricula) + 1}⟩"
            marcadores[por_matricula[matricula]] = matricula
        return por_matricula[matricula]

    texto = _DIGITOS.sub(lambda m: marcar(m.group()), texto)
    dobrado = dobrar(texto)
    trechos: list[tuple[int, int, str]] = []
    for nome in sorted(nomes, key=len, reverse=True):  # o nome mais longo ganha
        for achado in re.finditer(rf"(?<!\w){re.escape(nome)}(?!\w)", dobrado):
            if not any(achado.start() < fim and inicio < achado.end() for inicio, fim, _ in trechos):
                trechos.append((achado.start(), achado.end(), marcar(nomes[nome])))
    for inicio, fim, marcador in sorted(trechos, reverse=True):
        texto = texto[:inicio] + marcador + texto[fim:]
    return Anonimizada(texto, marcadores)


def restaurar(texto: str, marcadores: dict[str, str]) -> str:
    return _MARCADOR.sub(lambda m: marcadores.get(m.group(), m.group()), texto)
