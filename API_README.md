# API de Alunos — Dashboard Educacional

Uma API FastAPI que consolida dados acadêmicos (CRG) e socioeconômicos de alunos da UFPA Cametá, casando-os pela matrícula.

## Visão Geral

A API une duas fontes pela matrícula e só expõe ao dashboard quem passou pelo cruzamento:

| Fonte | Dados | Como entra |
|-------|-------|-----------|
| **FasiTech** | Socioeconômico (renda, moradia, saúde mental, etc.) | passo 1 da importação |
| **Histórico SIGAA (PDF)** | CRG por semestre + nome + data de nascimento + período (data de emissão) | passo 2 da importação |

**A única escrita é `POST /lotes/importar`**: responsável + `.zip` dos históricos. A API gera o id do lote, busca o FasiTech, lê os PDFs, extrai o período, gera os relatórios e **fecha o lote** — numa transação só. Lote fechado é imutável (também no banco, por triggers). Ver `docs/governanca_simplificada.md`.

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

Servidor sobe em `http://127.0.0.1:8000`. **`DATABASE_URL` é obrigatória** e tem que apontar para PostgreSQL: sem ela — ou apontando para SQLite — a aplicação recusa subir, com mensagem dizendo o que fazer. Não há mais fallback silencioso para um arquivo `.sqlite` local; ele escondia defeito de schema que só aparecia em produção (ver `docs/migracoes.md`).

## As Rotas

### 1. `POST /lotes/importar`
Importa um lote. Multipart com **só dois campos**: `responsavel` (texto, 1–100 caracteres) e `arquivo` (`.zip` com os PDFs do SIGAA). No Swagger aparece com seletor de arquivo.

```bash
curl -X POST localhost:8000/lotes/importar -F 'responsavel=Edinaldo' -F 'arquivo=@historicos.zip'
```

O que acontece, em ordem, numa transação: gera o id `AAAA-MM-Lnn`; extrai os `.pdf` do zip para `data/raw/lotes/<id>/historicos/` (subpastas achatadas, `__MACOSX/`/`Thumbs.db` em `ignorados`, teto de 100 MB descomprimidos); **passo 1** — busca o FasiTech, congela em `fasitech.json`, grava uma linha em `usuarios` por registro válido; **passo 2** — lê cada PDF, grava `historico` (com o período = semestre letivo da data de emissão) e `crg_semestre`, e atualiza o vigente de quem tem socioeconômico; `periodos_cobertos` = períodos dos históricos; **fechamento** — `SHA256SUMS`, `lote.md`, `vigente.csv`, `integrados.csv`, `nao_integrados.csv`, `fechado_em`.

**Qualquer erro desfaz tudo** — banco e disco. Não sobra lote pela metade.

**Resposta**: `201` — o lote (já fechado) mais o que a execução fez:
```json
{
  "id": "2026-09-L02",
  "fechado_em": "2026-09-25T10:01:00Z",
  "periodos_cobertos": ["2025.2"],
  "executado_por": "Edinaldo",
  "ingestoes": [{"passo": 1, "...": "..."}, {"passo": 2, "...": "..."}],
  "excecoes_por_motivo": {"sem_academico": 91},
  "arquivos": {"gravados": ["historico_202016040011.pdf", "..."], "ja_existiam": [], "ignorados": []},
  "sincronizar": {"ingestao_id": 1, "importados": 187, "rejeitados": 0},
  "atualizar_crg": {"ingestao_id": 2, "pdfs_lidos": 56, "semestres_gravados": 258, "alunos_atualizados": 87,
                    "sem_academico": 91, "sem_socioeconomico": 0, "duplicados": 0, "ilegiveis": 0},
  "arquivos_gerados": ["/data/raw/lotes/2026-09-L02/SHA256SUMS", "..."],
  "resumo": {"total": 111, "integrados": 56, "nao_integrados": 55,
             "por_motivo": {"sem_academico": 55}, "preenchimento_medio_integrados": 62.9}
}
```

**Status de erro** (em todos, nada é gravado):
- `400` — arquivo não é `.zip`, zip corrompido ou sem nenhum PDF
- `409` — dois PDFs com o mesmo nome e conteúdo diferente no zip
- `413` — passa de 100 MB descomprimidos
- `422` — `responsavel` ausente/vazio; ou nenhum PDF legível (o período não pôde ser identificado)
- `502` — FasiTech fora do ar ou formato inesperado
- `503` — `FASITECH_URL` não configurada

