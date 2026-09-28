# Governança dos Dados

> **Atualização 25/09/2026 — governança simplificada.** A entrada de dados agora é
> uma importação só (`POST /lotes/importar`: responsável + `.zip`), com período
> extraído dos históricos, lote fechado automaticamente e imutável no banco, e
> dashboards só com alunos integrados. O fluxo de abrir/enviar/rodar/fechar descrito na §3 e na §5 foi substituído; os fundamentos (append-only, hashes, repositório de dados, views) continuam valendo. Ver `docs/governanca_simplificada.md`.

Como parar de perder dado no projeto e deixar rastreável de onde veio cada valor.

---

## 1. O problema

Hoje o projeto tem três problemas que fazem perder dado:

1. **Nada tem backup.** Os arquivos de origem existem em uma máquina só e estão no `.gitignore`. Os 56 PDFs do SIGAA são insubstituíveis.
2. **A escrita apaga o que estava lá.** O fluxo é uma rodada de três rotas em ordem fixa — `/sincronizar` → `/atualizar-crg` → `/preencher-legado` — e o banco guarda só o estado atual de cada aluno: cada rodada sobrescreve a anterior. Depois de rodar, não dá pra saber de onde veio cada valor nem desfazer.
3. **O que não casa é jogado fora.** Os contadores `ignorados` e `nao_encontrados` voltam na resposta da API e somem. São 47 alunos reais.

E um quarto, que não perde dado mas invalida a análise longitudinal:

4. **O CRG é achatado.** O `crg_historico.csv` tem um CRG por matrícula (o final, na data de emissão) e `/atualizar-crg` grava esse mesmo valor em todas as linhas do aluno. O PDF traz o CRG **por semestre letivo**, mas o passo 2 descarta. A curva de progresso do aluno sai reta.

Trocar SQLite por PostgreSQL **não resolve nenhum dos quatro**. São de modelagem e processo.

---

## 2. Situação medida (08/09/2026)

| | |
|---|---|
| Alunos únicos | 103 |
| Com acadêmico + socioeconômico | 56 |
| Só socioeconômico (falta histórico) | 47 |
| Só acadêmico | 0 |
| Taxa de integração | 54% |
| Volume de dados brutos | 2,0 MB |
| PDFs de histórico | 56, todos emitidos em 10/12/2025 |
| CRG por semestre extraível | 56 de 56 PDFs, de 2020.2 a 2025.1 |

Os 47 sem histórico não são um bug: existem 56 PDFs para 103 alunos. É lacuna de coleta. O que a governança precisa fazer é **registrar isso como estado conhecido**, não deixar sumir.

---

## 3. Regra dos arquivos físicos

> **O arquivo nunca é a verdade. O registro do arquivo no banco é.**

### 3.1. O lote é a unidade

As duas fontes têm cadência diferente:

| Fonte | Quando está disponível |
|---|---|
| Histórico SIGAA (PDF) | a qualquer momento |
| Socioeconômico (FasiTech) | fecha no fim do semestre |

Quem dita o ritmo é a mais lenta. Então a unidade de trabalho não é "um arquivo" nem "um semestre" — é o **lote**: uma rodada completa das rotas, disparada quando a coleta socioeconômica fecha. Os PDFs são puxados **no momento do lote**, não antes, para que o histórico e o socioeconômico do mesmo lote sejam contemporâneos.

Lote e período são eixos distintos e não se misturam:

- **Período** (`2025.2`) é *a que semestre o dado se refere*. É atributo da linha.
- **Lote** (`2026-09-L01`) é *quando a rodada foi executada e com quais insumos*. Um lote pode cobrir mais de um período — o inicial cobre dois; daí em diante, um por semestre.

Um lote tem dois insumos, um por rota:

| Passo | Rota | Insumo | Em quais lotes |
|---|---|---|---|
| 1 | `/sincronizar` | resposta da API FasiTech | todos |
| 2 | `/atualizar-crg` | PDFs do SIGAA | todos |

Não há mais um passo 3 de planilha legada: o L01 já nasce só com API + PDF (decisão tomada em `docs/superpowers/2026-09-12-primeiro-lote-design.md`). Campos que a planilha manual (`DadosAgrupados.csv`) preenchia e o FasiTech não traz ficam `NULL` — limitação declarada da fonte, não defeito do lote.

