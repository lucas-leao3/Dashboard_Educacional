"""Consulta de lotes e o que o fechamento deixa em disco.

O fechamento não é mais rota: é a última etapa de POST /lotes/importar
(tests/test_importacao.py). Aqui se confere o que ele produz.
"""
import csv
import hashlib

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core import config
from app.db.engine import Excecao, Ingestao
from app.schemas.alunos import AlunoOut
from conftest import historico, zip_de


async def test_listar_e_buscar_lote(client, lote):
    lista = await client.get("/lotes")
    assert [l["id"] for l in lista.json()] == [lote]
    um = await client.get(f"/lotes/{lote}")
    assert um.status_code == 200
    assert um.json()["periodos_cobertos"] == ["2025.2"]
    assert (await client.get("/lotes/L99")).status_code == 404


async def test_listar_excecoes_ordenada_por_passo_matricula_periodo(client, lote, db_engine):
    SessionTeste = sessionmaker(bind=db_engine)
    with SessionTeste() as session:
        ing2 = Ingestao(lote_id=lote, passo=2)
        ing1 = Ingestao(lote_id=lote, passo=1)
        session.add_all([ing1, ing2])
        session.flush()
        session.add_all([
            Excecao(ingestao_id=ing2.id, matricula=100, periodo="2026.1", motivo="sem_academico"),
            Excecao(ingestao_id=ing1.id, matricula=200, periodo="2025.2", motivo="sem_periodo", detalhe="periodo: missing"),
            Excecao(ingestao_id=ing1.id, matricula=100, periodo="2026.1", motivo="matricula_invalida"),
        ])
        session.commit()

    resposta = await client.get(f"/lotes/{lote}/excecoes")
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert [(e["passo"], e["matricula"], e["periodo"]) for e in corpo] == [
        (1, 100, "2026.1"),
        (1, 200, "2025.2"),
        (2, 100, "2026.1"),
    ]
    assert corpo[1]["detalhe"] == "periodo: missing"
    assert corpo[1]["motivo"] == "sem_periodo"


async def test_listar_excecoes_de_lote_inexistente_da_404(client):
    assert (await client.get("/lotes/L99/excecoes")).status_code == 404


async def test_relatorio_de_lote_inexistente_da_404(client):
    assert (await client.get("/lotes/L99/relatorio")).status_code == 404


# ---------------------------------------------------------------------------
# Fechamento: SHA256SUMS, lote.md e CSVs
# ---------------------------------------------------------------------------

