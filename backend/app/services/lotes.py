"""Operações comuns a todo lote (docs/governanca_dados.md, seções 3 e 5):
diretório em raw/lotes/<id>/, hash dos insumos, abertura e fechamento de
ingestão, registro de exceção. As rotas usam isto em vez de repetir."""
import hashlib
import io
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.db.engine import ArquivoFonte, Excecao, Ingestao, Lote

# Teto do que um envio de históricos pode expandir em disco (zip descomprimido
# incluso). Os 56 PDFs do L01 somam poucos MB; 100 MB é folga, não meta.
LIMITE_BYTES_HISTORICOS = 100 * 1024 * 1024


def caminho_do_lote(lote_id: str) -> Path:
    # Lido em tempo de chamada, não no import: os testes trocam config.RAIZ_LOTES.
    return config.RAIZ_LOTES / lote_id


def criar_diretorio(lote_id: str) -> Path:
    caminho = caminho_do_lote(lote_id)
    (caminho / "historicos").mkdir(parents=True, exist_ok=False)
    return caminho


def sha256_de(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def registrar_arquivo(session: Session, lote_id: str, caminho: Path, tipo: str) -> ArquivoFonte | None:
    """Registra o arquivo em arquivo_fonte. Devolve None se o mesmo conteúdo
    (mesmo hash) já entrou -- em qualquer lote."""
    sha = sha256_de(caminho)
    if session.get(ArquivoFonte, sha) is not None:
        return None
    registro = ArquivoFonte(
        sha256=sha,
        lote_id=lote_id,
        nome_original=caminho.name,
        tipo=tipo,
        tamanho_bytes=caminho.stat().st_size,
    )
    session.add(registro)
    session.flush()
    return registro


def proximo_id(session: Session, hoje: date) -> str:
    """AAAA-MM-Lnn do mês de `hoje`; nn = maior sequência do mês + 1, olhando
    o banco E o disco -- uma pasta órfã em raw/lotes/ também ocupa o número."""
    prefixo = f"{hoje.year}-{hoje.month:02d}-L"
    ids = set(session.execute(select(Lote.id).where(Lote.id.like(f"{prefixo}%"))).scalars())
    if config.RAIZ_LOTES.exists():
        ids |= {p.name for p in config.RAIZ_LOTES.iterdir() if p.name.startswith(prefixo)}
    sequencias = [int(i[len(prefixo):]) for i in ids if i[len(prefixo):].isdigit()]
    return f"{prefixo}{max(sequencias, default=0) + 1:02d}"


def abrir_ingestao(session: Session, lote_id: str, passo: int, arquivo_sha256: str | None = None) -> Ingestao:
    """Uma ingestão por passo por lote (o banco garante: ux_ingestao_lote_passo)."""
    ingestao = Ingestao(lote_id=lote_id, passo=passo, arquivo_sha256=arquivo_sha256)
    session.add(ingestao)
    session.flush()
    return ingestao


def fechar_ingestao(session: Session, ingestao: Ingestao, lidos: int, aceitos: int, rejeitados: int) -> None:
    ingestao.registros_lidos += lidos
    ingestao.registros_aceitos += aceitos
    ingestao.registros_rejeitados += rejeitados
    # flush, não commit: a importação inteira é uma transação só, que o
    # fechamento do lote confirma (app.services.importacao).
    session.flush()


def registrar_excecao(
    session: Session,
    ingestao: Ingestao,
    motivo: str,
    matricula: int | None = None,
    periodo: str | None = None,
    detalhe: str | None = None,
) -> None:
    session.add(Excecao(ingestao_id=ingestao.id, matricula=matricula, periodo=periodo, motivo=motivo, detalhe=detalhe))


def _excesso() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"Envio passa de {LIMITE_BYTES_HISTORICOS // (1024 * 1024)} MB descomprimidos; divida em mais de um envio.",
    )


def _desempacotar(nome: str, conteudo: bytes, ignorados: list[str]) -> Iterator[tuple[str, bytes]]:
    """Um upload vira PDFs (nome, bytes), um por vez. Um .zip é aberto e só
    as entradas .pdf saem, pelo nome-base (sem subpasta -- também elimina
    '../'). Lixo como __MACOSX/ e Thumbs.db vai para `ignorados`, não
    derruba o envio. O tamanho declarado de cada entrada é checado ANTES de
    descomprimir, senão o teto não protege de zip-bomb."""
    if nome.lower().endswith(".pdf"):
        yield nome, conteudo
        return
    if not nome.lower().endswith(".zip"):
        ignorados.append(nome)
        return
    try:
        z = zipfile.ZipFile(io.BytesIO(conteudo))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail=f"'{nome}' não é um zip válido.")
    with z:
        for entrada in z.infolist():
            if entrada.is_dir():
                continue
            base = Path(entrada.filename).name
            if not base.lower().endswith(".pdf") or base.startswith("._"):
                ignorados.append(entrada.filename)
                continue
            if entrada.file_size > LIMITE_BYTES_HISTORICOS:
                raise _excesso()
            yield base, z.read(entrada)


def gravar_historicos(lote_id: str, arquivos: list[tuple[str, bytes]]) -> dict[str, list[str]]:
    """Grava os PDFs recebidos (soltos ou dentro de .zip) em
    <lote>/historicos/. A extensão é normalizada para '.pdf' minúsculo:
    o passo 2 faz glob("*.pdf"), sensível a maiúsculas em Linux.

    Nome repetido (na pasta ou no próprio envio): mesmo conteúdo ->
    `ja_existiam`; conteúdo diferente -> 409 antes de gravar qualquer coisa,
    porque insumo de lote não se sobrescreve."""
    destino = caminho_do_lote(lote_id) / "historicos"
    resultado: dict[str, list[str]] = {"gravados": [], "ja_existiam": [], "ignorados": []}
    a_gravar: list[tuple[str, bytes]] = []
    pendentes: dict[str, bytes] = {}
    conflitos: list[str] = []
    total = 0
    for nome, conteudo in arquivos:
        for nome_pdf, bytes_pdf in _desempacotar(nome, conteudo, resultado["ignorados"]):
            total += len(bytes_pdf)
            if total > LIMITE_BYTES_HISTORICOS:
                raise _excesso()
            nome_final = Path(nome_pdf).stem + ".pdf"
            existente = destino / nome_final
            # O mesmo nome pode vir duas vezes no mesmo zip (subpastas
            # diferentes achatadas): sem isto o segundo sobrescreveria o
            # primeiro sem aviso.
            anterior = pendentes.get(nome_final)
            if anterior is None and existente.exists():
                anterior = existente.read_bytes()
            if anterior is None:
                pendentes[nome_final] = bytes_pdf
                a_gravar.append((nome_final, bytes_pdf))
            elif anterior == bytes_pdf:
                resultado["ja_existiam"].append(nome_final)
            else:
                conflitos.append(nome_final)
    if conflitos:
        raise HTTPException(
            status_code=409,
            detail=f"Mais de um histórico com o mesmo nome e conteúdo diferente: {', '.join(conflitos)}. "
                   "Renomeie ou remova a duplicata do .zip.",
        )
    for nome_final, bytes_pdf in a_gravar:
        (destino / nome_final).write_bytes(bytes_pdf)
        resultado["gravados"].append(nome_final)
    return resultado