### 3.2. Onde colocar cada arquivo

Não classifique por assunto. Classifique por **regenerabilidade**, e dentro de `raw/` por lote:

```
data/
├── raw/                          imutável, só acrescenta
│   └── lotes/
│       ├── 2026-09-L01/          lote inicial — cobre 2 períodos, sem legado
│       │   ├── fasitech.json     resposta da API congelada, com envelope
│       │   ├── historicos/       56 PDFs, emitidos em 10/12/2025
│       │   ├── SHA256SUMS
│       │   └── lote.md
│       └── 2027-03-L02/          um por semestre daí em diante
│           ├── fasitech.json
│           ├── historicos/
│           ├── SHA256SUMS
│           └── lote.md
├── interim/                      dá pra regerar de raw/
│   └── crg_semestre.csv          extraído dos PDFs: matricula, semestre, crg
└── processed/                    dá pra regerar de raw/ + código
    └── <lote>/                   vigente.csv + correspondencia.csv, por lote
```

**Teste:** apague `interim/` e `processed/` inteiros. Se você conseguir regerar tudo a partir de `raw/` + código, está certo. Se não conseguir, aquele arquivo é `raw/` e está no lugar errado.

**`fasitech.json` é o insumo que hoje não existe.** A rota lê a API e grava direto no banco; a resposta some. Sem o arquivo congelado não há como provar o que a fonte respondeu naquela data — e o socioeconômico pode ser alterado retroativamente pelo aluno ou pela coordenação. O envelope guarda `url`, `params`, `coletado_em` e as páginas como vieram.

**`lote.md`** é o registro humano do lote: data, quem rodou, períodos cobertos, e os contadores devolvidos por cada rota. É o que se lê primeiro quando alguém pergunta "de onde veio esse número".

Aplicando ao que existe hoje — **os insumos atuais são o L01, montado retroativamente:**

| Arquivo | Onde vai | Por quê |
|---|---|---|
| `historicos/*.pdf` | `raw/lotes/2026-09-L01/historicos/` | fonte original, não se regenera |
| `fasitech.json` | `raw/lotes/2026-09-L01/` | nasce na primeira rodada de `/sincronizar` com congelamento |
| `crg_historico.csv` | aposentado → `interim/crg_semestre.csv` | extraído dos PDFs, agora por semestre |
| `DadosAgrupados.csv` e `relatorio_correspondencia*.csv` | **abandonados** — não entram no L01 | planilha manual e relatórios manuais de antes da API do FasiTech; sucedidos por `processed/<lote>/correspondencia.csv`, gerado por `scripts/lote.py fechar` |

Isso aposenta o `ONDE_COLOCAR.txt`: a pergunta "onde colocar" passa a ter resposta automática.

### 3.3. Integridade: `SHA256SUMS` por lote, não renomear

Cada lote tem um `SHA256SUMS` com o hash de todos os seus arquivos:

```bash
cd data/raw/lotes/2026-09-L01 && sha256sum historicos/*.pdf fasitech.json > SHA256SUMS
sha256sum -c SHA256SUMS      # verifica
```

Os arquivos mantêm o nome original — `historico_202016040011.pdf` já diz de quem é. Renomear para o hash ganharia dedup automático, mas perderia a legibilidade que a matrícula no nome dá, e dedup por lote é trivial: comparar `SHA256SUMS` de dois lotes mostra o que mudou entre eles. O hash de cada arquivo vai para o banco (`arquivo_fonte.sha256`), e é lá que a duplicata é detectada.

### 3.4. Backup: dois repositórios, não um

```
Dashboard_Educacional/      repositório de código (já existe)
├── backend/ frontend/ docs/
└── data/                   ignorado pelo git — onde os dados ficam em uso

dashboard-dados/            repositório NOVO, privado
└── raw/lotes/              só os 2 MB insubstituíveis
```

**Por que dois e não um:**

- O repo de código pode ser aberto, mostrado na dissertação, compartilhado. O de dados, não.
- Acesso diferente: quem lê o código não precisa ler dado de aluno.
- Ritmo diferente: o código muda toda semana, o `raw/` só quando chega lote novo.

**Como funciona na prática:**

