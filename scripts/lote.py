#!/usr/bin/env python3
"""Importação de lote pela linha de comando (docs/governanca_simplificada.md).

Roda na máquina host, fora do container -- só fala com a API por HTTP. Não
importa nada de `app.*` de propósito: o script tem que funcionar mesmo que o
backend rode isolado dentro do Docker. Toda a escrita em disco (PDFs,
SHA256SUMS, lote.md, CSVs) é feita pela API; o script só envia e imprime.

Subcomandos:
  importar --responsavel NOME ARQUIVO   ARQUIVO é o .zip dos históricos (ou
                                        uma pasta de PDFs, que o script
                                        compacta antes de enviar)
  relatorio LOTE                        integrados e não integrados do lote
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

import httpx


def _detalhe_erro(resposta: httpx.Response) -> str:
    try:
        return str(resposta.json().get("detail", resposta.text))
    except ValueError:
        return resposta.text


def _conteudo_zip(caminho: Path) -> tuple[str, bytes] | None:
    """(nome, bytes) do .zip a enviar. Pasta -> zip em memória com os *.pdf
    dela (qualquer caixa). Outra coisa -> None."""
    if caminho.is_dir():
        pdfs = sorted(p for p in caminho.iterdir() if p.suffix.lower() == ".pdf")
        if not pdfs:
            return None
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for pdf in pdfs:
                z.write(pdf, pdf.name)
        return f"{caminho.name}.zip", buffer.getvalue()
    if caminho.suffix.lower() == ".zip" and caminho.is_file():
        return caminho.name, caminho.read_bytes()
    return None


def importar(client: httpx.Client, responsavel: str, caminho: Path) -> int:
    """POST /lotes/importar. A API cria o lote, processa, extrai o período e
    fecha -- ou não grava nada, se algo falhar."""
    arquivo = _conteudo_zip(caminho)
    if arquivo is None:
        print(f"Nada para enviar: {caminho} não é um .zip nem uma pasta com PDFs.", file=sys.stderr)
        return 1
    nome, conteudo = arquivo
    resposta = client.post(
        "/lotes/importar",
        data={"responsavel": responsavel},
        files={"arquivo": (nome, conteudo, "application/zip")},
    )
    if resposta.status_code >= 400:
        print(f"Importação recusada, nada foi gravado: {_detalhe_erro(resposta)}", file=sys.stderr)
        return 1
    corpo = resposta.json()
    resumo = corpo["resumo"]
    print(f"Lote '{corpo['id']}' importado e fechado em {corpo['fechado_em']}.")
    print(f"  Período (extraído dos históricos): {', '.join(corpo['periodos_cobertos'])}")
    print(f"  Históricos: gravados={len(corpo['arquivos']['gravados'])} ignorados={len(corpo['arquivos']['ignorados'])}")
    for ignorado in corpo["arquivos"]["ignorados"]:
        print(f"    ignorado: {ignorado}")
    print(f"  Integrados: {resumo['integrados']}  Não integrados: {resumo['nao_integrados']}")
    for motivo, n in sorted(resumo["por_motivo"].items()):
        print(f"    {motivo}: {n}")
    print("  Arquivos gerados (caminhos vistos pela API):")
    for gerado in corpo["arquivos_gerados"]:
        print(f"    {gerado}")
    return 0


def relatorio(client: httpx.Client, lote_id: str) -> int:
    resposta = client.get(f"/lotes/{lote_id}/relatorio")
    if resposta.status_code >= 400:
        print(f"Erro ao buscar o relatório do lote '{lote_id}': {_detalhe_erro(resposta)}", file=sys.stderr)
        return 1
    corpo = resposta.json()

    def campos(linha: dict) -> str:
        return ", ".join(linha["campos_sem_resposta"]) or "nenhum"

    print(f"Integrados ({len(corpo['integrados'])})")
    for l in corpo["integrados"]:
        print(f"  {l['matricula']}  {l['percentual_preenchimento']}%  sem resposta: {campos(l)}")
    print(f"Não integrados ({len(corpo['nao_integrados'])})")
    for l in corpo["nao_integrados"]:
        print(f"  {l['matricula'] or '—'}  {l['motivo_descricao']}  sem resposta: {campos(l)}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000", help="Base da API (padrão: %(default)s)")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_importar = sub.add_parser("importar", help="Importa um .zip de históricos num lote novo, já fechado")
    p_importar.add_argument("--responsavel", required=True, help="Nome de quem está importando")
    p_importar.add_argument("arquivo", type=Path, help=".zip dos históricos, ou pasta com os PDFs")

    p_relatorio = sub.add_parser("relatorio", help="Integrados e não integrados de um lote")
    p_relatorio.add_argument("id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # Importação lê PDFs e consulta o FasiTech numa chamada só: timeout folgado.
    with httpx.Client(base_url=args.api, timeout=300.0) as client:
        if args.comando == "importar":
            return importar(client, args.responsavel, args.arquivo)
        if args.comando == "relatorio":
            return relatorio(client, args.id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