A rota **não tem autenticação**, como o resto da API: só deve ficar alcançável por `localhost`/rede interna do compose (`docs/governanca_dados.md`, seção 3.5).

### 2. `GET /lotes`
Lista todos os lotes, cada um com suas ingestões (uma por passo já rodado) e as exceções agrupadas por motivo.

**Resposta**: `200` com array de lotes (`id`, `executado_em`, `fechado_em`, `periodos_cobertos`, `executado_por`, `observacao`, `ingestoes`, `excecoes_por_motivo`).

### 3. `GET /lotes/{id}`
Busca um lote por id, no mesmo formato acima.

**Resposta**:
- `200` — lote encontrado
- `404` — não existe

### 4. `GET /alunos`
Lista o valor **vigente** de cada aluno **integrado** (view `aluno_integrado` = `aluno_vigente` — a ingestão mais recente por `matricula, periodo` — restrita a quem tem histórico acadêmico **e** resposta socioeconômica), com **turma e polo derivados da matrícula** (governança §4.8). Quem não passou pelo cruzamento não aparece aqui: está no relatório do lote (rota 7).

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
    "polo": null,
    "turma": "2020",
    "polo_cod": "1604",
    "polo_nome": "Cametá",
    ...
  }
]
```

#### Turma e polo (`turma`, `polo_cod`, `polo_nome`)

Só de leitura: ninguém envia, ninguém grava — a view calcula a partir dos 12 dígitos da matrícula (`2020` `1604` `0002` = turma, polo, sequencial), e `polo_nome` sai de um `LEFT JOIN` com a tabela `polo`.

Existem porque **a fonte não manda esses dados**: verificada em 2026-09-23, a API do FasiTech devolve `polo` nulo em 187 de 187 registros e não devolve `primeiro_ano_eletivo` campo nenhum. O campo `polo` continua na resposta por fidelidade ao que foi gravado — e é justamente por isso que ele aparece `null` no exemplo acima.

| Situação | `turma` | `polo_cod` | `polo_nome` |
|---|---|---|---|
| Matrícula de 12 dígitos, polo conhecido | `"2020"` | `"1604"` | `"Cametá"` |
| Polo ainda não cadastrado na tabela `polo` | `"2020"` | `"9999"` | `null` |
| Matrícula fora do padrão de 12 dígitos | `null` | `null` | `null` |

Polo novo é `INSERT INTO polo` — não exige deploy. As três colunas também entram no `vigente.csv` gerado ao fechar o lote.

### 4b. `GET /crg-semestres`
A **trajetória acadêmica**: um ponto por `(matricula, semestre)`, lido da view `crg_semestre_vigente` (ingestão mais recente por chave, como `aluno_vigente`). Só alunos integrados.

```json
[{ "matricula": 202016040011, "semestre": "2024.1", "crg": 7.69 },
 { "matricula": 202016040011, "semestre": "2025.2", "crg": null }]
