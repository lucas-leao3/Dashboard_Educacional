# Dashboards do frontend — navegação Polo → Turma → Aluno → Perfil

Implementação do documento `frontend/references/Alteracoes_Dashboard_Alinhamento_Reuniao.md`.
Quando as maquetes (`Reunião-2-Audio-*.png`) divergem do documento, vale o documento.

## Rotas

| Rota | Tela | Item do doc |
|---|---|---|
| `/` | Visão Geral dos Polos: KPIs + comparativo por indicador selecionável, n sempre visível | 3, 4, 8 |
| `/polo/:polo` | Turmas do polo: cards (alunos, CRG médio, sinalizações) + comparativo entre turmas | 5 |
| `/polo/:polo/turma/:turma` | Alunos da turma: KPIs, filtros, cards de perfil com as 4 dimensões, trajetórias | 5, 6, 7, 10 |
| `/analises/bidimensional` | CRG médio por categoria (cor/etnia, gênero, renda, trabalho, polo, turma), com o n de cada barra | 4, 8 |
| `/analises/distribuicao` | Histograma de CRG em faixas inteiras, com a média marcada | 4 |
| `/analises/longitudinal` | CRG médio por **semestre letivo**, uma linha por turma | 7 |

### As telas de Análises

As três liam arrays fixos no código até 2026-09-23 — valores que contradiziam a base (mostravam a categoria "Indígena", que não existe nela, e escondiam "Quilombola" e "Amarelo", que existem) e filtros que mudavam o estado sem filtrar nada. Hoje saem de `domain/analises.ts`, sobre os mesmos dados das outras telas.

Três regras que valem nelas:

- **O `n` é sempre visível.** Nesta base há categoria com um aluno só; sem o n, a barra dela parece tão sólida quanto a de quarenta.
- **Ausência de nota nunca vira zero.** No longitudinal, semestre sem apuração é lacuna na linha (`connectNulls={false}`).
- **A distribuição não traz curva ajustada.** A anterior era uma gaussiana decorativa; ajustar uma normal de verdade afirmaria uma distribuição que ninguém testou. No lugar vai a média, marcada sobre o eixo.

O eixo do longitudinal é o **semestre letivo**, não o período de coleta — ver a explicação em `API_README.md`, `GET /crg-semestres`.

### Como um aluno é identificado

Sempre **`Nome · matrícula`**, em toda tela, por `domain/aluno.ts`. Quem não tem nome aparece como **`— · matrícula`**.

O nome **não vem do FasiTech** (a API não devolve esse campo): ele é lido do histórico em PDF, no passo 2 do lote. Até 25/09/2026 só parte da base tinha PDF — 56 de 111 alunos —, e metade aparecia com nome e metade sem; desde a governança simplificada os dashboards só mostram integrados (todos com histórico), mas o marcador continua para PDF sem nome legível e para as tabelas de relatório. Antes cada tela resolvia isso sozinha com `nome ?? "Matrícula X"`, e a grade saía meio com nome e meio com número, parecendo defeito da interface quando era a cobertura dos PDFs aparecendo.

Duas decisões dentro disso:

- **A matrícula nunca some.** É o identificador estável (dela saem turma e polo, §4.8) e é por ela que se cruza acadêmico com socioeconômico. Só o nome faria dois homônimos virarem a mesma linha aos olhos de quem lê.
- **O nome é capitalizado na exibição.** O SIGAA entrega em CAIXA ALTA, que atrapalha a leitura de uma grade com dezenas de nomes; as partículas (`de`, `da`, `dos`, `e`) ficam em minúscula. A transformação é só de tela: o valor gravado em `usuarios` e o `vigente.csv` do lote continuam com o original, que é o que vale como registro.

**Em duas linhas, nome em cima e matrícula embaixo** (`components/ui/IdentificacaoAluno.tsx`). Numa linha só (`Nome · matrícula`) o `truncate` do card comia justamente a matrícula — "Andrey Azevedo do Carmo · 20…" —, que é o identificador estável e o que nunca deveria sumir. Empilhado, o nome pode truncar à vontade e os 12 dígitos cabem sempre. No Perfil o `<h1>` também trunca, então lá o nome fica no título e a matrícula abre o subtítulo.

As tabelas dos relatórios do lote (`/dados`) são a exceção deliberada: lá matrícula e nome já são colunas separadas, então não se repete a identificação — só o mesmo `—` quando falta.

### Busca do cabeçalho

Casa por **trecho** do nome ou da matrícula, sem caixa e sem acento (`domain/busca.ts`), e lista os resultados em vez de pular para um deles — um sobrenome comum casa com vários, e escolher o primeiro calado esconderia os outros. `Enter` vai para o primeiro, que é o mais relevante pela ordem: matrícula exata, depois quem começa com o termo, depois quem apenas o contém.

