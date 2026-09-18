# API de Alunos — Dashboard Educacional

Uma API FastAPI que consolida dados acadêmicos (CRG) e socioeconômicos de alunos da UFPA Cametá, casando-os pela matrícula.

## Visão Geral

A API mantém uma tabela única de alunos que une três fontes de dado:

| Fonte | Dados | Como entra |
|-------|-------|-----------|
| **Lotes** | Abre a rodada; pré-requisito das outras | `POST /lotes` |
| **Históricos (PDF)** | Recebe os PDFs do SIGAA para dentro do lote; com `?executar=true` já roda os dois passos | `POST /lotes/{id}/historicos` |
| **Fechamento** | Sela o lote: `SHA256SUMS`, `lote.md`, CSVs derivados, `fechado_em` | `POST /lotes/{id}/fechar` |
| **FasiTech** | Socioeconômico (renda, moradia, saúde mental, etc.) | `POST /alunos/sincronizar?lote=<id>` |
| **Histórico SIGAA** | CRG oficial + nome + data de nascimento | `POST /alunos/atualizar-crg?lote=<id>` |

A API não calcula nada — importa dado já pronto e resolve conflitos entre fontes. Toda escrita fica presa a um **lote** (`docs/governanca_dados.md`) — nada roda sem `?lote=<id>` de um lote já aberto com `POST /lotes`.

## Com Docker (recomendado)

```bash
cp backend/.env.example backend/.env
# edite backend/.env: preencha FASITECH_URL, FASITECH_TOKEN e troque POSTGRES_PASSWORD
docker compose up --build
```

Sobe dois serviços: `db` (PostgreSQL 17, sem porta publicada no host) e `backend` em `http://localhost:8000`. `./data` é montado em `/data` dentro do container `backend` — é onde ficam os lotes (`DADOS_RAW_DIR=/data/raw/lotes`) e os derivados gerados ao fechar (`DADOS_PROCESSED_DIR=/data/processed`).

- **Documentação interativa (Swagger)**: http://localhost:8000/docs
- **Health-check**: `GET /` retorna `{"status": "ok"}`

## Sem Docker

Requisitos: Python 3.14+, `venvDashboard` (venv) configurada, variáveis de ambiente `FASITECH_URL` e `FASITECH_TOKEN` em `backend/.env`.

```bash
# 1. Entre na raiz do projeto
cd Dashboard_Educacional

# 2. Ative a venv e set PYTHONPATH
$env:PYTHONPATH = "backend"
venvDashboard\Scripts\python.exe -m uvicorn app.main:app --reload
```

Servidor sobe em `http://127.0.0.1:8000`. Sem `DATABASE_URL` no ambiente, a API cai num SQLite local (`backend/app/db/BancoDeDados.sqlite`, ver `backend/app/core/config.py`) — útil para desenvolvimento rápido, mas é o `docker compose` acima que sobe o PostgreSQL de verdade.

## As Rotas

### 1. `POST /lotes`
Abre um lote: cria `data/raw/lotes/<id>/historicos/` e a linha em `lote`. Pré-requisito de toda rota abaixo que recebe `?lote=<id>`.

**Body**:
```json
{
  "id": "2026-09-L01",
  "periodos_cobertos": ["2025.2", "2026.1"],
  "executado_por": "edinaldo"
}
```

**Resposta**: `201`
```json
{
  "id": "2026-09-L01",
  "executado_em": "2026-09-12T15:30:14.412951Z",
  "periodos_cobertos": ["2025.2", "2026.1"],
  "executado_por": "edinaldo",
  "observacao": null,
  "ingestoes": [],
  "excecoes_por_motivo": {}
}
```

**Status de erro**:
- `409` — lote já existe (no banco ou a pasta já existe em disco)

### 2. `GET /lotes`
Lista todos os lotes, cada um com suas ingestões (uma por passo já rodado) e as exceções agrupadas por motivo.

**Resposta**: `200` com array de lotes, no mesmo formato do `POST /lotes`.