```

**Por que existe, se `/alunos` já traz `CRG`.** O `CRG` de `/alunos` é o do **último semestre apurado, repetido em todos os períodos de coleta do aluno** — o passo 2 grava o mesmo valor em cada linha vigente. Serve para o corte transversal ("como está a turma agora"); uma série temporal sobre ele seria uma reta horizontal por construção. Quem quer evolução lê esta rota.

`crg: null` é **semestre não apurado** na data de emissão do histórico (§4.6, a regra do zero), e a linha **continua na resposta**. Quem desenha faz lacuna ali: sumir da lista colaria dois semestres distantes como vizinhos, e virar zero inventaria uma queda. Na base atual 2025.2 e 2026.1 têm 56 alunos e nenhuma nota.

### 5. `GET /alunos/{matricula}`
Busca um aluno integrado por matrícula (retorna o período mais recente se houver múltiplos).

**Resposta**: 
- `200` — aluno encontrado
- `404` — não existe ou não está integrado

### 6. `GET /lotes/{id}/excecoes`
Lista as exceções do lote, uma por linha, com o passo que a gerou. Ordenada por `passo, matricula, periodo`. É a trilha de auditoria bruta; o relatório (rota 7) é a leitura dela.

**Resposta**: `200`
```json
[
  {"ingestao_id": 3, "passo": 2, "matricula": 202016040002, "periodo": "2025.2", "motivo": "sem_academico", "detalhe": null}
]
```

**Status de erro**:
- `404` — lote não existe

### 7. `GET /lotes/{id}/relatorio`
Os dois relatórios do lote, sobre a base consolidada no fechamento dele (para o lote mais recente, os integrados são exatamente os alunos de `GET /alunos`). Os mesmos dados de `integrados.csv` e `nao_integrados.csv`.

```json
{
  "lote": "2026-09-L02",
  "resumo": {"total": 111, "integrados": 56, "nao_integrados": 55, "por_motivo": {"sem_academico": 55}, "preenchimento_medio_integrados": 62.9},
  "integrados": [
    {"matricula": 202016040011, "nome": "…", "academico": true, "socioeconomico": true, "status": "Integrado com sucesso",
     "campos_avaliados": 13, "qtd_campos_sem_resposta": 3, "campos_sem_resposta": ["renda", "trabalho", "acesso_internet"],
     "percentual_preenchimento": 76.9}
  ],
  "nao_integrados": [
    {"matricula": 202116040005, "nome": null, "academico": false, "socioeconomico": true,
     "motivo": "sem_academico", "motivo_descricao": "Possui socioeconômico e não possui acadêmico", "detalhe": null,
     "campos_avaliados": 12, "qtd_campos_sem_resposta": 4, "campos_sem_resposta": ["..."], "percentual_preenchimento": 66.7}
  ]
}
```

`motivo` ∈ `sem_academico`, `sem_socioeconomico`, `falha_identificacao` (PDF ilegível/sem matrícula, ou registro sem período), `matricula_nao_encontrada` (registro do FasiTech sem matrícula válida). Regras de completude em `docs/governanca_simplificada.md` §5. `404` se o lote não existe.

## Fluxo de um lote

1. **Importar** — rota 1 (tela Dados, `scripts/lote.py importar`, Swagger ou `curl`).
2. **Conferir** — rota 7 (ou a tela Dados, que mostra o relatório logo abaixo do formulário).
3. **Commit no repositório privado de dados** (fora deste repo — `docs/governanca_dados.md`, seção 3.4).

Dado novo = nova importação = lote novo. Os anteriores ficam intactos. Roteiro em `docs/operacao_lote.md`.

## Dados Faltantes

L01 (dados reais): 111 matrículas, 56 integradas, 55 só com socioeconômico (sem histórico). Essas 55 não aparecem em `GET /alunos` nem nos dashboards; estão no relatório de não integrados com o motivo. Quando os históricos chegarem, uma nova importação as integra.

## Testes

A suíte roda offline (FasiTech e leitura de PDF falsificados) contra um PostgreSQL de verdade:

```bash
pytest -q                                   # com Docker: sobe um postgres:17-alpine descartável
TEST_POSTGRES_URL=postgresql+psycopg://postgres@localhost:55432/postgres pytest -q   # sem Docker
```

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
BancoDeDados.sqlite      # resíduo do SQLite abandonado — pode ser apagado
```

## Arquitetura

```
backend/app/
├── main.py                         # FastAPI app + health-check
├── api/
│   ├── lotes.py                    # importar (única escrita), listar, buscar, exceções, relatório
│   ├── alunos.py                   # só leitura, da view aluno_integrado
│   └── crg.py                      # trajetória por semestre, só integrados
├── schemas/                        # Pydantic: alunos, lotes (importação, relatório), crg
├── db/
│   ├── engine.py                   # modelos: lote, ingestao, arquivo_fonte, usuarios, crg_semestre, historico, excecao, polo
│   └── vigente.py                  # views aluno_vigente, aluno_integrado, crg_semestre_vigente
├── services/
│   ├── importacao.py               # a importação: passos 1 e 2, período, fechamento, tudo ou nada
│   ├── relatorio.py                # integrados, não integrados, completude
│   ├── fechamento.py               # SHA256SUMS, lote.md, CSVs, fechado_em
│   ├── lotes.py                    # pasta do lote, id, hash, ingestão, exceção, extração do zip
│   ├── fasitech_client.py          # HTTP client paginado
│   ├── ausentes.py                 # CLI: alunos do FasiTech fora da base integrada (python -m app.services.ausentes)
│   └── crg_historico.py            # leitor do PDF do SIGAA
└── core/config.py                  # .env loader

backend/migrations/versions/         # revisões do Alembic (ver docs/migracoes.md)
tests/                               # pytest contra PostgreSQL real (conftest.py)
scripts/lote.py                      # CLI: importar, relatorio
```

