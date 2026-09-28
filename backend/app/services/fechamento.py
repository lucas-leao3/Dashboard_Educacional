"""Fechar um lote (docs/governanca_simplificada.md): selar os insumos com
SHA256SUMS e lote.md em raw/lotes/<id>/, gerar os derivados vigente.csv,
integrados.csv e nao_integrados.csv em processed/<id>/, e carimbar
lote.fechado_em. Depois disso o lote é imutável.

Não é mais uma ação do usuário: é a última etapa da importação
(app.services.importacao), na mesma transação que gravou os dados."""
import csv
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import config
from app.db.engine import Excecao, Ingestao, Lote
from app.db.vigente import aluno_vigente
from app.schemas.alunos import AlunoOut
from app.services.lotes import caminho_do_lote, sha256_de
from app.services.relatorio import MOTIVOS, relatorio_do_lote

PASSOS_OBRIGATORIOS = {Ingestao.PASSO_SINCRONIZAR, Ingestao.PASSO_CRG}

COLUNAS_VIGENTE = list(AlunoOut.model_fields)

TEXTO_LIMITACOES = (
    "Campos que o levantamento socioeconômico manual (`DadosAgrupados.csv`) "
    "preenchia e a API do FasiTech não traz ficam `NULL` neste lote. Nome e "
    "data de nascimento continuam vindo do histórico em PDF (passo 2). É "
    "limitação declarada da fonte de dados, não defeito da execução deste lote."
)


def caminho_processado(lote_id: str) -> Path:
    return config.RAIZ_PROCESSADA / lote_id


def _gerar_sha256sums(raiz: Path) -> list[tuple[str, str]]:
    """Hash de todo arquivo em `raiz`, exceto SHA256SUMS e lote.md. Devolve
    [(caminho_relativo, hash)] ordenado, e grava o arquivo SHA256SUMS."""
    excluidos = {raiz / "SHA256SUMS", raiz / "lote.md"}
    arquivos = sorted(p for p in raiz.rglob("*") if p.is_file() and p not in excluidos)
    linhas = []
    with open(raiz / "SHA256SUMS", "w", encoding="utf-8") as saida:
        for arquivo in arquivos:
            relativo = arquivo.relative_to(raiz).as_posix()
            hash_ = sha256_de(arquivo)
            linhas.append((relativo, hash_))
            saida.write(f"{hash_}  {relativo}\n")
    return linhas


def _escrever_lote_md(
    raiz: Path, lote: Lote, ingestoes: list[Ingestao], excecoes_por_motivo: dict[str, int],
    arquivos: list[tuple[str, str]], resumo: dict,
) -> None:
    linhas = [f"# Lote {lote.id}", ""]
    linhas.append(f"- Responsável: {lote.executado_por or 'não informado'}")
    linhas.append(f"- Período (extraído dos históricos): {', '.join(lote.periodos_cobertos.split(';'))}")
    linhas.append(f"- Executado em: {lote.executado_em.isoformat()}")
    if lote.observacao:
        linhas.append(f"- Observação: {lote.observacao}")
    linhas.append("")

    linhas += ["## Integração", "", "| Situação | Alunos |", "|---|---|"]
    linhas.append(f"| Integrados (acadêmico + socioeconômico) | {resumo['integrados']} |")
    for codigo, n in sorted(resumo["por_motivo"].items()):
        linhas.append(f"| Não integrado: {MOTIVOS[codigo]} | {n} |")
    media = resumo["preenchimento_medio_integrados"]
    linhas += ["", f"Preenchimento médio dos integrados: {'—' if media is None else f'{media}%'}.",
               "Só os integrados entram nos dashboards.", ""]

    linhas += ["## Ingestões", "", "| Passo | Executado em | Lidos | Aceitos | Rejeitados |", "|---|---|---|---|---|"]
    for i in ingestoes:
        linhas.append(
            f"| {i.passo} | {i.executado_em.isoformat()} | {i.registros_lidos} "
            f"| {i.registros_aceitos} | {i.registros_rejeitados} |"
        )
    linhas.append("")

    linhas += ["## Exceções por motivo", ""]
    if excecoes_por_motivo:
        linhas += ["| Motivo | Quantidade |", "|---|---|"]
        linhas += [f"| {motivo} | {n} |" for motivo, n in excecoes_por_motivo.items()]
    else:
        linhas.append("Nenhuma.")
    linhas.append("")

    linhas += ["## Arquivos (SHA256)", "", "| Arquivo | SHA256 |", "|---|---|"]
    linhas += [f"| {relativo} | {hash_} |" for relativo, hash_ in arquivos]
    linhas.append("")

    linhas += ["## Limitações", "", TEXTO_LIMITACOES, ""]
    (raiz / "lote.md").write_text("\n".join(linhas), encoding="utf-8")