1. Cria um repositório privado (GitHub, ou o GitLab da instituição).
2. Coloca só o `raw/lotes/` nele — 2 MB cabe com folga.
3. **Cada lote é um commit.** O histórico do git vira o registro de quando cada lote entrou; a mensagem do commit é o id do lote.
4. Na máquina de trabalho, clona ele dentro de `data/raw/`, que o repo de código já ignora.

**Decidido:** por ora, apenas o repositório privado separado, sem cifrar. Cifrar (`age` ou `.7z` com senha) fica como opção a revisitar se o comitê de ética exigir — o custo seria perder a comparação arquivo a arquivo do git e passar a versionar um blob opaco.

### 3.5. Anonimizar? Não no dashboard

**A matrícula fica visível.** Ela é padrão institucional de identificação e é a chave do cruzamento entre o CRG do histórico SIGAA e o socioeconômico do FasiTech. `anonymize_matricula=false` fica como está, e o dashboard mostra a matrícula normalmente.

Não existe tabela de pseudônimo no modelo. O controle correto aqui não é disfarçar o dado, é **controlar quem abre o dashboard** — que é uso interno e legítimo.

O cuidado se desloca para a fronteira onde o dado sai do ambiente controlado:

| Onde | Matrícula | Nome |
|---|---|---|
| Dashboard interno | visível | visível |
| Exportação de CSV para terceiros | mascarar | remover |
| Tabela ou figura na dissertação | mascarar | remover |
| Print de tela em artigo ou apresentação | mascarar | remover |

O que torna o dado sensível não é a matrícula em si — é a **ligação** entre ela e a declaração de saúde mental ou renda. Internamente, com acesso restrito, essa ligação é o objetivo da pesquisa. Publicada, é reidentificação.

Regra prática: qualquer coisa que saia do ambiente controlado passa por uma função de mascaramento (ex.: `2020160400**`). Isso é um passo de exportação, não uma camada da arquitetura.

**A API não tem autenticação — e os históricos entram por ela.** `POST /lotes/{id}/historicos` recebe os PDFs do SIGAA (nome, matrícula, notas) e grava em `raw/lotes/<id>/historicos/`. A fronteira de acesso hoje é a rede: o compose só publica a porta 8000 no `localhost` da máquina que roda o lote, e o banco nem isso. Enquanto for assim, "controlar quem abre o dashboard" e "controlar quem alcança a porta 8000" são a mesma coisa. Publicar a API fora do `localhost` (outra máquina, servidor da faculdade) exige autenticação antes — vira decisão registrada na seção 9, não ajuste de compose.

---

## 4. Modelo de dados

Cinco tabelas novas. `usuarios` muda de comportamento. O resto continua.

> O schema é versionado com Alembic desde 22/09/2026: cada mudança de tabela
> ou coluna vira uma revisão em `backend/migrations/versions/`, commitada junto
> com o código. Como alterar o schema e como conferir se banco e modelo estão
> de acordo: **`docs/migracoes.md`**.

```
lote ──< ingestao ──< usuarios          (1 lote, 3 ingestões, N linhas)
  │         │
  │         ├──< excecao
  │         └──< crg_semestre
  └──< arquivo_fonte
```

### 4.1. `lote` — a rodada

```sql
CREATE TABLE lote (
    id                TEXT PRIMARY KEY,      -- 2026-09-L01
    executado_em      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    periodos_cobertos TEXT NOT NULL,         -- '2025.2;2026.1'
    executado_por     TEXT,
    observacao        TEXT,
    fechado_em        TIMESTAMP              -- NULL = aberto
);
```

É o espelho de `raw/lotes/<id>/` no banco. `periodos_cobertos` é descritivo — o período de cada dado está na linha dele. `fechado_em` é o estado do lote: `NULL` enquanto recebe insumo; preenchido por `POST /lotes/{id}/fechar`, que também escreve `SHA256SUMS` e `lote.md` (3.3). Fechado não se reabre e não recebe mais histórico — a interface lê daqui, não da existência de `lote.md` em disco.

### 4.2. `arquivo_fonte` — de onde veio

```sql
CREATE TABLE arquivo_fonte (
    sha256         TEXT PRIMARY KEY,
    lote_id        TEXT NOT NULL REFERENCES lote(id),
    nome_original  TEXT NOT NULL,
    tipo           TEXT NOT NULL,   -- pdf_historico | csv_legado | api_fasitech
    tamanho_bytes  INTEGER NOT NULL
);
```

