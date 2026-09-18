# Tela "Dados": inserção de lote + cobertura do lote

Data: 2026-09-18. Depende da governança por lote já implementada
(`docs/governanca_dados.md`) e dos endpoints `POST /lotes/{id}/historicos?executar=true`
e `POST /lotes/{id}/fechar`.

## Objetivo

Uma página do dashboard onde o pesquisador **insere um lote** (abrir → enviar
PDFs e rodar → conferir e fechar) e vê, na mesma tela, a **cobertura do lote**:
quantos alunos entraram, quantos têm acadêmico e socioeconômico, quem falta o
quê. É o "corte transversal" da governança (§4.7, `aluno_vigente` /
`correspondencia.csv`) na tela, ao lado da inserção que o produz.

Princípio: simples. Sem biblioteca nova, sem estado global além do que o
`DadosProvider` já tem, sem lógica de negócio no frontend que já exista no
backend.

## Fora de escopo

- Autenticação (a API continua só em `localhost`; §3.5 da governança).
- Editar observação do lote, reabrir lote, apagar lote.
- Indicadores de desempenho (CRG, sinalizações) — continuam nas páginas Polos/Turmas.
- Download dos CSVs pela tela (ficam em `data/processed/<lote>/`).

## Backend: um endpoint de leitura

`GET /lotes/{id}/correspondencia` → `200`

```json
[{"matricula": 202016040001, "nome": "Ana", "academico": true, "socioeconomico": false, "faltando": "SocioEconomico"}]
```

`faltando` ∈ `""`, `"Academico"`, `"SocioEconomico"`, `"Ambos"`. Ordenado por
matrícula. `404` se o lote não existe.

Implementação: em `services/fechamento.py`, a montagem da correspondência sai
de `_escrever_correspondencia_csv` para uma função `correspondencia(alunos,
excecoes) -> list[Correspondencia]`; o CSV e a rota consomem a mesma lista.
Saída do CSV não muda (testes existentes cobrem).

## Frontend

### Rota e navegação

- `/dados`, item **Dados** no grupo Navegação da `Sidebar`.
- `AppShell` com `semFiltros` (período não se aplica).
- Sem API (`origem === 'demonstracao'`): a página mostra só o aviso
  "A inserção de dados exige a API" — nenhum formulário.

### Arquivos

```
src/pages/Dados.tsx                   seletor de lote + <InserirLote> + <CoberturaLote>
src/components/lote/InserirLote.tsx   stepper de 3 passos; renderiza o passo atual
src/components/lote/PassoAbrir.tsx    id (sugerido), períodos, executado_por
src/components/lote/PassoEnviar.tsx   input de arquivos (.zip/.pdf, múltiplos) + "Enviar e rodar" + resultado
src/components/lote/PassoFechar.tsx   resumo do lote + "Fechar lote" (com confirmação)
src/components/lote/CoberturaLote.tsx KPIs + exceções por motivo + tabela de correspondência
src/domain/lote.ts                    passoAtual, sugerirIdLote, validarIdLote, filtrarArquivosAceitos
src/hooks/fluxoLote.ts                criarFluxoLote({ api, recarregar, confirmar }) → { abrir, enviar, fechar }
src/data/api.ts                       + abrirLote, enviarHistoricos, fecharLote, carregarLote, carregarCorrespondencia, ErroApi
src/data/tipos.ts                     + Lote.fechado_em, HistoricosOut, Correspondencia
```

### Máquina de estados (`passoAtual(lote)`)

Derivada só do que a API devolve. Recarregar a página cai no passo certo.

| Lote selecionado | Passo |
|---|---|
| nenhum / "Novo lote" | 1 Abrir |
| sem ingestão de passo 2 | 2 Enviar e rodar |
| ingestões 1 e 2, `fechado_em` nulo | 3 Conferir e fechar |
| `fechado_em` preenchido | nenhum — selo "Fechado em …", só a cobertura |

Stepper mostra os três passos (feito / atual / pendente); só o atual é interativo.

### Cliente de API

Mesmo padrão das funções existentes (`baseUrl`/`fetchFn` injetáveis), mas
**escrita não cai em demonstração**: erro HTTP lança `ErroApi { status, detail }`
com o `detail` do FastAPI; `fetch` rejeitado lança `ErroApi { status: 0,
detail: "Sem resposta da API" }`.

| Função | Chamada |
|---|---|
| `abrirLote({ id, periodos_cobertos, executado_por })` | `POST /lotes` |
| `enviarHistoricos(id, arquivos: File[])` | `POST /lotes/{id}/historicos?executar=true`, `FormData` com um campo `arquivos` por arquivo |
| `fecharLote(id)` | `POST /lotes/{id}/fechar` |
| `carregarLote(id)` | `GET /lotes/{id}` |
| `carregarCorrespondencia(id)` | `GET /lotes/{id}/correspondencia` |

### `DadosProvider`

Ganha `lotes: Lote[]` (a lista inteira; hoje guarda só o vigente) e
`recarregar(): Promise<void>` (refaz `carregarRegistros` + `carregarLotes`).
É o que faz Polos/Turmas refletirem o lote assim que o passo 2 termina.

