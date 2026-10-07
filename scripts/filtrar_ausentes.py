#!/usr/bin/env python3
"""Remove da lista de ausentes os alunos que já foram preenchidos.

O cruzamento é pela matrícula, não pelo nome: `alunos_ausentes_api.csv` vem
com a coluna `nome` vazia, e matrícula não sofre com acento/abreviação.

`preenchidos.csv` não tem cabeçalho; a matrícula é a primeira coluna
(matricula,nome,periodo,crg).

Uso:
  python scripts/filtrar_ausentes.py
  python scripts/filtrar_ausentes.py --ausentes A.csv --preenchidos P.csv --saida S.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AUSENTES = RAIZ / "data/processed/ausentes/alunos_ausentes_api.csv"
PREENCHIDOS = RAIZ / "data/preenchidos.csv"
SAIDA = RAIZ / "data/processed/ausentes/alunos_ausentes_pendentes.csv"


def matriculas_preenchidas(caminho: Path) -> set[str]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return {linha[0].strip() for linha in csv.reader(f) if linha and linha[0].strip()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ausentes", type=Path, default=AUSENTES)
    parser.add_argument("--preenchidos", type=Path, default=PREENCHIDOS)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args(argv)

    preenchidas = matriculas_preenchidas(args.preenchidos)

    with args.ausentes.open(encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        campos = leitor.fieldnames
        ausentes = list(leitor)

    pendentes = [a for a in ausentes if a["matricula"].strip() not in preenchidas]

    with args.saida.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(pendentes)

    removidos = len(ausentes) - len(pendentes)
    fora_da_lista = preenchidas - {a["matricula"].strip() for a in ausentes}
    print(f"ausentes: {len(ausentes)} | removidos: {removidos} | pendentes: {len(pendentes)}")
    print(f"gravado em {args.saida}")
    if fora_da_lista:
        print(f"aviso: {len(fora_da_lista)} matrícula(s) de preenchidos não estão na lista de ausentes:",
              ", ".join(sorted(fora_da_lista)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
