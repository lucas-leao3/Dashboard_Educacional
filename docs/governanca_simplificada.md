# Governança de dados simplificada

Estado implementado em 25/09/2026 (revisão Alembic `c5e8a1f3d920`). Substitui o
fluxo de lote em quatro passos (abrir → enviar → rodar → fechar) descrito em
`governanca_dados.md` §3 e `operacao_lote.md` (versão anterior).

Resumo: **o usuário informa o responsável e envia um `.zip`. Todo o resto é
inferido, o lote termina fechado e não se altera mais. Os dashboards só mostram
alunos que passaram pelo cruzamento acadêmico × socioeconômico.**

---

## 1. O que mudou

| Antes | Agora |
|---|---|
| 4 ações: abrir lote (id + períodos + executado por + observação), enviar PDFs, rodar passos, fechar | 1 ação: `POST /lotes/importar` com `responsavel` + `arquivo` (.zip) |
| Período digitado à mão (`periodos_cobertos`) | Extraído da data "Emitido em" de cada histórico |
| Id do lote digitado (sugerido pela tela) | Gerado: `AAAA-MM-Lnn` (sequência do mês, pulando pasta órfã em disco) |
| Fechar era um passo manual separado | O lote é fechado no fim da importação, na mesma transação |
| Falha no meio deixava lote aberto pela metade para "retomar" | Falha desfaz tudo (banco e disco): ou lote fechado, ou nada |
| Lote fechado protegido só pela API | Protegido também no banco (triggers) |
| `POST /alunos`, `/alunos/sincronizar`, `/alunos/atualizar-crg`, `POST /lotes/{id}/historicos`, `POST /lotes/{id}/fechar` | Removidos: a única escrita é a importação |
| Dashboards liam todo `aluno_vigente` (111 matrículas no L01) | Leem `aluno_integrado`: só quem tem histórico **e** socioeconômico (56) |
| Relatório único de correspondência (`faltando`) | Dois relatórios — integrados e não integrados — com motivo e completude |
| Mesmo nome duas vezes no zip (subpastas): o segundo sobrescrevia o primeiro calado | Recusado com 409 |

Arquivos principais:

| Camada | Arquivo | Papel |
|---|---|---|
| Migração | `backend/migrations/versions/20260925_c5e8a1f3d920_importacao_simplificada.py` | tabela `historico`, view `aluno_integrado`, triggers |
| Serviço | `backend/app/services/importacao.py` | orquestra a importação (passos 1 e 2, período, fechamento) |
| Serviço | `backend/app/services/relatorio.py` | integrados, não integrados, completude |
| Serviço | `backend/app/services/fechamento.py` | SHA256SUMS, lote.md, CSVs, `fechado_em` |
| Rotas | `backend/app/api/lotes.py`, `alunos.py`, `crg.py` | importar, consultar, relatório; alunos e CRG só leitura |
| Frontend | `frontend/src/pages/Dados.tsx`, `components/lote/ImportarLote.tsx`, `components/lote/RelatorioLote.tsx` | formulário de 2 campos e os dois relatórios |
| CLI | `scripts/lote.py` | `importar --responsavel NOME arquivo.zip` e `relatorio LOTE` |

---

## 2. Modelagem

```
lote ─┬─< ingestao (passo 1: FasiTech, passo 2: históricos)
      │      ├─< usuarios       socioeconômico (append-only)
      │      ├─< crg_semestre   acadêmico por semestre (append-only)
      │      ├─< historico      NOVO: um PDF lido, com o período
      │      └─< excecao        o que não casou, com motivo
      └─< arquivo_fonte         hash de cada insumo

views:  aluno_vigente   = linha mais recente por (matricula, periodo)
        aluno_integrado = aluno_vigente com crg_semestre   ← NOVA, base dos dashboards
        crg_semestre_vigente
```

### Tabela nova: `historico`

```sql
CREATE TABLE historico (
    id                 SERIAL PRIMARY KEY,
    ingestao_id        INTEGER NOT NULL REFERENCES ingestao(id),
    arquivo_sha256     VARCHAR(64) REFERENCES arquivo_fonte(sha256),
    matricula          BIGINT NOT NULL,
    nome               VARCHAR(100),
    data_de_nascimento VARCHAR,
    emitido_em         DATE NOT NULL,      -- "Emitido em" do PDF
    periodo            VARCHAR(6) NOT NULL -- semestre letivo de emitido_em: '2025.2'
);
```

É o registro de **cada** histórico lido: de onde vem o período e o nome de quem
tem histórico mas não respondeu o FasiTech (antes esse nome não ficava em lugar
nenhum).