O `sha256` como chave primária é o que detecta duplicata: o mesmo PDF em dois lotes falha na inserção, e o lote registra "já entrou no L01".

### 4.3. `ingestao` — um passo do lote

```sql
CREATE TABLE ingestao (
    id                   SERIAL PRIMARY KEY,
    lote_id              TEXT NOT NULL REFERENCES lote(id),
    passo                SMALLINT NOT NULL,   -- 1 sincronizar | 2 atualizar-crg
    arquivo_sha256       TEXT REFERENCES arquivo_fonte(sha256),
    executado_em         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    registros_lidos      INTEGER NOT NULL,
    registros_aceitos    INTEGER NOT NULL,
    registros_rejeitados INTEGER NOT NULL,
    UNIQUE (lote_id, passo)
);
```

Uma ingestão por rota por lote. **Não tem coluna `periodo`**: um lote cobre mais de um período, então amarrar a ingestão a um só quebraria já no L01. Toda escrita passa a referenciar um `ingestao_id`. É isso que transforma "rodei o endpoint" em fato rastreável.

### 4.4. `excecao` — o que não casou

```sql
CREATE TABLE excecao (
    id           SERIAL PRIMARY KEY,
    ingestao_id  INTEGER NOT NULL REFERENCES ingestao(id),
    matricula    BIGINT,
    periodo      TEXT,
    motivo       TEXT NOT NULL,   -- sem_academico | sem_socioeconomico | matricula_invalida | duplicado
    detalhe      TEXT
);
```

Substitui os contadores que hoje somem. Os 47 alunos passam a existir como registro.

### 4.5. Parar de sobrescrever

A tabela `usuarios` ganha `ingestao_id` e vira **append-only**: cada ingestão grava uma linha nova para `(matricula, periodo)`, em vez de alterar a que existe.

```sql
ALTER TABLE usuarios ADD COLUMN ingestao_id INTEGER REFERENCES ingestao(id);
CREATE UNIQUE INDEX ux_usuarios ON usuarios (matricula, periodo, ingestao_id);
```

O valor atual sai de uma view que resolve pela ingestão mais recente:

```sql
CREATE VIEW aluno_vigente AS
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY matricula, periodo ORDER BY ingestao_id DESC
    ) AS rn
    FROM usuarios
) AS ranked WHERE rn = 1;
```

Assim a regra que hoje é comentário no código — *"CRG só vem do histórico oficial, nunca do CSV legado"* — vira dado, não convenção.

**A view não é a única forma de ler.** A tabela `usuarios` continua com tudo dentro. Para ver histórico, comparar versões ou auditar uma importação, consulte a tabela direto filtrando por `ingestao_id`. A view é só o atalho para "o valor de agora".

> **Tradeoff:** guardar snapshot inteiro por importação gasta mais espaço que guardar só o campo que mudou. Com 103 alunos isso é irrelevante, e é muito mais simples de implementar e explicar.

### 4.6. `crg_semestre` — o progresso do aluno

O PDF do SIGAA traz um bloco "Coeficiente de Rendimento por Semestre Letivo", no formato `2024/Sem1: 7.14`. É esse bloco que dá o eixo longitudinal, não o CRG final.

```sql
CREATE TABLE crg_semestre (
    matricula    BIGINT  NOT NULL,
    semestre     TEXT    NOT NULL,           -- '2024.1'
    crg          NUMERIC(5,2),               -- NULL = semestre não apurado
    ingestao_id  INTEGER NOT NULL REFERENCES ingestao(id),
    PRIMARY KEY (matricula, semestre, ingestao_id)
);
```

**Validado nos 56 PDFs:** o bloco extrai de todos, cobrindo 2020.2 a 2026.1, 12 semestres.

**Regra do zero.** Nos 56 PDFs, 2025.2 e 2026.1 aparecem como `0.00` em 100% dos casos — a emissão foi em 10/12/2025, com o semestre em curso. Ali zero é *"ainda não apurado"*, não nota. Já entre 2021.1 e 2024.1 há um zero isolado por semestre, que é nota real (trancamento ou reprovação total). A regra, portanto:

> Semestre igual ou posterior ao da data de emissão do PDF → `crg = NULL`. Anterior → o valor que está lá, zero incluso.

A data de emissão está no rodapé de cada página (`Emitido em: 10/12/2025`) e é lida do próprio PDF, não digitada.