## Arquivos Criados Nesta Demanda

> Registro histórico do commit `30a232e` (02/09/2026). O estado atual está em "Arquitetura" acima.

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

1. **Históricos faltando**: no L01, 55 das 111 matrículas têm só socioeconômico e ficam fora dos dashboards (relatório de não integrados)
2. **Campos que a planilha legada preenchia ficam `NULL`**: o L01 é só API + PDF; `DadosAgrupados.csv` foi abandonado (`docs/superpowers/2026-09-12-primeiro-lote-design.md`) — limitação declarada da fonte, não defeito do lote
3. **`trabalho`, `acesso_internet` e `renda` vêm nulos do FasiTech** em 187, 187 e 184 de 187 registros — aparece como "campo sem resposta" nos relatórios; conferir o mapeamento na fonte
4. **Multiplicidade por matrícula**: Um aluno pode ter múltiplas linhas (um por período socioeconômico) — isso é proposital, use `GET /alunos` e agregue se quiser "um por aluno"

## Tratamento de Erros

| Status | Significa |
|--------|-----------|
| `400` | Arquivo da importação não é `.zip`, está corrompido ou não tem PDF |
| `404` | Recurso não existe (matrícula integrada ou lote) |
| `409` | Dois PDFs com mesmo nome e conteúdo diferente no zip |
| `413` | Zip passa de 100 MB descomprimidos |
| `422` | Dado inválido: falta `responsavel`, ou nenhum histórico legível (sem período) |
| `502` | Dependência externa falhou (FasiTech indisponível, formato inesperado) |
| `503` | `FASITECH_URL` não configurada |

Em erro na importação, nada é gravado.

## Assistente de consultas — `POST /assistente/perguntar`, `POST /assistente/executar`

Pergunta em português → resposta na forma mais adequada (`dashboard`, `dinamico`, `tabela`, `texto` ou `nao_entendi`), sempre com `explicacao` (consulta interpretada, filtros, fontes, forma). Desenho: `docs/superpowers/specs/2026-09-25-assistente-consultas-design.md`.

```bash
curl -X POST localhost:8000/assistente/perguntar -H 'Content-Type: application/json' -d '{"pergunta": "Compare renda familiar por polo"}'
```

- **O que sai para o Groq:** só a pergunta, com nome e matrícula trocados por `⟨A1⟩`, e o catálogo de campos. Nunca linha de aluno nem resultado.
- **SQL:** montado pelo backend a partir da `consulta` (o modelo não escreve SQL) e executado com a role `leitor_assistente` (só `SELECT` em `aluno_integrado` e `crg_semestre_vigente`), com timeout de 5 s.
- `POST /assistente/executar {"consulta": {...}}` reexecuta uma `consulta` salva sem LLM (histórico e link compartilhado). Uma consulta fora do catálogo recebe 422.
- **Erros:** 503 LLM indisponível (sem `GROQ_API_KEY`, fora do ar, 429); 504 consulta passou de 5 s.
- **Configuração:** `GROQ_API_KEY`, `GROQ_MODELO`, `GROQ_URL` em `backend/.env` (ver `.env.example`).
- **Avaliação:** `AVALIAR_LLM=1 pytest tests/test_assistente_avaliacao.py -s` mede a taxa de acerto da interpretação.

## Próximas Etapas

- [ ] Importar os históricos que faltam (55 matrículas do L01)
- [ ] Confirmar com o FasiTech o mapeamento de `trabalho`, `acesso_internet` e `renda`
- [ ] Implementar paginação em `GET /alunos` (hoje retorna tudo)

---

**Última atualização**: 25/09/2026 (governança simplificada, `docs/governanca_simplificada.md`)  
**Documentação técnica completa**: Veja `/docs` no servidor ou consulte `backend/app/` direto