def _escrever_vigente_csv(caminho: Path, alunos: list[AlunoOut]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_VIGENTE)
        escritor.writeheader()
        for aluno in alunos:
            escritor.writerow(aluno.model_dump())


def _lista_campos(linha: dict) -> str:
    return "; ".join(linha["campos_sem_resposta"]) or "nenhum"


def _percentual(linha: dict) -> str:
    return "" if linha["percentual_preenchimento"] is None else str(linha["percentual_preenchimento"])


def _escrever_integrados_csv(caminho: Path, linhas: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["Matricula", "Nome", "Academico", "SocioEconomico", "Status",
                           "Qtd_campos_sem_resposta", "Campos_sem_resposta", "Percentual_preenchimento"])
        for l in linhas:
            escritor.writerow([l["matricula"], l["nome"] or "", "Sim", "Sim", l["status"],
                               l["qtd_campos_sem_resposta"], _lista_campos(l), _percentual(l)])


def _escrever_nao_integrados_csv(caminho: Path, linhas: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["Matricula", "Nome", "Academico", "SocioEconomico", "Motivo", "Detalhe",
                           "Qtd_campos_sem_resposta", "Campos_sem_resposta", "Percentual_preenchimento"])
        for l in linhas:
            escritor.writerow([
                "" if l["matricula"] is None else l["matricula"], l["nome"] or "",
                "Sim" if l["academico"] else "Não", "Sim" if l["socioeconomico"] else "Não",
                l["motivo_descricao"], l["detalhe"] or "",
                l["qtd_campos_sem_resposta"], _lista_campos(l), _percentual(l),
            ])


def _alunos_vigentes(session: Session) -> list[AlunoOut]:
    return [
        AlunoOut.model_validate(linha)
        for linha in session.execute(
            select(aluno_vigente).order_by(aluno_vigente.c.matricula, aluno_vigente.c.periodo)
        ).all()
    ]


def exigir_aberto(lote: Lote) -> None:
    if lote.fechado_em is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Lote '{lote.id}' está fechado desde {lote.fechado_em.isoformat()}. Lote fechado não se altera; faça uma nova importação.",
        )


def fechar_lote(session: Session, lote: Lote) -> list[Path]:
    """Sela o lote e devolve os caminhos gerados, na ordem: SHA256SUMS,
    lote.md, vigente.csv, integrados.csv, nao_integrados.csv."""
    exigir_aberto(lote)
    ingestoes = session.execute(
        select(Ingestao).where(Ingestao.lote_id == lote.id).order_by(Ingestao.passo)
    ).scalars().all()
    faltando = PASSOS_OBRIGATORIOS - {i.passo for i in ingestoes}
    if faltando:
        raise HTTPException(
            status_code=409,
            detail=f"Lote '{lote.id}' ainda não executou os passos {sorted(faltando)}. Rode-os antes de fechar.",
        )

    por_motivo = dict(session.execute(
        select(Excecao.motivo, func.count())
        .join(Ingestao, Ingestao.id == Excecao.ingestao_id)
        .where(Ingestao.lote_id == lote.id)
        .group_by(Excecao.motivo)
    ).all())
    relatorio = relatorio_do_lote(session, lote.id)

    raiz = caminho_do_lote(lote.id)
    arquivos = _gerar_sha256sums(raiz)
    _escrever_lote_md(raiz, lote, ingestoes, por_motivo, arquivos, relatorio["resumo"])

    processada = caminho_processado(lote.id)
    processada.mkdir(parents=True, exist_ok=True)
    _escrever_vigente_csv(processada / "vigente.csv", _alunos_vigentes(session))
    _escrever_integrados_csv(processada / "integrados.csv", relatorio["integrados"])
    _escrever_nao_integrados_csv(processada / "nao_integrados.csv", relatorio["nao_integrados"])

    lote.fechado_em = datetime.now(timezone.utc)
    session.commit()
    session.refresh(lote)  # a resposta mostra o que o banco guardou, não o objeto em memória
    return [
        raiz / "SHA256SUMS", raiz / "lote.md", processada / "vigente.csv",
        processada / "integrados.csv", processada / "nao_integrados.csv",
    ]