### View nova: `aluno_integrado`

```sql
CREATE VIEW aluno_integrado AS
SELECT av.* FROM aluno_vigente av
WHERE EXISTS (SELECT 1 FROM crg_semestre c WHERE c.matricula = av.matricula);
```

Critério do cruzamento, o mesmo em view, API, relatório e CSV:

| Fonte | Presença | Origem |
|---|---|---|
| Socioeconômico | há linha em `usuarios` para a matrícula | FasiTech (passo 1) |
| Acadêmico | há linha em `crg_semestre` para a matrícula | histórico em PDF (passo 2) |

O acadêmico é `crg_semestre`, não `historico`, porque o L01 é anterior à tabela
`historico` e já tem os semestres gravados.

### `lote`: o que o usuário informa e o que é inferido

| Coluna | Origem |
|---|---|
| `id` | gerado (`AAAA-MM-Lnn`) |
| `executado_por` | **informado**: o responsável |
| `periodos_cobertos` | inferido: união de `historico.periodo` do lote, ordenada (`'2025.2'` ou `'2025.2;2026.1'`) |
| `executado_em`, `fechado_em` | carimbados pelo servidor |
| `observacao` | não é mais pedida; só o L01 pode ter |

### Período do histórico

`periodo = semestre letivo da data de emissão` — `AAAA.1` se o mês é ≤ 6, senão
`AAAA.2`. É a mesma regra de corte que o parser já usava (§4.6, regra do zero:
semestre ≥ o da emissão ainda não foi apurado). Nos 56 PDFs reais: emissão
10/12/2025 → `2025.2`.

> O L01 foi aberto à mão com `2025.2; 2026.1`. Pela regra automática ele seria
> só `2025.2` (o `2026.1` aparece no PDF como semestre em curso, sem nota). O
> registro do L01 não foi reescrito: lote fechado é imutável.

### Lote fechado é imutável no banco

Triggers da revisão `c5e8a1f3d920`:

| Trigger | Tabela | Recusa |
|---|---|---|
| `lote_imutavel` | `lote` | UPDATE e DELETE de lote com `fechado_em` preenchido (inclusive reabrir) |
| `<tabela>_lote_fechado` | `ingestao`, `arquivo_fonte`, `usuarios`, `crg_semestre`, `excecao`, `historico` | INSERT, UPDATE e DELETE de linha ligada a lote fechado |

Lote aberto aceita escrita — é assim que a importação grava tudo e fecha no fim
da mesma transação. Depois do COMMIT, nada daquele lote muda. Dado novo é
importação nova, em lote novo; os anteriores ficam intactos (relatórios, CSVs,
`lote.md` e linhas no banco).

---

## 3. Fluxo de importação

```
Usuário: responsável + historicos.zip
   │
   ▼  POST /lotes/importar  (multipart: responsavel, arquivo)
   │
   ├─ valida: responsável não vazio (≤100), arquivo .zip ........ 422 / 400
   ├─ id = AAAA-MM-Lnn; cria raw/lotes/<id>/historicos/
   ├─ extrai só os .pdf do zip (achata subpastas, ignora lixo,
   │  teto de 100 MB descomprimidos) ............................ 400 / 409 / 413
   ├─ INSERT lote (aberto)
   ├─ passo 1: FasiTech → fasitech.json congelado → usuarios ..... 502 / 503
   ├─ passo 2: cada PDF → historico (com período), crg_semestre,
   │           linha nova em usuarios para quem tem socioeconômico
   ├─ periodos_cobertos = períodos dos históricos legíveis
   │     nenhum legível → 422 ("período não pôde ser identificado")
   ├─ fechamento: SHA256SUMS, lote.md, vigente.csv,
   │              integrados.csv, nao_integrados.csv, fechado_em
   └─ COMMIT ─────────────────────────────────────────────────────→ 201

Qualquer erro: ROLLBACK + apaga raw/lotes/<id>/ e processed/<id>/.
```

Tela **Dados** (`/dados`): dois campos (responsável e arquivo `.zip`) e o botão
**Importar**, com confirmação ("o lote é fechado ao terminar"). Abaixo, o
seletor de lotes (todos fechados) e os relatórios do lote escolhido.

Linha de comando:

```bash
python scripts/lote.py importar --responsavel "Edinaldo" historicos.zip
python scripts/lote.py importar --responsavel "Edinaldo" ./pasta_com_pdfs   # o script compacta
python scripts/lote.py relatorio 2026-09-L02
```

