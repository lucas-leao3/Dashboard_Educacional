# Assistente de consultas em linguagem natural — fatia vertical

Data: 2026-09-25. Substitui o placeholder `/ia-chat` (`main.tsx`, `BotaoIA.tsx`).

## Objetivo

O usuário pergunta em português ("compare renda familiar por polo") e recebe a
resposta na forma mais adequada — **dashboard existente com filtros**,
**dashboard dinâmico**, **tabela** ou **texto** — sempre com a explicação do
que foi entendido. Esta fatia atravessa todas as camadas de forma estreita.
Ampliar o catálogo e os tipos de gráfico fica para fatias seguintes.

## Decisões

| # | Decisão | Motivo |
|---|---|---|
| D1 | LLM na nuvem (**Groq**, API compatível com OpenAI, via `httpx` — sem dependência nova) atrás de uma interface `ProvedorLLM` | Troca de provedor vira configuração |
| D2 | **O LLM vê só a pergunta anonimizada e o catálogo. Nunca vê linha de aluno nem resultado** | Saúde mental e renda ligadas à matrícula não saem da máquina (governança §3.5, LGPD) |
| D3 | **Camada semântica**: o LLM devolve uma `ConsultaEstruturada` (JSON); o SQL é montado pelo backend. O modelo nunca escreve SQL | Segurança por construção; as regras da base (integrados, CRG em dois eixos, ausência ≠ zero) ficam no compilador, onde o LLM não as quebra |
| D4 | "Agentes" são etapas de um pipeline: **1 chamada ao LLM** (intenção) + planejador, compilador e visualização determinísticos | Rápido, barato, testável com pytest, defensável em banca |
| D5 | Histórico, favoritos e compartilhamento no **navegador** (`localStorage` + link) | Não há login; a API segue só em `localhost` |

## Fora de escopo

Autenticação e rate limit (só entram se a API sair do `localhost`, e juntos) ·
text-to-SQL livre (evolução possível: fallback rotulado "consulta livre") ·
heatmap, scatter, área e mapa (a base não tem coordenadas nem uma segunda
métrica numérica) · evasão (não há dado) · histórico no servidor.

## Arquitetura

```
frontend /ia-chat ──POST /assistente/perguntar──▶ api/assistente.py
                  ──POST /assistente/executar───▶   └ services/assistente/
                  ◀── RespostaAssistente ─────────       catalogo.py      fonte única
                  navigate(rota?filtros)                 anonimizador.py  nome/matrícula → ⟨A1⟩
                                                         provedor_llm.py  ProvedorLLM, Groq
                                                         intencao.py      pergunta → ConsultaEstruturada
                                                         planejador.py    forma da resposta
                                                         compilador.py    consulta → Select → linhas
                                                         visualizacao.py  gráfico pela forma do resultado
                                                         respostas.py     templates de texto
                                                              │ role leitor_assistente
                                                              ▼ SELECT em views do catálogo
```

### Backend

- **`catalogo.py`**: métricas, dimensões, filtros, listas, itens operacionais e
  dashboards existentes (rota + filtros aceitos). Os valores válidos de `polo`,
  `turma` e `periodo` são lidos do banco a cada pergunta, porque a base é
  pequena. O catálogo gera o texto do prompt **e** a validação Pydantic: o que
  não está nele não existe para o assistente.
- **`anonimizador.py`**: antes do LLM, troca qualquer sequência de 9 ou mais
  dígitos, e todo nome da base (`historico.nome`, `usuarios.nome`, comparado sem
  caixa e sem acento, com pelo menos 2 palavras), por `⟨A1⟩`, `⟨A2⟩`… O
  mapeamento fica na requisição, e o compilador resolve o marcador de volta
  para a matrícula.
- **`provedor_llm.py`**: `interpretar(pergunta, catalogo) -> dict`. A
  implementação Groq usa `POST {GROQ_URL}/chat/completions` com
  `response_format: json_object`, `temperature: 0` e timeout de 20 s.
  Configuração em `core/config.py`: `GROQ_API_KEY`, `GROQ_MODELO`, `GROQ_URL`
  (e no `.env.example`). Nos testes entra um `ProvedorFalso`.
- **`intencao.py`**: valida o JSON contra o catálogo. Se for inválido, faz **uma**
  nova tentativa mandando o erro de validação ao modelo. Se falhar de novo, a
  forma é `nao_entendi`.
