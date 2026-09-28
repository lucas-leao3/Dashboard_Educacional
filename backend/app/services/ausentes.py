"""Alunos que respondem ao FasiTech e ainda não estão na base integrada.

Uso (o banco não expõe porta; roda dentro do contêiner do backend):

    docker compose run --rm -v ./backend/app:/app/app backend \\
        python -m app.services.ausentes [--snapshot ARQ.json] [--saida ARQ.csv]

Sem --snapshot, consulta a API ao vivo (buscar_paginas, a mesma do passo 1).
Com --snapshot, lê um envelope congelado, ex.: /data/raw/lotes/<id>/fasitech.json.

**O que é "importado".** O sistema não importa CSV: o socioeconômico vem da
API do FasiTech (tabela `usuarios`) e o acadêmico dos PDFs de histórico
(`crg_semestre`); os CSVs em data/processed/ são derivados, e os de
backend/app/data/ são o levantamento manual abandonado. Importado aqui é o
mesmo critério da view `aluno_integrado` e do relatório do lote: matrícula
com linha em `usuarios` E em `crg_semestre`. Só essas duas tabelas são lidas,
para funcionar também em banco anterior à revisão c5e8a1f3d920.

Nome, polo e turma:
- nome: o FasiTech não manda (verificado em 187/187). O único nome é o do
  histórico em PDF, copiado para `usuarios.nome` no passo 2 -- quem não tem
  histórico sai sem nome, e o resumo diz quantos.
- polo: a tabela `polo` pelo código da matrícula, o mesmo nome do dashboard.
  O `polo` da API (quando vem, em outro vocabulário: "OEIRAS DO PARÁ") só
  cobre código que a tabela ainda não conhece.
- turma: ano de ingresso, os 4 primeiros dígitos (turma_da_matricula).
"""
import argparse
import csv
import json
import logging
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.db.engine import CrgSemestre, Polo, SessionLocal, Usuarios
from app.db.matricula import codigo_de_polo, digitos_da_matricula, turma_da_matricula
from app.services.fasitech_client import buscar_paginas, registros_do_envelope

COLUNAS = ("nome", "matricula", "polo", "turma")

log = logging.getLogger("ausentes")


def _texto(valor) -> str | None:
    """NFC e espaços colapsados; vazio vira None."""
    if valor is None:
        return None
    texto = " ".join(unicodedata.normalize("NFC", str(valor)).split())
    return texto or None


def alunos_do_fasitech(registros: list[dict]) -> tuple[dict[str, dict], int]:
    """Um aluno por matrícula -- o FasiTech manda uma linha por período.
    Devolve ({matricula: {"nome", "polo_api"}}, registros com matrícula
    inválida). Inválida não tem como ser comparada; fica só na contagem."""
    alunos: dict[str, dict] = {}
    invalidos = 0
    for registro in registros:
        matricula = digitos_da_matricula(registro.get("matricula"))
        if matricula is None:
            invalidos += 1
            continue
        aluno = alunos.setdefault(matricula, {"nome": None, "polo_api": None})
        aluno["nome"] = aluno["nome"] or _texto(registro.get("nome"))
        aluno["polo_api"] = aluno["polo_api"] or _texto(registro.get("polo"))
    return alunos, invalidos


def base_importada(session: Session) -> dict:
    """Matrículas de cada lado do cruzamento, nomes já gravados e polos."""
    socio = {str(m) for m in session.execute(select(Usuarios.matricula).distinct()).scalars()}
    academico = {str(m) for m in session.execute(select(CrgSemestre.matricula).distinct()).scalars()}
    nomes: dict[str, str] = {}
    for matricula, nome in session.execute(
        select(Usuarios.matricula, Usuarios.nome)
        .where(Usuarios.nome.is_not(None))
        .order_by(Usuarios.ingestao_id.desc(), Usuarios.id.desc())
    ):
        nomes.setdefault(str(matricula), nome)
    polos = dict(session.execute(select(Polo.codigo, Polo.nome)).all())
    return {"socioeconomico": socio, "academico": academico, "integradas": socio & academico,
            "nomes": nomes, "polos": polos}