@pytest.fixture()
async def importado(importar, fontes):
    """Um lote importado com os três casos: 100 integrado, 200 só
    socioeconômico, 300 só histórico. Devolve o corpo da resposta."""
    fontes.fasitech = [
        {"matricula": 100, "periodo": "2026.1", "genero": "Feminino", "renda": "Até 1 salário mínimo"},
        {"matricula": 200, "periodo": "2026.1", "genero": "Masculino"},
    ]
    fontes.historicos = {
        "h100": historico(100, {"2025.1": 8.5}, nome="Ana"),
        "h300": historico(300, {"2025.1": 6.0}, nome="Caio"),
    }
    resposta = await importar(zip_de(["h100.pdf", "h300.pdf"]))
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def _csv(caminho) -> list[dict]:
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def test_sha256sums_cobre_os_insumos_e_confere(importado):
    raiz = config.RAIZ_LOTES / importado["id"]
    linhas = (raiz / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    caminhos = sorted(l.split("  ", 1)[1] for l in linhas)
    assert caminhos == ["fasitech.json", "historicos/h100.pdf", "historicos/h300.pdf"]
    for linha in linhas:
        hash_esperado, caminho = linha.split("  ", 1)
        assert hashlib.sha256((raiz / caminho).read_bytes()).hexdigest() == hash_esperado


async def test_lote_md_registra_responsavel_periodo_e_integracao(importado):
    conteudo = (config.RAIZ_LOTES / importado["id"] / "lote.md").read_text(encoding="utf-8")
    assert f"# Lote {importado['id']}" in conteudo
    assert "- Responsável: Edinaldo" in conteudo
    assert "- Período (extraído dos históricos): 2025.2" in conteudo
    assert "| Integrados (acadêmico + socioeconômico) | 1 |" in conteudo
    assert "| Não integrado: Possui socioeconômico e não possui acadêmico | 1 |" in conteudo
    assert "| Não integrado: Possui acadêmico e não possui socioeconômico | 1 |" in conteudo
    assert "historicos/h100.pdf" in conteudo
    assert "## Limitações" in conteudo


async def test_arquivos_gerados_na_ordem(importado):
    lote_id = importado["id"]
    assert importado["arquivos_gerados"] == [
        str(config.RAIZ_LOTES / lote_id / "SHA256SUMS"),
        str(config.RAIZ_LOTES / lote_id / "lote.md"),
        str(config.RAIZ_PROCESSADA / lote_id / "vigente.csv"),
        str(config.RAIZ_PROCESSADA / lote_id / "integrados.csv"),
        str(config.RAIZ_PROCESSADA / lote_id / "nao_integrados.csv"),
    ]


async def test_vigente_csv_tem_as_colunas_de_alunoout(importado):
    caminho = config.RAIZ_PROCESSADA / importado["id"] / "vigente.csv"
    with open(caminho, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        assert leitor.fieldnames == list(AlunoOut.model_fields)
        linhas = list(leitor)
    assert [l["matricula"] for l in linhas] == ["100", "200"]
    assert linhas[0]["CRG"] == "8.5"


async def test_integrados_csv_com_status_e_completude(importado):
    [linha] = _csv(config.RAIZ_PROCESSADA / importado["id"] / "integrados.csv")
    assert (linha["Matricula"], linha["Nome"], linha["Academico"], linha["SocioEconomico"]) == ("100", "Ana", "Sim", "Sim")
    assert linha["Status"] == "Integrado com sucesso"
    # 13 campos do questionário menos tipo_deficiencia (pcd não é "Sim") + CRG = 13 avaliados;
    # respondidos: CRG, genero, renda.
    assert linha["Qtd_campos_sem_resposta"] == "10"
    assert "cor_etnia" in linha["Campos_sem_resposta"] and "renda" not in linha["Campos_sem_resposta"]
    assert linha["Percentual_preenchimento"] == "23.1"


async def test_nao_integrados_csv_com_motivo_e_completude(importado):
    linhas = {l["Matricula"]: l for l in _csv(config.RAIZ_PROCESSADA / importado["id"] / "nao_integrados.csv")}
    assert set(linhas) == {"200", "300"}
    assert (linhas["200"]["Academico"], linhas["200"]["SocioEconomico"]) == ("Não", "Sim")
    assert linhas["200"]["Motivo"] == "Possui socioeconômico e não possui acadêmico"
    assert (linhas["300"]["Academico"], linhas["300"]["SocioEconomico"]) == ("Sim", "Não")
    assert linhas["300"]["Motivo"] == "Possui acadêmico e não possui socioeconômico"
    assert linhas["300"]["Nome"] == "Caio"           # nome vem do histórico
    assert linhas["300"]["Campos_sem_resposta"] == "nenhum"
    assert linhas["300"]["Percentual_preenchimento"] == "100.0"


async def test_falha_depois_de_gravar_arquivos_desfaz_banco_e_disco(importar, fontes, db_engine):
    """O fechamento escreve em disco antes do COMMIT. Se o COMMIT falhar, a
    pasta raw e a processed também têm que sumir -- senão sobra lote em
    disco sem registro no banco.

    Usa um pytest.MonkeyPatch próprio (não o fixture `monkeypatch`, que é
    compartilhado com o fixture `client` -- um `.undo()` nele desfaria
    também o RAIZ_LOTES apontando pro tmp_path)."""
    fontes.fasitech = [{"matricula": 100, "periodo": "2026.1"}]
    fontes.historicos = {"h100": historico(100, {"2025.1": 8.5})}

    def commit_explode(self):
        raise RuntimeError("falha sintética de commit")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(Session, "commit", commit_explode)
        with pytest.raises(RuntimeError):
            await importar(zip_de(["h100.pdf"]))

    assert not any(config.RAIZ_LOTES.iterdir())
    assert not config.RAIZ_PROCESSADA.exists() or not any(config.RAIZ_PROCESSADA.iterdir())
    with Session(db_engine) as s:
        assert s.execute(Ingestao.__table__.select()).first() is None