### 3. `GET /lotes/{id}`
Busca um lote por id, no mesmo formato acima.

**Resposta**:
- `200` — lote encontrado
- `404` — não existe

### 4. `GET /alunos`
Lista o valor **vigente** de cada aluno (view `aluno_vigente` — a ingestão mais recente por `matricula, periodo`).

**Resposta**: `200` com array de alunos (vazio se o banco tá vazio)

```json
[
  {
    "id": 12,
    "matricula": 202016040011,
    "periodo": "2026.1",
    "CRG": 7.9662,
    "nome": "NALBERTH DE LEAO CASTRO",
    "genero": "Masculino",
    "renda": "Até 1 salário mínimo",
    ...
  }
]
```

### 5. `GET /alunos/{matricula}`
Busca um aluno vigente por matrícula (retorna o período mais recente se houver múltiplos).

**Resposta**: 
- `200` — aluno encontrado
- `404` — não existe

### 6. `POST /alunos?lote=<id>`
Cadastra um aluno manualmente, gravado na ingestão de passo manual do lote. Só `matricula` e `periodo` são obrigatórios. Sempre insere uma linha nova (a tabela é append-only); quem resolve o vigente é a view.

**Body**:
```json
{
  "matricula": 999999,
  "periodo": "2026.1",
  "CRG": 7.5,
  "nome": "Fulano"
}
```

**Resposta**:
- `201` — criado
- `400` — o lote de `?lote=<id>` não existe (crie com `POST /lotes`)
- `422` — falta matrícula ou período

### 7. `POST /alunos/sincronizar?lote=<id>`
Passo 1 do lote: busca todos os alunos no FasiTech, congela a resposta em `<lote>/fasitech.json` e só então grava — uma linha nova por registro válido.

**Resposta**: `200` com contadores. Exemplo ilustrativo (números fictícios, só para mostrar o formato):
```json
{ "lote": "2026-09-L01", "ingestao_id": 1, "importados": 156, "rejeitados": 9 }
```

**Status de erro**:
- `400` — lote não existe
- `409` — o passo 1 já rodou nesse lote
- `502` — FasiTech fora do ar ou respondeu formato inesperado
- `503` — `FASITECH_URL` não configurada

### 8. `POST /alunos/atualizar-crg?lote=<id>`
Passo 2 do lote: lê os PDFs de `<lote>/historicos/`, extrai o CRG **por semestre** (grava em `crg_semestre`, regra do zero aplicada) e insere, para cada vigente do aluno, uma linha nova com o CRG do último semestre apurado, nome e nascimento.

**Resposta**: `200` com contadores.

Exemplo ilustrativo do L01 completo (após `/sincronizar` ter trazido os 103 alunos do FasiTech): 56 PDFs casam, 47 alunos ficam `sem_academico`.
```json
{
  "lote": "2026-09-L01",
  "ingestao_id": 2,
  "pdfs_lidos": 56,
  "semestres_gravados": 258,
  "alunos_atualizados": 56,
  "sem_academico": 47,
  "sem_socioeconomico": 0,
  "duplicados": 0,
  "ilegiveis": 0
}
```
Se `/atualizar-crg` rodar antes de `/sincronizar`, todos os PDFs caem em `sem_socioeconomico` (56) e `alunos_atualizados` fica 0 — o CRG é guardado mesmo assim.

**Status de erro**:
- `400` — lote não existe
- `409` — o passo 2 já rodou nesse lote
- `503` — nenhum PDF em `<lote>/historicos/`

### 9. `GET /lotes/{id}/excecoes`
Lista as exceções do lote, uma por linha, com o passo que a gerou. Ordenada por `passo, matricula, periodo`. É a base do relatório de correspondência (`scripts/lote.py fechar`, `docs/operacao_lote.md`).

**Resposta**: `200`
```json
[
  {"ingestao_id": 3, "passo": 2, "matricula": 202016040002, "periodo": "2025.2", "motivo": "sem_academico", "detalhe": null}
]
```

**Status de erro**:
- `404` — lote não existe

