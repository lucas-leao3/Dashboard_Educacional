# Primeiro lote (L01): rodar a governança de ponta a ponta e ligar o dashboard à API

**Data:** 12/09/2026
**Contexto:** a governança por lote está implementada no backend (`POST /lotes`, `/alunos/sincronizar`, `/alunos/atualizar-crg`, view `aluno_vigente`), mas nenhum lote foi rodado: `data/raw/lotes/` está vazio, os 56 PDFs seguem em `backend/app/data/historicos/`, e o frontend roda em modo demonstração por falta de `VITE_API_URL`. Este documento define o que falta para rodar o L01, fechar o lote e deixar o dashboard lendo dado real enquanto o L02 não chega.

## Decisões tomadas

| Decisão | Escolha | Por quê |
|---|---|---|
| Fonte do socioeconômico no L01 | API do FasiTech (credenciais em `backend/.env`) | É a fonte oficial; o `fasitech.json` do L01 nasce aqui. |
| Dados legados (`DadosAgrupados.csv`) | **Abandonados.** Passo 3 (`/preencher-legado`) é removido do código. | O L01 passa a ser API + PDF. Deixar a rota viva é convite pra rodar por engano num lote. |
| Ambiente do L01 | `docker compose` (PostgreSQL) | É o desenho da governança (seção 6). Lotes em `./data`, montado no container como `/data`. |
| Operação | Script `scripts/lote.py` (`abrir` / `rodar` / `fechar`) + roteiro em `docs/operacao_lote.md` | Repetível no L02 sem lembrar de curl. |
| Fechamento do lote | `SHA256SUMS` + `lote.md` em `raw/`; `vigente.csv` + `correspondencia.csv` em `processed/<lote>/` | O corte transversal e os dados ausentes saem por lote, regeneráveis do banco. |
| Frontend | Trocar para a API + selo do lote vigente no `AppShell` | Deixa claro de onde vem o dado. |

## 1. Ligação frontend ↔ backend

Já existe: `carregarRegistros()` busca `${VITE_API_URL}/alunos` com fallback para a demonstração; o Vite faz proxy de `/api` para `localhost:8000`; o nginx do compose faz o mesmo para `backend:8000`; o compose injeta `VITE_API_URL=/api` no bundle.

Falta:

- `frontend/.env.development` (versionado) com `VITE_API_URL=/api`, para o `vite dev` usar o proxy em vez de cair na demonstração. Backend fora → fallback atual continua valendo.
- `backend/.env` com `FASITECH_URL` e `FASITECH_TOKEN` preenchidos (fora do git; responsabilidade do operador).

Nenhuma mudança de contrato: `GET /alunos` devolve `aluno_vigente`, que é o `Registro` do frontend.

## 2. Backend

### 2.1. Remover o passo 3

Apagar: rota `POST /alunos/preencher-legado` em `api/alunos.py`, `services/dados_legado.py`, a constante `Ingestao.PASSO_LEGADO`, os testes que os cobrem, e a menção em `API_README.md`. O `DadosAgrupados.csv` e os `relatorio_*.csv` em `backend/app/data/` ficam onde estão (já fora do git) até decisão separada de apagar.

Consequência a declarar no `lote.md`: campos que o legado preenchia e o FasiTech não traz ficam `NULL`. Nome e nascimento continuam vindo do PDF (passo 2). É limitação declarada da fonte, não defeito do lote.

### 2.2. `GET /lotes/{id}/excecoes`

Nova rota em `api/lotes.py`. Devolve a lista de exceções do lote, uma por linha:

```json
[{"ingestao_id": 3, "passo": 2, "matricula": 202016040002, "periodo": "2025.2", "motivo": "sem_academico", "detalhe": null}]
```

Ordenada por `passo, matricula, periodo`. 404 se o lote não existir. Schema `ExcecaoOut` em `schemas/lotes.py`. É o que o relatório de correspondência precisa — `LoteOut.excecoes_por_motivo` só tem a contagem.

## 3. `scripts/lote.py`

Script Python de linha de comando, rodando na máquina host (fora do container), usando `httpx` (já é dependência). Parâmetros globais: `--api` (padrão `http://localhost:8000`), `--dados` (padrão `./data`, a raiz que o compose monta).

| Subcomando | Faz | Falha quando |
|---|---|---|
| `abrir <id> --periodos P1 [P2 …] --por "nome" [--obs "…"]` | `POST /lotes`. Imprime o caminho `data/raw/lotes/<id>/historicos/` onde o operador copia os PDFs. | 409 se o lote já existe (repassa a mensagem da API). |
| `rodar <id>` | `POST /alunos/sincronizar?lote=<id>` e depois `POST /alunos/atualizar-crg?lote=<id>`. Imprime os contadores de cada passo. | Para no primeiro erro HTTP e sai com código ≠ 0; o passo seguinte não roda. |
| `fechar <id>` | Ver abaixo. | Recusa se `data/raw/lotes/<id>/lote.md` já existir (lote fechado não se reabre). Recusa se o lote não tiver as ingestões 1 e 2. |

### 3.1. O que `fechar` gera

Em `data/raw/lotes/<id>/` (insumo, imutável):

