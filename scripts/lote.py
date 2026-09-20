#!/usr/bin/env python3
"""Operação de um lote de dados (docs/governanca_dados.md, docs/operacao_lote.md).

Roda na máquina host, fora do container -- só fala com a API por HTTP. Não
importa nada de `app.*` de propósito: o script tem que funcionar mesmo que o
backend rode isolado dentro do Docker. Toda a escrita em disco (PDFs,
SHA256SUMS, lote.md, CSVs) é feita pela API; o script só envia e imprime.

Subcomandos: abrir, enviar, rodar, fechar, executar (= abrir+enviar+rodar). Ver `python scripts/lote.py --help`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx


def raiz_do_lote(dados: Path, lote_id: str) -> Path:
    return dados / "raw" / "lotes" / lote_id


def _detalhe_erro(resposta: httpx.Response) -> str:
    try:
        return str(resposta.json().get("detail", resposta.text))
    except ValueError:
        return resposta.text


def abrir(client: httpx.Client, dados: Path, lote_id: str, periodos: list[str], por: str | None, obs: str | None,
          tolerar_existente: bool = False) -> int:
    resposta = client.post("/lotes", json={
        "id": lote_id,
        "periodos_cobertos": periodos,
        "executado_por": por,
        "observacao": obs,
    })
    if resposta.status_code == 409 and tolerar_existente:
        print(f"Lote '{lote_id}' já estava aberto, seguindo.")
        return 0
    if resposta.status_code >= 400:
        print(f"Erro ao abrir o lote '{lote_id}': {_detalhe_erro(resposta)}", file=sys.stderr)
        return 1
    caminho = raiz_do_lote(dados, lote_id) / "historicos"
    print(f"Lote '{lote_id}' aberto. Copie os PDFs em: {caminho}")
    return 0


def _arquivos_para_enviar(caminhos: list[Path]) -> list[Path]:
    """Pasta -> todos os *.pdf dela (qualquer caixa); .zip e .pdf soltos vão
    como estão. O resto é ignorado aqui mesmo, sem gastar upload."""
    arquivos: list[Path] = []
    for caminho in caminhos:
        if caminho.is_dir():
            arquivos.extend(sorted(p for p in caminho.iterdir() if p.suffix.lower() == ".pdf"))
        elif caminho.suffix.lower() in (".pdf", ".zip"):
            arquivos.append(caminho)
    return arquivos


def enviar(client: httpx.Client, lote_id: str, caminhos: list[Path]) -> int:
    arquivos = _arquivos_para_enviar(caminhos)
    if not arquivos:
        print(f"Nada para enviar: nenhum .pdf ou .zip em {', '.join(map(str, caminhos))}", file=sys.stderr)
        return 1
    partes = [("arquivos", (a.name, a.read_bytes(), "application/octet-stream")) for a in arquivos]
    resposta = client.post(f"/lotes/{lote_id}/historicos", files=partes)
    if resposta.status_code >= 400:
        print(f"Erro ao enviar históricos para o lote '{lote_id}': {_detalhe_erro(resposta)}", file=sys.stderr)
        return 1
    corpo = resposta.json()
    print(f"Históricos enviados: gravados={len(corpo['gravados'])} "
          f"ja_existiam={len(corpo['ja_existiam'])} ignorados={len(corpo['ignorados'])}")
    for nome in corpo["ignorados"]:
        print(f"  ignorado: {nome}")
    return 0


def _passos_executados(client: httpx.Client, lote_id: str) -> set[int] | None:
    resposta = client.get(f"/lotes/{lote_id}")
    if resposta.status_code >= 400:
        print(f"Erro ao consultar o lote '{lote_id}': {_detalhe_erro(resposta)}", file=sys.stderr)
        return None
    return {i["passo"] for i in resposta.json()["ingestoes"]}


def rodar(client: httpx.Client, lote_id: str) -> int:
    """Passo 1 e depois passo 2, pulando o que já executou: cada passo só
    roda uma vez por lote (409), então reexecutar depois de uma falha no
    passo 2 tem que ir direto a ele, sem bater no 409 do passo 1."""
    feitos = _passos_executados(client, lote_id)
    if feitos is None:
        return 1

    if 1 in feitos:
        print("Passo 1 (sincronizar): já executado, pulando.")
    else:
        resposta = client.post("/alunos/sincronizar", params={"lote": lote_id})
        if resposta.status_code >= 400:
            print(f"Erro no passo 1 (sincronizar) do lote '{lote_id}': {_detalhe_erro(resposta)}", file=sys.stderr)
            return 1
        corpo = resposta.json()
        print(f"Passo 1 (sincronizar): importados={corpo.get('importados')} rejeitados={corpo.get('rejeitados')}")

    if 2 in feitos:
        print("Passo 2 (atualizar-crg): já executado, pulando.")
        return 0
    resposta = client.post("/alunos/atualizar-crg", params={"lote": lote_id})
    if resposta.status_code >= 400:
        print(f"Erro no passo 2 (atualizar-crg) do lote '{lote_id}': {_detalhe_erro(resposta)}", file=sys.stderr)
        return 1
    corpo = resposta.json()
    contadores = ", ".join(f"{k}={v}" for k, v in corpo.items() if k not in ("lote", "ingestao_id"))
    print(f"Passo 2 (atualizar-crg): {contadores}")
    return 0


def executar(client: httpx.Client, dados: Path, lote_id: str, periodos: list[str], por: str | None,
             obs: str | None, historicos: list[Path]) -> int:
    """abrir -> enviar -> rodar, parando no primeiro erro. Seguro de repetir
    depois de uma falha: lote já aberto segue, PDF já enviado é idempotente,
    passo já executado é pulado. `fechar` fica de fora de propósito -- antes
    dele há a conferência do dashboard e do fasitech.json (operacao_lote.md)."""
    if abrir(client, dados, lote_id, periodos, por, obs, tolerar_existente=True) != 0:
        return 1
    if enviar(client, lote_id, historicos) != 0:
        return 1
    if rodar(client, lote_id) != 0:
        return 1
    print(f"Lote '{lote_id}' executado. Confira o dashboard e o fasitech.json; depois: lote.py fechar {lote_id}")
    return 0


def fechar(client: httpx.Client, lote_id: str) -> int:
    """POST /lotes/{id}/fechar. A API exige os passos 1 e 2, gera SHA256SUMS,
    lote.md, vigente.csv e correspondencia.csv, e carimba fechado_em. Lote
    fechado não se reabre -- a API recusa a segunda chamada."""
    resposta = client.post(f"/lotes/{lote_id}/fechar")
    if resposta.status_code >= 400:
        print(f"Erro ao fechar o lote '{lote_id}': {_detalhe_erro(resposta)}", file=sys.stderr)
        return 1
    corpo = resposta.json()
    print(f"Lote '{lote_id}' fechado em {corpo['fechado_em']}. Arquivos gerados (caminhos vistos pela API):")
    for caminho in corpo["arquivos_gerados"]:
        print(f"  {caminho}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000", help="Base da API (padrão: %(default)s)")
    parser.add_argument("--dados", default="./data", help="Raiz de dados montada pelo compose, só para imprimir caminhos (padrão: %(default)s)")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_abrir = sub.add_parser("abrir", help="Abre um lote novo (POST /lotes)")
    p_abrir.add_argument("id")
    p_abrir.add_argument("--periodos", nargs="+", required=True)
    p_abrir.add_argument("--por", default=None)
    p_abrir.add_argument("--obs", default=None)

    p_enviar = sub.add_parser("enviar", help="Envia históricos (pasta com PDFs, .zip ou PDFs soltos) para o lote")
    p_enviar.add_argument("id")
    p_enviar.add_argument("historicos", nargs="+", type=Path)

    p_rodar = sub.add_parser("rodar", help="Roda sincronizar + atualizar-crg (pula passo já executado)")
    p_rodar.add_argument("id")

    p_exec = sub.add_parser("executar", help="abrir + enviar + rodar de uma vez; fechar continua à parte")
    p_exec.add_argument("id")
    p_exec.add_argument("--periodos", nargs="+", required=True)
    p_exec.add_argument("--historicos", nargs="+", required=True, type=Path)
    p_exec.add_argument("--por", default=None)
    p_exec.add_argument("--obs", default=None)

    p_fechar = sub.add_parser("fechar", help="Fecha o lote via API: SHA256SUMS, lote.md, vigente.csv, correspondencia.csv")
    p_fechar.add_argument("id")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    dados = Path(args.dados)
    with httpx.Client(base_url=args.api, timeout=60.0) as client:
        if args.comando == "abrir":
            return abrir(client, dados, args.id, args.periodos, args.por, args.obs)
        if args.comando == "enviar":
            return enviar(client, args.id, args.historicos)
        if args.comando == "rodar":
            return rodar(client, args.id)
        if args.comando == "executar":
            return executar(client, dados, args.id, args.periodos, args.por, args.obs, args.historicos)
        if args.comando == "fechar":
            return fechar(client, args.id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