---

## 4. Dashboards

| Onde | Mudança |
|---|---|
| `GET /alunos`, `GET /alunos/{matricula}` | leem `aluno_integrado`; não integrado dá 404 |
| `GET /crg-semestres` | só matrículas de `aluno_integrado` |
| Polos, Turmas, Alunos, Perfil, Análises | nenhuma mudança de cálculo: consomem `GET /alunos`, que já vem filtrado. Totais, KPIs, gráficos e comparativos passam a contar só integrados |
| Tela Polos | KPI "Alunos únicos" → **"Alunos integrados"**; subtítulo diz que só entram integrados |
| Selo do lote (cabeçalho) | mostra o período extraído; o tooltip explica que os indicadores usam só integrados |

A regra mora no banco (view), não no frontend: API, `vigente.csv`, consulta SQL
e dashboard não têm como divergir. No L01 real, o dashboard passa de 111 para
**56 alunos** — os 55 restantes têm só socioeconômico.

---

## 5. Relatórios

`GET /lotes/{id}/relatorio` → `{lote, resumo, integrados[], nao_integrados[]}`.
Os mesmos dados ficam congelados em `processed/<id>/integrados.csv` e
`nao_integrados.csv` no fechamento. Substituem `correspondencia` (rota e CSV).

**Base do relatório:** a base consolidada no fechamento do lote — tudo o que as
ingestões dele e das anteriores gravaram. Para o lote mais recente, os
integrados são exatamente os alunos do dashboard. Para um lote antigo, é o
retrato de quando fechou e não muda com lotes seguintes.

### Dados não integrados

| Matrícula | Nome | Acadêmico | Socioeconômico | Motivo | Sem resposta | Campos sem resposta | Preenchimento |
|---|---|---|---|---|---|---|---|

| Código | Motivo exibido | Quando |
|---|---|---|
| `sem_academico` | Possui socioeconômico e não possui acadêmico | respondeu o FasiTech, não há histórico |
| `sem_socioeconomico` | Possui acadêmico e não possui socioeconômico | há histórico, a matrícula não está no FasiTech |
| `falha_identificacao` | Falha de identificação | PDF ilegível / sem matrícula, ou registro do FasiTech sem período (o `Detalhe` diz qual) |
| `matricula_nao_encontrada` | Matrícula não encontrada | registro do FasiTech sem matrícula válida |

### Dados integrados

| Matrícula | Nome | Acadêmico | Socioeconômico | Status | Sem resposta | Campos sem resposta | Preenchimento |
|---|---|---|---|---|---|---|---|

`Status` = `Integrado com sucesso`.

### Completude (nos dois relatórios)

- **Campos avaliados:** os das fontes que o registro **tem**.
  - acadêmico: `CRG` (último semestre apurado);
  - socioeconômico: `genero, cor_etnia, pcd, tipo_deficiencia, renda,
    deslocamento, trabalho, assistencia_estudantil, gasto_internet,
    saude_mental, estresse, tipo_moradia, acesso_internet` — as perguntas que o
    FasiTech envia hoje (`polo` fica de fora: nunca vem e é derivado da matrícula).
- `tipo_deficiencia` só conta para quem respondeu `pcd = Sim`.
- Vazio = `NULL` ou texto em branco. `Prefiro não responder` **é** resposta.
- `percentual_preenchimento = respondidos / avaliados × 100` (1 casa). Sem campo
  a avaliar (registro sem matrícula) → `—`.
- A falta de uma fonte inteira não vira 13 "campos sem resposta": ela já é o motivo.

Exemplo (`GET /lotes/{id}/relatorio`, trecho):

```json
{"matricula": 202016040011, "nome": "…", "academico": true, "socioeconomico": true,
 "status": "Integrado com sucesso", "campos_avaliados": 13,
 "qtd_campos_sem_resposta": 3, "campos_sem_resposta": ["renda", "trabalho", "acesso_internet"],
 "percentual_preenchimento": 76.9}
```

---

## 6. Evidências de validação

### Testes automatizados

| Suíte | Resultado |
|---|---|
| Backend (`pytest`, PostgreSQL real) | 101 passaram |
| Frontend (`vitest`) | 171 passaram |
| `tsc -b` | sem erros |
| `npm run build` | ok |
| `oxlint` | só os 2 avisos que já existiam (`main.tsx`, `DadosProvider.tsx`) |
| `alembic upgrade head` → `downgrade b7c4e9a21d38` → `upgrade head`; `alembic check` | ok; modelos e migrações em sincronia |