### 10. `POST /lotes/{id}/historicos[?executar=true]`
Recebe os históricos do SIGAA (multipart, campo `arquivos`, um ou mais) e grava em `<lote>/historicos/`. No Swagger (`/docs`) aparece com seletor de arquivos. Substitui a cópia manual dos PDFs. Cada arquivo é um `.pdf` ou um `.zip`; do zip só saem as entradas `.pdf`, pelo nome-base (subpastas são achatadas, `__MACOSX/`, `Thumbs.db` etc. vão para `ignorados`). A extensão vira `.pdf` minúsculo — o passo 2 faz `glob("*.pdf")`, sensível a maiúsculas em Linux. `.rar` não é aceito.

Reenviar é idempotente: nome que já existe com o **mesmo** conteúdo conta em `ja_existiam`. Nome que já existe com conteúdo **diferente** dá `409` antes de gravar qualquer coisa — insumo de lote não se sobrescreve. Não mexe em `arquivo_fonte`: o registro por SHA-256 continua sendo do passo 2.

```bash
curl -X POST localhost:8000/lotes/2026-09-L01/historicos \
  -F 'arquivos=@historicos.zip' -F 'arquivos=@202016040001.pdf'
```

**`?executar=true`** — depois de gravar, roda `/alunos/sincronizar` (passo 1) e `/alunos/atualizar-crg` (passo 2), pulando o que já executou neste lote. É o jeito de fazer o lote inteiro pelo Swagger em duas chamadas (`POST /lotes` e esta). Se um passo falhar, os PDFs ficam gravados e a resposta é o erro do passo (`502`/`503` do passo 1, por exemplo); reenviar os mesmos arquivos retoma de onde parou.

**Resposta**: `200`
```json
{
  "lote": "2026-09-L01",
  "gravados": ["202016040001.pdf"], "ja_existiam": [], "ignorados": ["__MACOSX/._x.pdf"],
  "sincronizar": {"lote": "2026-09-L01", "ingestao_id": 1, "importados": 103, "rejeitados": 0},
  "atualizar_crg": {"lote": "2026-09-L01", "ingestao_id": 2, "pdfs_lidos": 56, "sem_academico": 47, "...": "..."}
}
```
Sem `executar`, `sincronizar` e `atualizar_crg` vêm `null`; passo que já tinha rodado vem como `"ja_executado"`.

**Status de erro**:
- `400` — lote não existe, ou um `.zip` enviado está corrompido
- `409` — lote já fechado; o passo 2 já rodou nesse lote (insumo não muda depois de lido); ou há nome repetido com conteúdo diferente
- `413` — o envio passa de 100 MB descomprimidos (`LIMITE_BYTES_HISTORICOS`); divida em mais de um envio

A rota **não tem autenticação**, como o resto da API: só deve ficar alcançável por `localhost`/rede interna do compose (`docs/governanca_dados.md`, seção 3.5).

### 11. `POST /lotes/{id}/fechar`
Sela o lote. Exige os passos 1 e 2 executados. Gera em `<lote>/` o `SHA256SUMS` (hash de todo insumo) e o `lote.md` (períodos, quem rodou, contadores por ingestão, exceções por motivo, arquivos com hash, limitações declaradas); gera em `DADOS_PROCESSED_DIR/<lote>/` o `vigente.csv` (corte de `GET /alunos`) e o `correspondencia.csv` (uma linha por matrícula: `Academico`, `SocioEconomico`, `Dado_Faltando`); grava `lote.fechado_em`. Lote fechado não recebe mais históricos nem se reabre.

**Resposta**: `200` — o mesmo objeto de `GET /lotes/{id}` (agora com `fechado_em` preenchido) mais `arquivos_gerados`, os quatro caminhos como a API os vê (dentro do container, `/data/...`).

**Status de erro**:
- `404` — lote não existe
- `409` — já fechado, ou faltam os passos 1 e/ou 2

