# Implementação da governança por lote — design

Spec de implementação do que `docs/governanca_dados.md` decide. Este arquivo não repete o modelo de dados nem o fluxo — cobre só o que a governança deixa em aberto para quem vai codar: banco, container, contratos das rotas, testes e o que fica de fora.

Data: 2026-09-12. Spec de referência: `docs/governanca_dados.md` (seções 3.1, 3.2, 4, 5, 7).

---

## 1. Objetivo

Antes do L02 (próxima rodada, fim do semestre), o backend precisa:

1. Guardar cada rodada como **lote** com insumos congelados em disco (`raw/lotes/<id>/`).
2. Nunca sobrescrever: `usuarios` append-only, `aluno_vigente` resolve o valor atual.
3. Gravar **CRG por semestre** (`crg_semestre`) a partir dos PDFs, com a regra do zero.
4. Registrar o que não casou em `excecao`, não em contador que some.
5. Rodar em **PostgreSQL**, dentro de **Docker** (backend + banco).

## 2. Decisões de implementação

| # | Decisão | Por quê |
|---|---|---|
| 1 | **PostgreSQL 17** via `docker compose`; driver `psycopg[binary]` (v3) | Seção 6 do doc: schema reescrito de qualquer jeito, faz-se uma vez só. |
| 2 | `DATABASE_URL` em env; `engine.py` para de hardcodar SQLite | Mesmo código roda em Postgres (compose) e SQLite (testes). |
| 3 | **Testes continuam em SQLite temporário** (fixture atual) | Rápidos, sem Docker. Todo DDL fica na forma portável (seção 4.7 do doc). Nada Postgres-only nesta entrega — colunas geradas de turma/polo (passo 7) ficam para depois. |
| 4 | `Base.metadata.create_all` no **lifespan** do FastAPI, não no import | Import de módulo não pode depender de banco de pé. Sem Alembic agora: o banco Postgres nasce vazio, `create_all` basta. Migração incremental é dívida declarada. |
| 5 | `POST /lotes` cria `raw/lotes/<id>/` + linha em `lote`; as rotas de dados exigem `?lote=<id>` e recusam com 400 se o lote não existe | Impede rodar "solto". |
| 6 | Raiz dos lotes em `DADOS_RAW_DIR`; no compose, volume `./data:/data` e `DADOS_RAW_DIR=/data/raw/lotes` | `data/` já está no `.gitignore`; é onde o clone do repo privado entra. |
| 7 | PDF lido com **`pypdf`** (Python puro), não `pdftotext` | Roda igual no container e no Windows do autor. Validar nos 56 PDFs antes de aceitar. |
| 8 | `aluno_vigente` como **VIEW** criada por DDL no `after_create` do metadata | É o que o doc promete. `GET /alunos` e `GET /alunos/{matricula}` leem dela. |
| 9 | Passo 2 grava `crg_semestre` **e** uma linha nova em `usuarios` com `CRG` = último semestre apurado, `nome`, `data_de_nascimento` | `usuarios.CRG` fica coerente com "vigente" sem recalcular a cada leitura. |
| 10 | `/sincronizar` grava `fasitech.json` **antes** de abrir sessão no banco; se falhar, nada entra | Seção 3.2: o arquivo congelado é a evidência. |
| 11 | Contadores continuam na resposta das rotas **e** vão para `ingestao`; rejeitados vão para `excecao` | Compatível com quem já lê a resposta. |
| 12 | Dockerfile multi-stage `python:3.12-slim`, instala via `pyproject.toml`, usuário não-root, `uvicorn` na 8000 | Frontend não entra nesta entrega. |

## 3. Contratos das rotas

### `POST /lotes`
Body: `{ "id": "2026-09-L01", "periodos_cobertos": ["2025.2", "2026.1"], "executado_por": "...", "observacao": "..." }`
Efeito: cria `<DADOS_RAW_DIR>/<id>/historicos/`, insere em `lote`. `409` se já existe.

### `GET /lotes` e `GET /lotes/{id}`
Devolvem o lote com suas ingestões (passo, contadores, `executado_em`) e a contagem de exceções por motivo.

### `POST /alunos/sincronizar?lote=<id>`
1. Busca todas as páginas do FasiTech.
2. Grava `<lote>/fasitech.json` = `{ "url", "params", "coletado_em", "paginas": [<corpo de cada página como veio>] }`; registra em `arquivo_fonte` (`tipo=api_fasitech`, sha256 do arquivo).
3. Abre `ingestao (passo=1)`.
4. Para cada registro: válido → **insere sempre** linha nova em `usuarios` com `ingestao_id`; inválido → `excecao (motivo=matricula_invalida | sem_periodo)`.
5. Fecha a ingestão. Resposta: `{ "lote", "ingestao_id", "importados", "rejeitados" }`.