- **`planejador.py`** (regras, nesta ordem):
  1. `tipo = fora_do_catalogo` → `nao_entendi`.
  2. A métrica e todos os filtros cabem num dashboard do catálogo → `dashboard`. Nada é executado.
  3. `lista` → `tabela`.
  4. Resultado escalar (sem dimensão) → `texto`.
  5. Qualquer outro caso → `dinamico`.
- **`compilador.py`**: produz um `sqlalchemy.Select` (verificado com `isinstance`
  antes de executar) sobre `aluno_integrado` e `crg_semestre_vigente`. Itens
  operacionais chamam os serviços que já existem (`relatorio_do_lote`, tabelas
  `lote`/`ingestao`), para os números saírem iguais aos de `/dados`. Regras
  obrigatórias:
  - **Aluno se conta por `COUNT(DISTINCT matricula)`.** `aluno_integrado` tem uma
    linha por (matrícula, período).
  - **`crg_medio` usa um CRG por aluno.** O CRG de `/alunos` é constante por
    aluno; contar uma vez por período daria mais peso a quem tem mais períodos.
  - Trajetória por semestre vem **só** de `crg_semestre_vigente`. `crg` nulo vira `null`, nunca `0`.
  - Polo é `polo_nome` (derivado da matrícula); a coluna `polo` vem nula do FasiTech.
  - Resposta ausente é uma categoria "Sem resposta" explícita, nunca descartada em silêncio.
  - `LIMIT 1000` nas listas.
- **`visualizacao.py`**: ver a tabela "Regras de visualização" abaixo.
- **Execução**: numa transação própria, `SET LOCAL ROLE leitor_assistente` e
  `SET LOCAL statement_timeout = '5s'`. O `LOCAL` faz os dois morrerem com a
  transação, sem vazar para outras requisições do pool. Uma migração Alembic
  cria a role (`NOLOGIN`, com `GRANT leitor_assistente TO current_user`) e
  concede `GRANT SELECT` só em
  `aluno_integrado`, `crg_semestre_vigente`, `lote`, `ingestao`, `excecao` e
  `polo`. INSERT, UPDATE, DELETE, DROP, ALTER e TRUNCATE são recusados **pelo
  banco**.
- **Log**: pergunta anonimizada, `ConsultaEstruturada`, forma e duração. Nunca o resultado.

### Frontend

- **`domain/filtrosUrl.ts`** + hook `useFiltroUrl(nome, padrao)`: os filtros das
  telas-alvo passam de `useState` para query string. O período global passa a
  ser lido de `?periodo=` (sem o parâmetro, vale "Todos"), e os links internos o
  preservam.
- **`domain/catalogoDashboards.ts`**: monta a URL a partir do bloco `dashboard`
  da resposta. As rotas ficam aqui, e não no backend.
- **`pages/IaChat.tsx`**: campo de pergunta, lista de respostas e histórico
  lateral. Componentes em `components/assistente/`: `Explicacao`,
  `RespostaTexto`, `RespostaTabela` (paginação de 25 e exportação CSV no
  navegador), `DashboardDinamico` (KPIs + gráficos, reaproveitando
  `ChartDistribuicao`, `BarrasDimensao` e `ChartLongitudinal` onde couber) e
  `Historico`.
- **Forma `dashboard`**: mostra a explicação e navega com `navigate()`. A tela
  de destino exibe os filtros aplicados porque eles estão na URL.
- **Modo demonstração** (sem API): o chat mostra um aviso e fica desabilitado.

## Contratos

`POST /assistente/perguntar {pergunta: str (1–500)}` e
`POST /assistente/executar {consulta: ConsultaEstruturada}` devolvem
`RespostaAssistente`. `/executar` não chama o LLM.

```
ConsultaEstruturada
  tipo:        agregado | lista | operacional | fora_do_catalogo
  metrica:     id do catálogo | null
  dimensoes:   [id]  (0–2)
  filtros:     [{campo, op: "=" | "in" | "entre", valor}]  (valor existente no catálogo, ou ⟨An⟩)
  ordem:       {campo, direcao} | null
  limite:      int | null
  interpretacao: str   (paráfrase do modelo, exibida ao usuário)

RespostaAssistente
  id, pergunta, consulta: ConsultaEstruturada
  forma:      dashboard | dinamico | tabela | texto | nao_entendi
  explicacao: {consulta_interpretada, filtros_aplicados: [{rotulo, valor}], fontes: [view], forma}
  dashboard:  {id, params}
  dinamico:   {kpis: [{rotulo, valor, n}], graficos: [{tipo, titulo, dados, n_por_grupo}]}
  tabela:     {colunas: [{id, rotulo}], linhas, total}
  texto:      {mensagem, valor, n}
  nao_entendi:{motivo, sugestoes: [str]}
```