### 12. `GET /lotes/{id}/correspondencia`
O `correspondencia.csv` como JSON: uma linha por matrícula, ordenada. É o que a tela **Dados** do dashboard mostra na "Cobertura do lote".

```json
[{"matricula": 202016040001, "nome": "Ana", "academico": true, "socioeconomico": false, "faltando": "SocioEconomico"}]
```
`faltando` ∈ `""`, `"Academico"`, `"SocioEconomico"`, `"Ambos"`. `404` se o lote não existe.

## Fluxo de um lote

Um lote é uma rodada completa de importação (`docs/governanca_dados.md`, seção 5). Os passos rodam em ordem; são idempotentes — repetir uma chamada não duplica nem apaga o que já foi importado (o passo já executado responde `409`).

1. **Criar o lote** — abre `data/raw/lotes/<id>/historicos/` e a linha em `lote`.
   ```bash
   curl -X POST localhost:8000/lotes -H 'content-type: application/json' \
     -d '{"id":"2026-09-L01","periodos_cobertos":["2025.2","2026.1"],"executado_por":"edinaldo"}'
   ```
2. **Enviar os PDFs e rodar** — os históricos entram pela rota 10; com `executar=true` o passo 1 (`/sincronizar`: busca o FasiTech e congela `fasitech.json`) e o passo 2 (`/atualizar-crg`: lê os PDFs, grava CRG por semestre) rodam em seguida.
   ```bash
   curl -X POST 'localhost:8000/lotes/2026-09-L01/historicos?executar=true' -F 'arquivos=@historicos.zip'
   ```
   (As rotas 7 e 8 continuam existindo para rodar cada passo à parte.)
3. **Conferir** — `GET /lotes/2026-09-L01` (contadores, exceções por motivo), `GET /lotes/2026-09-L01/excecoes`, o dashboard, e se os períodos em `fasitech.json` batem com os declarados.
4. **Fechar o lote** — rota 11: `SHA256SUMS`, `lote.md`, CSVs derivados, `fechado_em`.
   ```bash
   curl -X POST localhost:8000/lotes/2026-09-L01/fechar
   ```
5. **Commit no repositório privado de dados** (fora deste repo — `docs/governanca_dados.md`, seção 3.4).

`scripts/lote.py` faz o mesmo pelo terminal (`executar` = passos 1 e 2; `fechar` = passo 4) — roteiro em `docs/operacao_lote.md`. Depois do passo 4, `GET /alunos` (via a view `aluno_vigente`) já reflete o lote; o anterior continua intacto para auditoria.

## Dados Faltantes

Hoje (02/09/2026): 103 alunos distintos, 56 com CRG completo, 47 ainda aguardando histórico.

Um aluno **sem CRG** aparece normal na API com `"CRG": null`. O resto dos dados continua acessível. Quando o histórico dele chegar, é só rodar `/atualizar-crg` de novo.

```json
{
  "matricula": 202116040005,
  "periodo": "2024.(3 e 4)",
  "CRG": null,              // falta — será preenchido quando histórico chegar
  "genero": "Feminino",     // veio do FasiTech
  "renda": "Até 1 salário mínimo",
  ...
}
```

## Testes

90 testes automatizados cobrindo as rotas de lotes (6), de alunos (5) e o `scripts/lote.py`. Rodam offline (nenhuma chamada real ao FasiTech).

```bash
PYTHONPATH=backend venvDashboard\Scripts\python.exe -m pytest -v
```

Resultado esperado: **90 passed**

## Arquivos de Configuração

### `backend/.env` (gitignored)
```
FASITECH_URL=https://...
FASITECH_TOKEN=...
```

### `backend/app/data/` (gitignored)
```
crg_historico.csv        # 56 alunos com CRG do histórico
DadosAgrupados.csv       # planilha manual antiga
BancoDeDados.sqlite      # banco SQLite local (auto-criado)
```

## Arquitetura

