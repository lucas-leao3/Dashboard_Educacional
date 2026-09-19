# Dashboards do frontend — navegação Polo → Turma → Aluno → Perfil

Implementação do documento `frontend/references/Alteracoes_Dashboard_Alinhamento_Reuniao.md`.
Quando as maquetes (`Reunião-2-Audio-*.png`) divergem do documento, vale o documento.

## Rotas

| Rota | Tela | Item do doc |
|---|---|---|
| `/` | Visão Geral dos Polos: KPIs + comparativo por indicador selecionável, n sempre visível | 3, 4, 8 |
| `/polo/:polo` | Turmas do polo: cards (alunos, CRG médio, sinalizações) + comparativo entre turmas | 5 |
| `/polo/:polo/turma/:turma` | Alunos da turma: KPIs, filtros, cards de perfil com as 4 dimensões, trajetórias | 5, 6, 7, 10 |
| `/aluno/:matricula` | Perfil individual: 4 dimensões detalhadas + trajetória por dimensão | 6, 7 |
| `/dados` | Inserção de lote (abrir → enviar PDFs e rodar → conferir e fechar) + cobertura do lote (correspondência por matrícula) | spec `2026-09-18-tela-dados-lote-design.md` |
| `/analises/*` | Gráficos agregados do dashboard anterior (Bidimensional, Distribuição, Longitudinal) | — |

Filtros globais no cabeçalho: **Período** (item 9) e **busca por matrícula** (complementar, item 3).

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
  cor categórica só para polos, fixa por nome (não por posição no ranking). Paletas validadas
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
- A tela `/dados` é a única que **escreve** na API (`POST /lotes`, `POST /lotes/{id}/historicos?executar=true`,
  `POST /lotes/{id}/fechar`) e lê `GET /lotes/{id}/correspondencia`. Sem API ela mostra só um aviso.
  Depois de cada ação, `recarregar()` do `DadosProvider` atualiza o dashboard inteiro.
  Para um lote fechado que não é mais o vigente (já existe um lote mais recente), a cobertura mostrada pode não coincidir mais com o `correspondencia.csv` congelado no fechamento — `GET /lotes/{id}/correspondencia` sempre lê o estado vigente atual, não um retrato histórico do lote consultado.

## Comandos

```bash
cd frontend
npm run dev      # http://localhost:5173
npm test         # vitest: domínio + smoke test das 4 telas
npm run build
```