### Orquestração (`criarFluxoLote`)

Função pura de dependências, sem React:

```ts
criarFluxoLote({ api, recarregar, confirmar = () => window.confirm(TEXTO_FECHAR) })
  → { abrir(form), enviar(id, arquivos), fechar(id) }
```

Cada ação devolve `{ ok: true, dados } | { ok: false, erro: string | null }`. No `ok`
chama `recarregar()`; no erro não. `fechar` sem confirmação devolve
`{ ok: false, erro: null }` sem chamar a API. A página só liga isso aos botões
e guarda `ocupado`, `erro` por passo e `resultadoEnvio`.

### Estado local da página

- `loteSelecionadoId` — do seletor; padrão = lote vigente; opção "Novo lote".
- `ocupado` — trava botões e seletor durante qualquer chamada.
- `resultadoEnvio: HistoricosOut | null` — gravados, ignorados, contadores dos passos.
- `correspondencia` — carregada quando o lote muda e após enviar/fechar.

### Sequência do caso feliz

1. Abrir → `abrirLote` → `recarregar()` → seletor aponta o lote novo → passo 2.
2. Escolher arquivos → "Enviar e rodar" → `enviarHistoricos` → `recarregar()` +
   `carregarCorrespondencia` → passo 3; resultado e cobertura aparecem juntos.
3. "Fechar lote" → `confirm` ("Fechar é definitivo…") → `fecharLote` →
   `recarregar()` → passo some, selo "Fechado em".

### Sugestão de id

`sugerirIdLote(hoje, lotes)`: `AAAA-MM-Lnn` com o mês atual e `nn` = maior
sequência do mês + 1 (`L01` se não há nenhum no mês). Campo editável; validação
`^[A-Za-z0-9_-]{3,20}$` (a do backend) antes de enviar.

### Erros

Todo erro vira uma faixa **no passo onde aconteceu**, com o `detail` do backend
em texto. A máquina de estados só avança quando `recarregar()` traz o lote mudado.

| Situação | API | Tela |
|---|---|---|
| Abrir com id existente | 409 | Faixa no passo 1 |
| Id fora do padrão | — | Campo em erro, sem chamar a API |
| Sem arquivo escolhido | — | Botão desabilitado |
| Extensão não aceita | — | Rejeitado antes de enviar, com o nome e "só .zip ou .pdf" |
| Zip corrompido / nome repetido com conteúdo diferente | 400 / 409 | Faixa no passo 2 |
| FasiTech fora / não configurado | 502 / 503 | Faixa no passo 2: "PDFs gravados; reenvie os mesmos arquivos para retomar" |
| Fechar sem os dois passos | 409 | Botão já desabilitado; se chegar, faixa no passo 3 |
| Lote fechado em outra aba | 409 | Faixa + `recarregar()` faz o passo sumir |
| Rede caiu no upload | fetch rejeita | Faixa "Sem resposta da API"; reenvio é idempotente |
| Correspondência falhou | qualquer | Cobertura mostra "não foi possível carregar"; resto continua |

## Testes

Sem `jsdom`/`testing-library`: lógica pura com vitest, telas por `renderToString`
(padrão do repo).

**Backend** (`tests/test_lotes.py`): correspondência com os quatro casos
(completo, só acadêmico faltando, só socioeconômico, ambos), ordenada; 404 em
lote inexistente. CSV do `fechar` inalterado.

**`src/domain/lote.test.ts`**: `passoAtual` (4 estados); `sugerirIdLote` (sem
lotes, mesmo mês com L01/L02 → L03, mês diferente → L01); `validarIdLote`;
`filtrarArquivosAceitos` (`.zip`/`.pdf` qualquer caixa; resto rejeitado com nome).

**`src/data/api.test.ts`** (fetch falso): `enviarHistoricos` monta o `FormData`
e usa `executar=true`; cada função lança `ErroApi` com `status`/`detail`; fetch
rejeitado → "Sem resposta da API"; `carregarLotes` continua caindo em `[]`.

**`src/hooks/fluxoLote.test.ts`** (api falsa): caso feliz chama `recarregar`
após cada ação; erro → `{ ok: false, erro: detail }` e não recarrega; `fechar`
sem confirmação não chama a API.

**`src/pages/paginas.test.tsx`**: sem API → aviso e nenhum formulário; lote sem
ingestões → passo 2 ativo com input de arquivos; lote com passos 1 e 2 → botão
"Fechar lote"; fechado → selo "Fechado em", sem botão; `CoberturaLote` com os
quatro casos → KPIs certos e quatro linhas.

**Roteiro manual** (Docker no ar, FasiTech configurado): abrir `2026-09-L01` →
enviar `historicos_L01.zip` → conferir 103 alunos / 47 `sem_academico` na
cobertura e o selo do lote no AppShell → fechar → `data/raw/lotes/2026-09-L01/lote.md`
existe e a página mostra "Fechado em".