```
backend/app/
├── main.py                         # FastAPI app + health-check
├── api/alunos.py                   # as 6 rotas (199 linhas)
├── schemas/alunos.py               # Pydantic: AlunoCreate, AlunoOut
├── db/engine.py                    # SQLAlchemy: table Usuarios + engine
├── services/
│   ├── fasitech_client.py          # HTTP client paginado
│   └── crg_historico.py            # leitor CSV histórico
└── core/config.py                  # .env loader

tests/                               # 52 testes no total (6 arquivos)
├── conftest.py                     # fixture client (banco isolado)
└── test_*.py                       # alunos, lotes, crg_historico, fasitech_client, schema, servico_lotes
```

## Arquivos Criados Nesta Demanda

Todos os arquivos abaixo foram desenvolvidos especificamente para esta API — `db/engine.py` já existia antes e só recebeu ajuste de tipo em dois campos.

| Arquivo | O que faz |
|---|---|
| `schemas/alunos.py` | Contrato de dado (Pydantic). Define `AlunoCreate` e `AlunoOut` — só `matricula` e `periodo` são obrigatórios, o resto é opcional |
| `core/config.py` | Lê `.env` e expõe `FASITECH_URL` e `FASITECH_TOKEN` — único lugar que toca nessas credenciais |
| `services/fasitech_client.py` | Cliente HTTP que busca os alunos socioeconômicos no FasiTech, paginando até trazer tudo |
| `services/crg_historico.py` | Lê `crg_historico.csv` (extraído de 56 PDFs de histórico) e devolve CRG, nome e nascimento por matrícula |
| `services/dados_legado.py` | Lê `DadosAgrupados.csv` e devolve os campos socioeconômicos que ainda faltam, por matrícula+período — nunca inclui CRG |
| `api/alunos.py` | As 6 rotas da API — orquestra os três serviços acima e o banco |
| `main.py` | Cria a aplicação FastAPI, registra as rotas, health-check em `GET /` |
| `tests/conftest.py` | Fixture `client` — sobe a API real com um banco de teste isolado e temporário |
| `tests/test_alunos.py` | 19 testes automatizados cobrindo as 6 rotas, sucesso e erro |
| `db/engine.py` *(editado)* | `qtd_computador` e `qtd_celular` mudaram de número pra texto — a resposta real é categórica (ex: "Acima de 3") |

**Total**: 9 arquivos novos + 1 arquivo ajustado, 721 linhas adicionadas (commit `30a232e`, 02/09/2026).

## Limitações Conhecidas

1. **CRG incompleto**: 47 dos 103 alunos ainda faltam histórico
2. **Campos que a planilha legada preenchia ficam `NULL`**: o L01 é só API + PDF; `DadosAgrupados.csv` foi abandonado (`docs/superpowers/2026-09-12-primeiro-lote-design.md`) — limitação declarada da fonte, não defeito do lote
3. **Multiplicidade por matrícula**: Um aluno pode ter múltiplas linhas (um por período socioeconômico) — isso é proposital, use `GET /alunos` e agregue se quiser "um por aluno"

## Tratamento de Erros

| Status | Significa |
|--------|-----------|
| `400` | `?lote=` aponta para um lote que não existe (crie com `POST /lotes`) |
| `404` | Recurso não existe (matrícula ou lote não cadastrado) |
| `409` | Lote já existe (`POST /lotes`) ou passo já executado neste lote (`/sincronizar`, `/atualizar-crg`) |
| `422` | Dado inválido (falta campo obrigatório) |
| `502` | Dependência externa falhou (FasiTech indisponível, formato inesperado) |
| `503` | Pré-requisito local ausente (URL não configurada, PDF ou CSV não encontrado no lote) |

## Próximas Etapas

- [ ] Adicionar 47 históricos faltantes a `crg_historico.csv`
- [ ] Implementar paginação em `GET /alunos` (hoje retorna tudo)
- [ ] Adicionar filtros por período, gênero, renda, etc.

---

**Última atualização**: 02/09/2026  
**Commits**: 52 testes passando, código em `main` branch  
**Documentação técnica completa**: Veja `/docs` no servidor ou consulte `backend/app/` direto