`usuarios.CRG` passa a ser só o vigente — o último semestre apurado — e é derivado desta tabela, não gravado por fora.

### 4.7. Três leituras, um conjunto de tabelas

| Você quer | Lê |
|---|---|
| **Progresso do aluno** por semestre | `crg_semestre` ⋈ `usuarios` por `(matricula, semestre = periodo)`, filtrando a ingestão vigente |
| **Corte transversal** (como está a turma agora) | `aluno_vigente` |
| **Histórico de versões** / auditoria | `usuarios` e `crg_semestre` filtrando `ingestao_id`, `lote.periodos_cobertos` para contexto |

O cruzamento acadêmico × socioeconômico que o dashboard mostra é o da primeira linha. O semestre vem do histórico; o socioeconômico se pendura nele pela matrícula e pelo período em que a coleta fechou.

> **Sintaxe:** o DDL é PostgreSQL, e é o único banco do projeto — em produção, em desenvolvimento e na suíte de testes, sempre `postgres:17-alpine`. A tabela de equivalências para SQLite que ficava aqui saiu junto com o SQLite (ver `docs/migracoes.md`).

### 4.8. Turma e polo saem da matrícula

A matrícula tem 12 dígitos com estrutura fixa, e isso dispensa coletar ou padronizar dois campos:

```
2020 1604 0002
│    │    └── sequencial do aluno
│    └─────── polo
└──────────── turma (ano de ingresso)
```

| Dígitos 5–8 | Polo |
|---|---|
| `1604` | Cametá |
| `8564` | Limoeiro |
| `8594` | Oeiras |

**Validado contra os dados reais:** as 103 matrículas têm exatamente 12 dígitos. As 7 turmas resultantes distribuem-se em 2020 (5), 2021 (7), 2022 (25), 2023 (7), 2024 (21), 2025 (23) e 2026 (15). O mapeamento de polo bate em 120 de 120 linhas, sem uma exceção.

**Consequência 1 — polo deixa de ser texto livre.** Hoje é string sem padronização, filtrada contra uma lista fixa no código, e uma grafia divergente ("Cametá" acentuado) some silenciosamente das análises. Derivando da matrícula, o problema desaparece.

**Consequência 2 — `primeiro_ano_eletivo` é redundante e pior.** Conferido contra os 4 primeiros dígitos: 82 registros confirmam, **0 divergem**, e 38 estão em branco. Derivar acerta onde a coluna acerta e ainda preenche os 38 vazios.

Em PostgreSQL, colunas geradas resolvem sem código de aplicação:

```sql
ALTER TABLE usuarios
  ADD COLUMN turma TEXT GENERATED ALWAYS AS (LEFT(matricula::TEXT, 4)) STORED,
  ADD COLUMN polo_cod TEXT GENERATED ALWAYS AS (SUBSTRING(matricula::TEXT, 5, 4)) STORED;

CREATE TABLE polo (
    codigo TEXT PRIMARY KEY,   -- 1604, 8564, 8594
    nome   TEXT NOT NULL       -- Cametá, Limoeiro, Oeiras
);
```

> **Guarde a regra como regra.** A estrutura da matrícula é uma convenção institucional, não uma lei da natureza. Por isso a derivação fica em um lugar só (coluna gerada ou uma função), documentada aqui, e não espalhada por consultas do dashboard. Matrícula fora do padrão de 12 dígitos vira `excecao` com motivo `matricula_invalida`, em vez de gerar turma errada silenciosamente.

**Confirmado contra a API em 2026-09-23, e não era mais opcional.** Consulta aos 187 registros de `dados-sociais/raw`: o campo `polo` volta **nulo em 187 de 187** e o campo `primeiro_ano_eletivo` **não existe no payload** (a resposta traz 16 chaves, e nenhuma delas é essa). Ou seja, os dois campos que o dashboard mostrava como "Sem polo informado"/"Sem turma informada" não estavam sendo perdidos no caminho — a fonte nunca os enviou. A matrícula é a única origem possível dos dois. Os 187 registros usam exatamente os três códigos da tabela acima (`1604`: 123, `8594`: 46, `8564`: 18) e têm 100% de 12 dígitos, então a derivação cobre a base inteira sem exceção.

