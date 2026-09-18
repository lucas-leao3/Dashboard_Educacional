"""Fechar um lote (docs/governanca_dados.md, seções 3.3 e 5): selar os
insumos com SHA256SUMS e lote.md em raw/lotes/<id>/, gerar os derivados
vigente.csv e correspondencia.csv em processed/<id>/, e carimbar
lote.fechado_em. Depois disso o lote não recebe insumo nem se reabre.

Era o `fechar` de scripts/lote.py; veio para a API para que uma interface
consiga fechar um lote sem depender de script no host."""
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
    arquivos: list[tuple[str, str]],
) -> None:
    linhas = [f"# Lote {lote.id}", ""]
    linhas.append(f"- Períodos cobertos: {', '.join(lote.periodos_cobertos.split(';'))}")
    linhas.append(f"- Executado por: {lote.executado_por or 'não informado'}")
    linhas.append(f"- Executado em: {lote.executado_em.isoformat()}")
    if lote.observacao:
        linhas.append(f"- Observação: {lote.observacao}")
    linhas.append("")

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


def correspondencia(alunos: list[AlunoOut], excecoes: list[Excecao]) -> list[dict]:
    """Uma linha por matrícula: tem acadêmico? tem socioeconômico? O que falta?
    Quem está em aluno_vigente tem os dois, salvo exceção que diga o contrário.
    É a fonte tanto do correspondencia.csv quanto de GET /lotes/{id}/correspondencia."""
    info: dict[int, dict] = {}
    for aluno in alunos:
        registro = info.setdefault(aluno.matricula, {"nome": None, "academico": True, "socio": True})
        if aluno.nome:
            registro["nome"] = aluno.nome
    for excecao in excecoes:
        if excecao.matricula is None:
            continue
        registro = info.setdefault(excecao.matricula, {"nome": None, "academico": True, "socio": True})
        if excecao.motivo == "sem_academico":
            registro["academico"] = False
        elif excecao.motivo == "sem_socioeconomico":
            registro["socio"] = False

    linhas = []
    for matricula in sorted(info):
        registro = info[matricula]
        academico_ok, socio_ok = registro["academico"], registro["socio"]
        if academico_ok and socio_ok:
            faltando = ""
        elif not academico_ok and not socio_ok:
            faltando = "Ambos"
        elif not academico_ok:
            faltando = "Academico"
        else:
            faltando = "SocioEconomico"
        linhas.append({
            "matricula": matricula, "nome": registro["nome"],
            "academico": academico_ok, "socioeconomico": socio_ok, "faltando": faltando,
        })
    return linhas


def _escrever_correspondencia_csv(caminho: Path, linhas: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["Matricula", "Nome", "Academico", "SocioEconomico", "Dado_Faltando"])
        for l in linhas:
            escritor.writerow([
                l["matricula"], l["nome"] or "",
                "Sim" if l["academico"] else "Não", "Sim" if l["socioeconomico"] else "Não", l["faltando"],
            ])


def _alunos_e_excecoes(session: Session, lote_id: str) -> tuple[list[AlunoOut], list[Excecao]]:
    excecoes = session.execute(
        select(Excecao).join(Ingestao, Ingestao.id == Excecao.ingestao_id).where(Ingestao.lote_id == lote_id)
    ).scalars().all()
    alunos = [
        AlunoOut.model_validate(linha)
        for linha in session.execute(
            select(aluno_vigente).order_by(aluno_vigente.c.matricula, aluno_vigente.c.periodo)
        ).all()
    ]
    return alunos, list(excecoes)


def correspondencia_do_lote(session: Session, lote_id: str) -> list[dict]:
    alunos, excecoes = _alunos_e_excecoes(session, lote_id)
    return correspondencia(alunos, excecoes)


def exigir_aberto(lote: Lote) -> None:
    if lote.fechado_em is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Lote '{lote.id}' está fechado desde {lote.fechado_em.isoformat()}. Lote fechado não se reabre; abra outro.",
        )


def fechar_lote(session: Session, lote: Lote) -> list[Path]:
    """Sela o lote e devolve os caminhos gerados, na ordem: SHA256SUMS,
    lote.md, vigente.csv, correspondencia.csv."""
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
    alunos, excecoes = _alunos_e_excecoes(session, lote.id)

    raiz = caminho_do_lote(lote.id)
    arquivos = _gerar_sha256sums(raiz)
    _escrever_lote_md(raiz, lote, ingestoes, por_motivo, arquivos)

    processada = caminho_processado(lote.id)
    processada.mkdir(parents=True, exist_ok=True)
    _escrever_vigente_csv(processada / "vigente.csv", alunos)
    _escrever_correspondencia_csv(processada / "correspondencia.csv", correspondencia(alunos, excecoes))

    lote.fechado_em = datetime.now(timezone.utc)
    session.commit()
    session.refresh(lote)  # a resposta mostra o que o banco guardou, não o objeto em memória
    return [raiz / "SHA256SUMS", raiz / "lote.md", processada / "vigente.csv", processada / "correspondencia.csv"]