Antes era igualdade exata contra o nome cru. Como a tela passou a mostrar o nome capitalizado, copiar o que estava na tela e colar na busca não encontrava nada.
| `/aluno/:matricula` | Perfil individual: 4 dimensões detalhadas + trajetória por dimensão | 6, 7 |
| `/dados` | Importação (responsável + `.zip`; o lote termina fechado) + relatórios do lote: não integrados (com motivo) e integrados, ambos com campos sem resposta e % de preenchimento | `docs/governanca_simplificada.md` |
| `/analises/*` | Gráficos agregados do dashboard anterior (Bidimensional, Distribuição, Longitudinal) | — |
| `/ia-chat` | Assistente de consultas: pergunta em português → dashboard filtrado, gráfico dinâmico, tabela ou texto, com explicação e histórico local | `docs/superpowers/specs/2026-09-25-assistente-consultas-design.md` |

Filtros globais no cabeçalho: **Período** (item 9) e **busca por matrícula** (complementar, item 3).

### Filtros na URL

As telas que o assistente abre leem os filtros da query string: `?periodo=` (global, em qualquer tela), `/analises/bidimensional?dimensao=&polo=`, `/analises/distribuicao?polo=`, `/analises/longitudinal?polo=&turma=`. Mudar o filtro na tela atualiza a URL, então copiar o endereço compartilha a visão. Quando a tela foi aberta pelo assistente, o cabeçalho mostra a faixa "Aberto pelo assistente" com a consulta, os filtros e a fonte.

## Decisões

- **Turma = `primeiro_ano_eletivo`** (ano.semestre de ingresso). É o único campo do schema
  que agrupa coortes. Registro sem o campo cai em "Sem turma informada".
- **Dimensões** (item 2): Dados Acadêmicos, Socioeconômicos, Saúde Mental, Infraestrutura.
  "Trabalho & Renda" e "Frequência" das maquetes não existem mais.
- **Perfil do aluno = resultado das 4 dimensões** (item 10): a pior sinalização entre elas,
  acompanhada dos "fatores" que a puxaram. Não há arquétipo textual.
- **"Sem dado"** é hachurado cinza e significa "não coletado", nunca "bom".
- **n baixo**: grupo com menos de 15 alunos (`N_MINIMO`) recebe o aviso no comparativo.
- **Cores**: estado (verde/âmbar/vermelho) reservado para sinalização, sempre com texto ao lado;
  cor categórica só para polos (nominal) e rampa ordinal de um hue só para turmas (ano de
  ingresso: a ordem é o dado), sempre fixa por entidade, não por posição no ranking. Paletas validadas
  para daltonismo com o validador da skill `dataviz`.

## Critério provisório de sinalização (`frontend/src/domain/classificacao.ts`)

O documento deixa a regra matemática como etapa metodológica pendente. Tudo está em um
único módulo, com testes, para a troca ser cirúrgica.

| Dimensão | Índice | Atenção | Crítico | Sem dado |
|---|---|---|---|---|
| Acadêmica | CRG | 5 ≤ CRG < 7 | CRG < 5 | CRG nulo |
| Socioeconômica | renda ≤ 1 SM (+2), trabalho informal/autônomo (+1), renda ≤ 1 SM sem assistência (+1) | ≥ 1 | ≥ 4 | nenhum campo respondido |
| Saúde mental | muito ruim (+4), ruim (+2), regular (+1), estresse frequente (+2) | ≥ 1 | ≥ 4 | nenhum campo / "Prefiro não responder" |
| Infraestrutura | sem internet (+3), internet às vezes (+1), sem computador próprio (+1), 0 computadores (+1) | ≥ 1 | ≥ 3 | nenhum campo respondido |

Na trajetória longitudinal (item 7), a dimensão acadêmica plota o CRG; as demais plotam o
índice acima por período (maior = pior), o que permite ver oscilações sem depender do CRG.

## Dados

- `GET {VITE_API_URL}/alunos` (contrato `AlunoOut`). Em dev, o Vite faz proxy de `/api` para
  `localhost:8000`; em produção o nginx faz o mesmo (ver `frontend/Dockerfile`).
- Sem API (ou com erro), a UI cai no **dataset de demonstração** (`src/data/mockData.ts`),
  sintético e determinístico, com as distribuições do `DadosAgrupados.csv`. O cabeçalho
  mostra o selo "Dados de demonstração" nesse caso.
- A trajetória usa os registros por período do FasiTech. O CRG por semestre do SIGAA
  (`crg_semestre`) ainda não tem endpoint; quando houver, basta alimentar
  `trajetoriaPorDimensao('academica')` com essa série.
- A tela `/dados` é a única que **escreve** na API (`POST /lotes/importar`) e lê
  `GET /lotes/{id}/relatorio`. Sem API ela mostra só um aviso.
- `GET /alunos` e `GET /crg-semestres` só devolvem alunos **integrados** (acadêmico + socioeconômico): todo
  KPI, total e gráfico das telas Polos, Turmas, Alunos, Perfil e Análises conta só eles.
  Depois de uma importação, `recarregar()` do `DadosProvider` atualiza o dashboard inteiro.
  O relatório de um lote antigo é o retrato de quando ele fechou (base consolidada até a última ingestão
  dele) e coincide com os CSVs congelados no fechamento; o do lote mais recente coincide com o dashboard.

## Comandos

```bash
cd frontend
npm run dev      # http://localhost:5173
npm test         # vitest: domínio + smoke test das 4 telas
npm run build
```