**Onde a derivação mora: no banco.** A view `aluno_vigente` ganhou três colunas — `turma`, `polo_cod` e `polo_nome` — e uma tabela `polo` (`codigo` → `nome`) resolve o nome por `LEFT JOIN`. Assim o dashboard, o `vigente.csv` e quem consultar por SQL leem o mesmo valor, sem cada um refazer a conta. Polo novo passa a ser `INSERT INTO polo`, não deploy. Revisão `a3f1c2d40b7e`.

**Por que view e não coluna gerada**, apesar do DDL acima. Dois motivos, nenhum deles de portabilidade — o projeto roda só em PostgreSQL:

1. **A coluna gerada não dispensa a view.** Ela resolveria `turma` e `polo_cod`, que são recortes da matrícula, mas `polo_nome` sai de um `LEFT JOIN` com a tabela `polo` — e coluna gerada não pode consultar outra tabela. Seria a derivação em dois lugares para entregar um valor só.
2. **`usuarios` é tabela de auditoria.** Ela é append-only e existe para registrar *o que a fonte mandou*. Valor calculado pertence ao modelo de leitura (a view), não ao registro bruto. Com a derivação na view, reinterpretar a regra amanhã é uma revisão que troca a view, sem tocar em uma linha de dado histórico.

A expressão protege o caso que esta seção exige: `CASE WHEN length(CAST(matricula AS TEXT)) = 12` devolve `NULL` para matrícula fora do padrão, em vez de fatiar lixo e inventar uma turma.

**No frontend**, `frontend/src/domain/matricula.ts` guarda a mesma regra como *reserva*: ela só entra quando não há API (o dataset de demonstração) ou quando o código do polo ainda não está na tabela — aí o código cru aparece como `Polo <código>`, em vez de o polo sumir da tela. A escolha entre o valor do banco e o derivado local é feita num lugar só, `consolidarAlunos` em `domain/agregacao.ts`, de onde todas as telas herdam.

**Verificado em PostgreSQL 17** (o mesmo `postgres:17-alpine` do compose e da suíte), com `upgrade`, `downgrade` e reaplicação, e com as 187 matrículas reais da API atravessando `POST /alunos` → banco → `GET /alunos`: 178 de 178 linhas voltam com turma e polo preenchidos.

---

## 5. Fluxo: rodar um lote

A regra que faz o desenho todo funcionar: **importar nunca apaga nada**. Rodar duas vezes é seguro.

```
coleta socioeconômica fecha (fim do semestre)
    │
    ▼
cria raw/lotes/<id>/  ─────────────>  lote
    │
    ├─ passo 1  /sincronizar
    │     congela fasitech.json ──>  arquivo_fonte
    │     abre ingestao (passo 1)
    │     linha NOVA em usuarios por (matricula, periodo)
    │     rejeitados ──────────────>  excecao
    │     fecha ingestao com contadores
    │
    └─ passo 2  /atualizar-crg
          puxa PDFs do SIGAA → historicos/  ──>  arquivo_fonte (1 por PDF)
          abre ingestao (passo 2)
          extrai CRG por semestre ──>  crg_semestre (regra do zero aplicada)
          nome, nascimento → usuarios (linha nova)
          matrícula sem PDF ─────────>  excecao (sem_academico)
          fecha ingestao
    │
    ▼
SHA256SUMS + lote.md + commit no repo privado
    │
    ▼
aluno_vigente e crg_semestre já refletem o lote
```

### Passo a passo

1. **Coleta fecha.** A coordenação sinaliza que o socioeconômico do semestre está completo no FasiTech.
2. **Cria o lote.** Pasta `raw/lotes/<AAAA-MM>-L<nn>/` e linha em `lote` com os períodos cobertos.
3. **Passo 1.** `/sincronizar` congela a resposta da API em `fasitech.json` **antes** de tocar o banco, registra o arquivo, abre a ingestão e insere uma linha nova por `(matricula, periodo)` — mesmo que já exista uma de lote anterior.
4. **Passo 2.** Puxa os PDFs do SIGAA para `historicos/`. `/atualizar-crg` registra cada PDF, extrai o bloco de CRG por semestre, aplica a regra do zero e grava em `crg_semestre`. Matrícula do FasiTech sem PDF vira `excecao`.
5. **Fecha o lote.** `SHA256SUMS`, `lote.md` com os contadores das rotas, commit no repositório privado. Campos que o levantamento manual (`DadosAgrupados.csv`) preenchia e a API do FasiTech não traz ficam `NULL` — limitação declarada da fonte, não defeito do lote (ver `docs/operacao_lote.md`).
6. **Pronto.** `aluno_vigente` mostra os valores novos; o lote anterior continua intacto e comparável.