def alunos_ausentes(fasitech: dict[str, dict], integradas: set[str],
                    nomes: dict[str, str], polos: dict[str, str]) -> list[dict]:
    """Linhas do relatório, ordenadas por matrícula (12 dígitos: ordem de
    texto = ordem numérica)."""
    linhas = []
    for matricula in sorted(fasitech.keys() - integradas):
        aluno = fasitech[matricula]
        linhas.append({
            "nome": _texto(aluno["nome"]) or _texto(nomes.get(matricula)) or "",
            "matricula": matricula,
            "polo": polos.get(codigo_de_polo(matricula)) or aluno["polo_api"] or "",
            "turma": turma_da_matricula(matricula) or "",
        })
    return linhas


def escrever_csv(caminho: Path, linhas: list[dict]) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: continua UTF-8, e o BOM faz o Excel abrir "Cametá" certo.
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    return caminho


def _registros(snapshot: Path | None) -> list[dict]:
    if snapshot is None:
        log.info("FasiTech: consultando a API ao vivo")
        return registros_do_envelope(buscar_paginas())
    log.info("FasiTech: lendo o envelope congelado %s", snapshot)
    return registros_do_envelope(json.loads(snapshot.read_text(encoding="utf-8")))


def executar(session: Session, snapshot: Path | None = None, saida: Path | None = None) -> dict:
    registros = _registros(snapshot)
    fasitech, invalidos = alunos_do_fasitech(registros)
    log.info("FasiTech: %d registros, %d alunos distintos, %d com matrícula inválida (ignorados)",
             len(registros), len(fasitech), invalidos)

    base = base_importada(session)
    log.info("Base importada: %d com socioeconômico, %d com acadêmico, %d integrados",
             len(base["socioeconomico"]), len(base["academico"]), len(base["integradas"]))

    linhas = alunos_ausentes(fasitech, base["integradas"], base["nomes"], base["polos"])
    sem_academico = {l["matricula"] for l in linhas} & base["socioeconomico"]
    resumo = {
        "fasitech_registros": len(registros),
        "fasitech_alunos": len(fasitech),
        "fasitech_matricula_invalida": invalidos,
        "base_integrados": len(base["integradas"]),
        "ausentes": len(linhas),
        "ausentes_sem_academico": len(sem_academico),
        "ausentes_fora_da_base": len(linhas) - len(sem_academico),
        "ausentes_sem_nome": sum(1 for l in linhas if not l["nome"]),
        "ausentes_sem_polo": sum(1 for l in linhas if not l["polo"]),
    }
    log.info("Ausentes: %d (%d sincronizados sem histórico acadêmico, %d fora da base: responderam "
             "ao FasiTech depois do último lote)",
             resumo["ausentes"], resumo["ausentes_sem_academico"], resumo["ausentes_fora_da_base"])
    if resumo["ausentes_sem_nome"]:
        log.warning("%d ausentes sem nome: o FasiTech não manda nome e eles não têm histórico em PDF",
                    resumo["ausentes_sem_nome"])
    if resumo["ausentes_sem_polo"]:
        log.warning("%d ausentes sem polo: código fora da tabela `polo` e a API não informou",
                    resumo["ausentes_sem_polo"])

    if saida is None:
        saida = config.RAIZ_PROCESSADA / "ausentes" / f"alunos_ausentes_{datetime.now():%Y%m%d-%H%M%S}.csv"
    resumo["arquivo"] = str(escrever_csv(saida, linhas))
    log.info("CSV gravado em %s", resumo["arquivo"])
    return resumo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--snapshot", type=Path, help="envelope congelado do FasiTech (fasitech.json de um lote)")
    parser.add_argument("--saida", type=Path, help="CSV de saída (padrão: <processed>/ausentes/alunos_ausentes_<data>.csv)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)

    with SessionLocal() as session:
        resumo = executar(session, snapshot=args.snapshot, saida=args.saida)

    print(f"Total de alunos no FasiTech:  {resumo['fasitech_alunos']}")
    print(f"Total de alunos na base:      {resumo['base_integrados']} (integrados: socioeconômico + acadêmico)")
    print(f"Total de alunos ausentes:     {resumo['ausentes']}")
    print(f"Arquivo gerado:               {resumo['arquivo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