Só o bloco da forma escolhida vem preenchido. O `n` acompanha todo grupo.

## Catálogo desta fatia

| Tipo | Itens |
|---|---|
| Métricas | `contagem_alunos`, `crg_medio`, `distribuicao` (alunos por resposta), `crg_medio_semestre` |
| Dimensões/filtros | `polo`, `turma`, `periodo`, `semestre` (só com `crg_medio_semestre`), `matricula` (só por marcador), `renda`, `genero`, `cor_etnia`, `trabalho`, `assistencia_estudantil`, `saude_mental`, `estresse`, `deslocamento`, `tipo_moradia`, `acesso_internet`, `computador_proprio`, `escolaridade_pai`, `escolaridade_mae`, `pcd` |
| Listas | `alunos`, `alunos_incompletos` (integrados com campo sem resposta), `nao_integrados` (com motivo) |
| Operacionais | `resumo_ultimo_lote`, `campos_sem_resposta` |
| Dashboards | Polos `/?periodo=` · Turmas `/polo/:polo?periodo=` · Alunos `/polo/:polo/turma/:turma?periodo=&sinal=&dimensao=` · Perfil `/aluno/:matricula` · Análises `bidimensional?dimensao=`, `distribuicao`, `longitudinal` · Dados `/dados` |

Dimensões ordinais, com a ordem natural fixada no catálogo: `renda`,
`escolaridade_*`, `turma`, `periodo`, `semestre`.

### Casos de aceitação (viram o teste por tabela do planejador)

| Pergunta | Forma esperada |
|---|---|
| Quantos alunos existem por polo? | dashboard Polos |
| Mostre os alunos do polo de Cametá | dashboard Turmas `/polo/Cametá` |
| Mostre a evolução dos indicadores acadêmicos por semestre | dashboard Longitudinal |
| Qual a distribuição de renda familiar dos alunos? | dinâmico: barras |
| Compare renda familiar por polo | dinâmico: barras empilhadas 100% |
| Quais campos possuem mais respostas ausentes? | dinâmico: barras horizontais |
| Quantos alunos ingressaram em 2020? | texto |
| Quantos registros foram integrados no último lote? | texto |
| Liste os alunos com dados incompletos | tabela |
| Quais alunos não possuem dados socioeconômicos? | tabela (`nao_integrados`, motivo `sem_socioeconomico`) |
| Quais polos possuem maior evasão? | nao_entendi ("a base não tem dado de evasão") |

## Regras de visualização

| Forma do resultado | Visualização |
|---|---|
| Sem dimensão, 1 valor | KPI |
| 1 dimensão temporal (`semestre`, `periodo`) | linha, com lacuna em `null` |
| 1 dimensão categórica, parte-do-todo, até 5 categorias | rosca |
| 1 dimensão categórica (demais casos) | barras horizontais: ordinal na ordem natural, nominal ordenada por valor |
| 2 dimensões | barras empilhadas 100%, com o n de cada barra |
| CRG por aluno | histograma (`ChartDistribuicao`) |
| Lista | tabela |

Cores de `theme/cores.ts` (polo com a cor fixa que já tem). "Sem resposta" em
cinza hachurado, como nas telas atuais.

## Histórico (navegador)

`localStorage["assistente.historico"]`: até 100 itens `{id, pergunta, consulta,
forma, quando, favorito}`. Favoritos ficam no topo e não entram no descarte dos
mais antigos. Todo acesso ao `localStorage` fica em `try/catch`.

- **Repetir** → `/executar` com a `consulta` salva.
- **Editar** → devolve a pergunta ao campo.
- **Compartilhar**: forma `dashboard` → a URL do dashboard; demais formas →
  `/ia-chat?c=<base64url(consulta)>`, que chama `/executar` ao abrir.

## Erros