Sem Docker na máquina, a suíte roda contra um PostgreSQL já de pé:

```bash
TEST_POSTGRES_URL=postgresql+psycopg://postgres@localhost:55432/postgres pytest -q
```

(Com Docker, `pytest -q` continua subindo o contêiner como antes.)

| Regra | Testes que provam |
|---|---|
| 1. Período extraído automaticamente | `test_importacao.py::test_periodo_e_extraido_da_data_de_emissao_dos_historicos`, `::test_nenhum_historico_legivel_da_422_porque_nao_ha_periodo` |
| 2. Usuário informa só responsável e .zip | `test_importacao.py::test_importar_sem_responsavel_da_422_e_nao_grava_nada`, `::test_importar_arquivo_que_nao_e_zip_da_400`, `::test_rotas_de_edicao_de_lote_nao_existem_mais`; `ImportarLote.test.tsx` (2 inputs, sem período nem id); `api.test.ts` (multipart só com `responsavel` e `arquivo`) |
| 3. Lote fechado não se altera | `test_imutabilidade.py` (5 testes, SQL direto contra os triggers); `test_importacao.py::test_segunda_importacao_cria_lote_novo_e_preserva_o_anterior`; atomicidade: `::test_fasitech_fora_do_ar_da_502_e_desfaz_tudo`, `test_lotes.py::test_falha_depois_de_gravar_arquivos_desfaz_banco_e_disco` |
| 4. Dashboards só com integrados | `test_alunos.py::test_aluno_sem_academico_nao_aparece`, `test_crg_semestres.py::test_historico_sem_socioeconomico_nao_entra_na_trajetoria`, `test_schema.py::test_vigente_resolve_pela_ingestao_mais_recente` (view `aluno_integrado`) |
| 5. Relatórios corretos | `test_relatorio.py::test_relatorio_separa_integrados_e_nao_integrados_com_motivo` (os 4 motivos), `::test_integrados_do_ultimo_lote_sao_exatamente_os_alunos_do_dashboard`, `::test_relatorio_de_lote_antigo_e_o_retrato_do_fechamento`; `test_lotes.py` (CSVs) |
| 6. Campos sem resposta nos dois relatórios | `test_relatorio.py::test_os_dois_relatorios_trazem_campos_sem_resposta` e os 5 testes de `completude`; `RelatorioLote.test.tsx` |

### Com os dados reais do L01

Os 56 PDFs do L01 num `.zip` + o `fasitech.json` congelado do L01 (no lugar da
chamada de rede), num banco descartável:

```
status 201 (7.3s)
periodos_cobertos (extraídos): ['2025.2']
arquivos: gravados 56 ignorados 0
passo1: importados 187, rejeitados 0
passo2: pdfs_lidos 56, semestres_gravados 258, alunos_atualizados 87, ilegiveis 0
resumo: total 111, integrados 56, nao_integrados 55 (todos sem_academico), preenchimento médio 62.9%
GET /alunos: 87 registros, 56 matrículas
integrados do relatório == matrículas do dashboard: True
matrículas em /crg-semestres ⊆ integrados: True (258 pontos)
aluno_vigente: 111 matrículas | aluno_integrado: 56
linhas com campos de completude: 111 de 111
UPDATE lote fechado recusado:  "Lote … está fechado …: não pode ser alterado nem apagado."
DELETE em usuarios do lote recusado: "… usuarios não aceita escrita ligada a ele."
rotas antigas: POST /lotes 405, /fechar 404, /historicos 404, /alunos/sincronizar 405, /alunos/atualizar-crg 405
```

### Achado dos dados reais (para decidir)

Entre os 56 integrados, os campos mais sem resposta são:

| Campo | Sem resposta |
|---|---|
| `trabalho` | 56 de 56 |
| `acesso_internet` | 56 de 56 |
| `renda` | 55 de 56 |
| `deslocamento` | 48 de 56 |
| `CRG` | 23 de 56 (nenhum semestre apurado até a emissão) |

`trabalho` e `acesso_internet` vêm nulos em **187 de 187** registros do
FasiTech, `renda` em 184. Isso tem cara de campo não mapeado na fonte, não de
aluno que deixou de responder. Os indicadores "Renda até 1 SM", "Trabalho
informal" e "Sem acesso à internet" dependem deles. Vale confirmar com o
FasiTech antes de ler esses indicadores.

---

## 7. Operação

Passo a passo (tela, terminal e Swagger, tabela de erros, commit no
repositório de dados) em `docs/operacao_lote.md`.