- `SHA256SUMS`: hash de todos os arquivos do lote exceto ele mesmo e `lote.md`, no formato de `sha256sum` (`<hash>  <caminho relativo>`), para `sha256sum -c` funcionar.
- `lote.md`: id, períodos cobertos, quem executou, `executado_em`; por ingestão: passo, `executado_em`, lidos/aceitos/rejeitados; exceções por motivo; lista dos arquivos com hash; seção "Limitações" com texto fixo sobre os campos que a fonte não traz. Tudo vindo de `GET /lotes/{id}` — o script não inventa número.

Em `data/processed/<id>/` (derivado, regenerável):

- `vigente.csv`: `GET /alunos` como está, uma linha por `(matricula, periodo)`, colunas na ordem de `AlunoOut`. É o corte transversal da seção 4.7 da governança.
- `correspondencia.csv`: uma linha por matrícula, colunas `Matricula, Nome, Academico, SocioEconomico, Dado_Faltando`. Cruza `GET /alunos` (quem tem socioeconômico) com `GET /lotes/{id}/excecoes`: `sem_academico` → `Academico=Não`; `sem_socioeconomico` → `SocioEconomico=Não`. `Dado_Faltando` é vazio, `Academico`, `SocioEconomico` ou `Ambos`. Sucede os `relatorio_correspondencia*.csv` antigos, agora por lote.

`data/processed/` já está coberto pelo `.gitignore` (`data/`). Não vai para o repositório privado de dados: é regenerável.

### 3.2. Testes

`tests/test_script_lote.py`, com `httpx.MockTransport` e diretório temporário:

- `rodar` chama sincronizar antes de atualizar-crg; se sincronizar falhar, atualizar-crg não é chamado e o processo sai com erro.
- `fechar` gera `SHA256SUMS` verificável (recalcular e comparar), `lote.md` contendo os contadores da resposta simulada, `vigente.csv` com as colunas de `AlunoOut`, `correspondencia.csv` classificando corretamente os quatro casos (completo, sem acadêmico, sem socioeconômico, ambos).
- `fechar` recusa quando `lote.md` já existe.

`tests/test_lotes.py` ganha o caso de `GET /lotes/{id}/excecoes` (lista, ordem, 404).

## 4. Frontend: selo do lote

- `data/api.ts`: `carregarLotes(opcoes)` → `GET {baseUrl}/lotes`; devolve `Lote[]` (tipo espelhando `LoteOut`) ou `[]` em erro.
- `DadosProvider`: carrega os lotes junto com os registros e expõe `lote: Lote | null` = o último por `executado_em` com ao menos uma ingestão.
- `components/SeloLote.tsx`: renderiza `Lote <id> · <dd/mm/aaaa> · <N> exceções`, com `title` listando as exceções por motivo. `N` é a soma de `excecoes_por_motivo`.
- `AppShell`: mostra o selo quando `origem === 'api'` e `lote` existe, no mesmo lugar do selo "Dados de demonstração".
- Teste em `paginas.test.tsx`: com API simulada devolvendo um lote, o selo aparece com id e contagem; sem lotes, não aparece.

## 5. Documentação

- `docs/operacao_lote.md` (novo): roteiro de ponta a ponta com o script — pré-requisitos (`.env`, `docker compose up`), `abrir`, copiar PDFs, `rodar`, conferir o dashboard em `:8080`, `fechar`, commit em `dashboard-dados`. Seção final "O que muda no L02": PDFs novos do SIGAA (incluindo os que faltaram no L01), sem passo 3, comparar `correspondencia.csv` dos dois lotes.
- `docs/governanca_dados.md`: seção 3.2 — árvore e tabela sem `DadosAgrupados.csv`, `processed/<lote>/` em vez de `processed/relatorios/`; seção 5 — fluxo em dois passos; seção 7 — marcar o que está feito e apontar para o roteiro. Aposentar `backend/app/data/ONDE_COLOCAR.txt`.
- `API_README.md`: remover `/preencher-legado`, adicionar `GET /lotes/{id}/excecoes`.

## 6. Execução do L01

Depois do código pronto e testado:

1. `docker compose up -d --build`; operador preenche `backend/.env`.
2. `python scripts/lote.py abrir 2026-09-L01 --periodos <…> --por "<nome>"`. Os períodos cobertos são os que o FasiTech devolver — conferir no `fasitech.json` congelado antes de fechar; se divergirem do informado em `abrir`, registrar no `--obs`.
3. `cp backend/app/data/historicos/*.pdf data/raw/lotes/2026-09-L01/historicos/`
4. `python scripts/lote.py rodar 2026-09-L01`
5. Conferir `http://localhost:8080`: selo do lote, contagem de alunos, exceções.
6. `python scripts/lote.py fechar 2026-09-L01`
7. Commit de `data/raw/lotes/2026-09-L01/` no repositório privado `dashboard-dados`.

`backend/app/data/` não é tocado nesta rodada.

## Fora do escopo

- Expor `crg_semestre` ao frontend (Trajetória por semestre).
- Página de exceções por matrícula no dashboard.
- Apagar `backend/app/data/`.