| Situação | Resposta |
|---|---|
| `GROQ_API_KEY` ausente, Groq fora, timeout ou 429 | `503 {detail}`. `/executar` e o histórico seguem funcionando |
| JSON inválido após a nova tentativa | `200`, forma `nao_entendi` com sugestões |
| `consulta` inválida em `/executar` | `422` |
| `statement_timeout` | `504 {detail}` |
| Resultado vazio | `texto`: "Nenhum aluno com esses filtros." Nunca gráfico zerado |

## Testes

**pytest** (PostgreSQL via testcontainers, como a suíte atual), em `tests/assistente/`:
- catálogo: filtro ou valor fora do catálogo é rejeitado;
- anonimizador: matrícula e nome da base viram marcador, e o marcador volta à matrícula;
- planejador: tabela de casos de aceitação, alimentada com `ConsultaEstruturada` fixas;
- compilador: números **iguais aos das telas**. Contagem por polo = agregação de `/alunos`; a série por semestre = `/crg-semestres`; `campos_sem_resposta` = `relatorio_do_lote`. Também: contagem distinta e `null` preservado;
- role: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` e `TRUNCATE` como `leitor_assistente` falham;
- visualização: uma asserção por linha da tabela de regras;
- API com `ProvedorFalso`: as quatro formas, `nao_entendi`, a nova tentativa, `503` e `/executar`.

**Avaliação da interpretação** (fora da suíte padrão, só com
`pytest -m avaliacao_llm` e `GROQ_API_KEY`):
`tests/assistente/perguntas_avaliacao.yaml` contém pergunta → consulta
esperada, e o teste reporta a taxa de acerto. Serve de métrica para a dissertação.

**vitest**:
- `filtrosUrl`: ida e volta;
- telas-alvo lendo filtros da URL;
- `IaChat` renderizando cada forma e navegando na forma `dashboard`;
- histórico: repetir, favoritar, limite de 100 e `localStorage` indisponível;
- link `?c=` reproduzindo a consulta.

## Critérios de pronto

- Os 11 casos de aceitação passam com o `ProvedorFalso`, e a taxa do conjunto de avaliação contra o Groq fica registrada.
- Nenhum payload enviado ao Groq contém matrícula, nome ou linha de resultado (teste que inspeciona a requisição).
- A suíte atual continua verde, e `docs/frontend_dashboards.md` e `API_README.md` ganham as rotas novas.

## Ajustes do plano (2026-09-25)

Decididos ao ler o código, antes de implementar (`docs/superpowers/plans/2026-09-25-assistente-consultas.md`):

- **Respostas do catálogo = `CAMPOS_SOCIOECONOMICOS`** (o que o FasiTech envia). Saem `escolaridade_pai`, `escolaridade_mae` e `computador_proprio`, que viriam nulos para 100% da base; entram `gasto_internet` e `tipo_deficiencia`.
- **Métrica `distribuicao` removida**: é `contagem_alunos` com uma dimensão. Entra `distribuicao_crg` (histograma do CRG, igual ao dashboard Distribuição).
- **Role com o mínimo**: `SELECT` só em `aluno_integrado` e `crg_semestre_vigente`. Os itens operacionais usam o serviço do relatório (código fixo, sem SQL derivado da pergunta).
- **`ProvedorLLM.completar(mensagens) -> str`**: o prompt fica em `intencao.py`, e o provedor só transporta.
- **`consulta_interpretada` é gerada da consulta executada**, não da paráfrase do LLM (que fica em `consulta.interpretacao`): mostra o que de fato rodou.
- **Visualização**: rosca só para categoria nominal (renda é ordinal → barras); duas dimensões com média → barras agrupadas; semestre + outra dimensão → uma linha por série.
- **Dashboards**: sai `dados` (nenhuma pergunta do catálogo cai nele); Alunos da turma recebe só `?periodo=`.
- **Gráficos dinâmicos** usam Recharts direto: os componentes de gráfico atuais leem `useDados()` e não recebem dados por props.
- **Período na URL**: `?periodo=` aplica o período ao abrir a tela; sem o parâmetro, vale o que está no seletor (e não "Todos"), então os links internos não precisam carregá-lo.
- **Testes** em `tests/test_assistente_*.py` (padrão plano do projeto); avaliação por `AVALIAR_LLM=1` com JSON (sem PyYAML).