### `POST /alunos/atualizar-crg?lote=<id>`
1. Lista `<lote>/historicos/*.pdf`; `503` se vazio.
2. Para cada PDF: registra em `arquivo_fonte` (sha256; se já existe em outro lote → `excecao motivo=duplicado`, pula); extrai matrícula, nome, data de nascimento, data de emissão, bloco "Coeficiente de Rendimento por Semestre Letivo".
3. Aplica a regra do zero: semestre ≥ semestre da emissão → `crg=NULL`.
4. Grava `crg_semestre` (uma linha por semestre, com `ingestao_id`).
5. Para cada `(matricula, periodo)` vigente em `usuarios` daquela matrícula: insere linha nova copiando o vigente + `CRG` (último semestre não nulo), `nome`, `data_de_nascimento`.
6. Matrícula do PDF sem nenhuma linha em `usuarios` → `excecao motivo=sem_socioeconomico`. Matrícula em `usuarios` sem PDF → `excecao motivo=sem_academico` (os 47).
7. Resposta: `{ "lote", "ingestao_id", "pdfs_lidos", "semestres_gravados", "alunos_atualizados", "sem_academico", "sem_socioeconomico", "duplicados" }`.

### `POST /alunos/preencher-legado?lote=<id>`
Lê `<lote>/DadosAgrupados.csv` (`503` se ausente). Para cada vigente com correspondência `(matricula, periodo)`: insere linha nova = vigente + campos vazios preenchidos. Nunca toca `CRG`. Resposta como hoje + `lote`, `ingestao_id`.

### `GET /alunos`, `GET /alunos/{matricula}`
Leem `aluno_vigente`. `AlunoOut` ganha `ingestao_id`.

### `POST /alunos`
Mantido para cadastro manual; exige `?lote=` e grava com `ingestao_id` de uma ingestão `passo=0` (manual). O `409` de duplicado sai — append-only.

## 4. Extração do PDF (serviço `crg_historico.py`, reescrito)

Entrada: caminho do PDF. Saída:

```python
{
  "matricula": 202016040011,
  "nome": "...",
  "data_de_nascimento": "dd/mm/aaaa",
  "emitido_em": date(2025, 12, 10),
  "crg_por_semestre": {"2020.2": 10.0, "2021.1": 0.0, ..., "2025.2": None, "2026.1": None},
}
```

Regex do bloco: `(\d{4})/Sem([12]):\s*([\d.]+)` a partir de "Coeficiente de Rendimento por Semestre". Semestre da emissão: mês ≤ 6 → `.1`, senão `.2`. O `crg_historico.csv` é aposentado.

## 5. Docker

```
docker-compose.yml          raiz do repo
backend/Dockerfile
backend/.env.example        DATABASE_URL, FASITECH_URL, FASITECH_TOKEN, DADOS_RAW_DIR
```

- `db`: `postgres:17-alpine`, volume nomeado `pgdata`, healthcheck `pg_isready`, porta 5432 só na rede interna.
- `backend`: build `backend/`, `depends_on: db (service_healthy)`, `ports: 8000:8000`, volume `./data:/data`, `env_file: backend/.env`.
- `docker compose up` sobe tudo; `create_all` roda no lifespan.

## 6. Testes

- Fixture atual (`tests/conftest.py`) continua: SQLite temporário, `monkeypatch` do engine. Passa a criar também a view e a receber um `tmp_path` como `DADOS_RAW_DIR`.
- Novos testes: lotes (criar, duplicado, listar), sincronizar congela `fasitech.json` e insere snapshot novo, atualizar-crg sem PDF real no repo (dado pessoal): o extrator é dividido em `extrair_texto(pdf) -> str` e `interpretar_historico(texto) -> dict`; os testes cobrem o segundo com texto sintético no formato do SIGAA e fazem `monkeypatch` do primeiro, regra do zero, exceções gravadas, vigente resolve pela ingestão mais recente, preencher-legado não altera linha existente.
- Testes que mudam de contrato de propósito: `test_sincronizar_nao_duplica_na_segunda_chamada` → `..._insere_snapshot_novo_e_vigente_muda`; `test_criar_aluno_duplicado_da_409` → removido; `test_atualizar_crg_atualiza_todos_os_periodos_da_matricula` → reescrito para `crg_semestre`.
- Verificação final manual: `docker compose up`, `POST /lotes`, rodar os 3 passos contra os 56 PDFs reais no L01, conferir `GET /lotes/2026-09-L01`.

## 7. Fora do escopo (declarado)

- `backend/app/db/repository.py` — consultas do dashboard precisam passar a ler `aluno_vigente`; tem alteração não commitada do autor, entra em entrega separada.
- Frontend no Docker.
- Alembic / migração incremental.
- Turma e polo derivados (passo 7 do doc), rótulos (passo 8).
- Mover os PDFs e o CSV para `data/raw/lotes/2026-09-L01/` e criar o repo privado — manual, do autor (seção 7 do doc, passos 1–2).

## 8. Ajuste no doc de governança

Seção 7, passo 6 passa a ser "PostgreSQL + Docker, junto do passo 3" — já era a intenção, só explicita o Docker.