### Os três casos

| Situação | O que acontece |
|---|---|
| **Semestre novo** (L02) | Lote novo, dois passos. Linhas novas com o período novo em `usuarios`; `crg_semestre` ganha um semestre apurado a mais por aluno (o que era `NULL` no L01 vira nota). Nada antigo é tocado. |
| **Correção na fonte** (o CRG estava errado, o aluno corrigiu a renda) | Aparece naturalmente no lote seguinte como linha nova para o mesmo `(matricula, periodo)`. A view mostra o valor corrigido; o antigo fica gravado como evidência do que a fonte dizia. Diff entre lotes é a ferramenta de auditoria. |
| **Mesmo PDF de novo** | `arquivo_fonte.sha256` já existe → o arquivo é registrado como repetido e não gera linha nova. |

### O que muda nos endpoints atuais

| Rota | Hoje | No fluxo novo |
|---|---|---|
| `/sincronizar` | lê a API e grava direto; **pula** se `(matricula, periodo)` já existe — por isso correção nunca chega | congela `fasitech.json` primeiro; sempre insere snapshot novo com `ingestao_id`; a view decide o vigente |
| `/atualizar-crg` | lê `crg_historico.csv` (1 CRG por matrícula) e grava o mesmo valor em **todas** as linhas do aluno | lê os PDFs do lote, extrai CRG **por semestre** para `crg_semestre`; `usuarios.CRG` vira derivado |
| `/preencher-legado` | roda sempre, preenche vazios in place | **removido.** O L01 passa a ser só API + PDF; manter a rota viva era convite pra rodar por engano num lote |
| `POST /lotes/{id}/historicos` | não existia — PDFs copiados à mão para a pasta | **nova.** Recebe `.pdf` ou `.zip` e grava em `historicos/`; reenvio idempotente por conteúdo, nome repetido com conteúdo diferente é `409`, e recusa depois que o passo 2 leu a pasta ou o lote fechou. Com `?executar=true` roda os passos 1 e 2 em seguida (pulando o já feito) — o lote inteiro cabe no Swagger. `scripts/lote.py executar` faz o mesmo pelo terminal |
| `POST /lotes/{id}/fechar` | era `scripts/lote.py fechar`, rodando no host | **nova.** A geração de `SHA256SUMS`, `lote.md` e dos CSVs derivados passa para a API, que também grava `lote.fechado_em`. Fechar continua uma chamada **separada** do upload, de propósito: entre os dois há a conferência dos contadores e das exceções, e fechado não se reabre. Uma interface futura vira um botão por transição (abrir → enviar+rodar → fechar) |

A inversão em `/sincronizar` (inserir sempre, resolver na view) conserta o problema 2. A mudança em `/atualizar-crg` conserta o problema 4.

---

## 6. PostgreSQL: vale a pena?

**Sim, mas junto com a mudança do modelo acima — não antes.**

Por que não é o primeiro passo: migrando hoje, você fica com os mesmos problemas, só que em PostgreSQL. Para 103 alunos e 2 MB, o argumento de escala não existe.

Por que ainda assim vale:

- **`JSONB`** para guardar o payload cru do FasiTech como chegou, espelhando o `fasitech.json` do lote. Permite *provar* o que a fonte respondeu, não só o que você extraiu.
- **Roles e row-level security.** Dado pessoal sensível precisa de controle de acesso. Com o PostgreSQL já em uso, isso deixou de ser argumento de migração e virou trabalho a fazer: nenhuma role além do dono foi criada até aqui.

Por que junto: **o schema vai ser reescrito de qualquer jeito** (seção 4). Fazer a reescrita já em PostgreSQL evita fazer duas vezes. Migrar 2 MB no final leva minutos.

---

## 7. Ordem de execução

| # | Passo | Resolve | Código? | Status |
|---|---|---|---|---|
| 1 | Montar o L01 retroativo: mover PDFs para `raw/lotes/2026-09-L01/`, gerar `SHA256SUMS` e `lote.md` | problema 1, onde colocar | não | ver roteiro |
| 2 | Colocar `raw/lotes/` em repositório privado separado, commit "L01" | problema 1 | não | ver roteiro |
| 3 | Criar `lote`, `arquivo_fonte`, `ingestao`, `excecao`; `usuarios` append-only + view | problemas 2 e 3 | sim | **feito** |
| 4 | Criar `crg_semestre`; reescrever a extração dos PDFs para semestre + regra do zero; `/atualizar-crg` passa a gravar nela | problema 4 | sim | **feito** |
| 5 | `/sincronizar` congela `fasitech.json` e insere sempre — o `fasitech.json` do L01 nasce aqui | problema 2 | sim | **feito** |
| 6 | Migrar para PostgreSQL e subir backend + banco com `docker compose` (junto dos passos 3–5) | JSONB, acesso | sim | **feito** |
| 7 | Derivar turma e polo da matrícula | análise por turma e polo | sim | **feito** — na view `aluno_vigente` + tabela `polo` (revisão `a3f1c2d40b7e`), com reserva no frontend |
| 8 | Rótulos por regra documentada | perfis | sim | fora do escopo do L01 |

Os passos 3 a 6 estão prontos: `POST /lotes`, `/alunos/sincronizar`, `/alunos/atualizar-crg`, a view `aluno_vigente` e o compose com PostgreSQL. O que falta é **rodar** o L01 de ponta a ponta e ligar o dashboard à API — roteiro completo em `docs/operacao_lote.md`, com `scripts/lote.py` fazendo `abrir`/`rodar`/`fechar`.

---

## 8. Rotulação

Regra explícita primeiro, modelo depois. Um rótulo por regra é auditável: dá pra mostrar o critério, contestar e reproduzir. Um rótulo de modelo sem linha de base por regra não é nem uma coisa nem outra — e é a primeira pergunta que a banca faz.

Ordem: regra documentada → conjunto rotulado e validado → modelo estatístico medido **contra** a regra.

O critério de cada rótulo é gravado como dado, versionado junto do registro que ele classificou — e, agora, junto do `lote_id` que o produziu.

---

## 9. Decisões pendentes

- **Os 47 históricos faltantes são recuperáveis no SIGAA?** Como o histórico sai a qualquer hora, a resposta provável é sim — e o lugar de puxá-los é o passo 2 do L02. Se não, vira limitação declarada da pesquisa.
- **Como o período do FasiTech se traduz em semestre?** O eixo semestral vem do PDF. O socioeconômico entra com o período em que a coleta fechou — precisa ficar escrito no `lote.md` de cada lote qual semestre a coleta representa. O legado (`2024.(1 e 2)`, `2025.(3 e 4)`) fica com a onda como está; é dado do L01 e não se reinterpreta.
- **Há aprovação de comitê de ética?** Determina o que pode ser publicado e se o mascaramento na exportação (seção 3.5) precisa ir além do que está proposto.
- **Onde o repositório privado vai ficar?** GitHub, GitLab da instituição, ou outro. Depende da política da UFPA para dado de pesquisa com sujeitos humanos.
- **A API vai sair do `localhost`?** Hoje não tem autenticação e recebe PDF com dado pessoal (3.5). Se um dia rodar em servidor compartilhado, autenticação vem antes da publicação.

**Decidido em 18/09/2026:** históricos entram pela API (`POST /lotes/{id}/historicos`), não por cópia manual · fechamento vira endpoint com `fechado_em` no banco · fechar **não** é automático depois do upload — a conferência humana entre rodar e selar fica como ponto de revisão (5).

**Decidido nesta revisão:** lote como unidade de governança, com `ingestao` por passo e sem período fixo (3.1, 4.3) · `SHA256SUMS` por lote em vez de renomear arquivo (3.3) · resposta do FasiTech congelada em arquivo antes de gravar (3.2, 5) · CRG por semestre em tabela própria, com regra do zero (4.6) · passo 3 (legado) planejado como exclusivo do L01 e depois **abandonado** antes do L01 rodar — API + PDF bastam (3.1; decisão revista em `docs/superpowers/2026-09-12-primeiro-lote-design.md`) · matrícula visível no dashboard, sem pseudonimização interna (3.5) · repositório privado separado, sem cifrar por ora (3.4) · turma e polo derivados da matrícula (4.8).
