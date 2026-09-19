# Operação de um lote

Roteiro de ponta a ponta para abrir, rodar e fechar um lote com
`scripts/lote.py`. Pressupõe a governança por lote já implementada no backend
(`docs/governanca_dados.md`) — este documento é só o "como fazer", passo a
passo, sem repetir o "por quê" (que está lá).

## Pré-requisitos

1. **Credenciais do FasiTech.** Copie `backend/.env.example` para
   `backend/.env` e preencha `FASITECH_URL` e `FASITECH_TOKEN`. Troque
   também `POSTGRES_PASSWORD`. Esse arquivo nunca vai pro git.
2. **Docker Compose no ar:**
   ```bash
   docker compose up -d --build
   ```
   Sobe `db` (PostgreSQL, sem porta publicada), `backend` em
   `http://localhost:8000` e `frontend` em `http://localhost:8080`. `./data`
   é montado como `/data` no container `backend` — é a mesma pasta que
   `scripts/lote.py --dados ./data` (padrão) usa no host.
3. **Python no host** com `httpx` instalado (já é dependência do projeto —
   `pip install -e .` ou a `venvDashboard` de sempre). O script roda fora do
   container, só fala com a API por HTTP.

## Pelo Swagger (sem terminal)

A tela **Dados** do dashboard (`http://localhost:8080/dados`) faz estas mesmas três chamadas por botões — é o caminho recomendado para quem não quer abrir o Swagger.

Abra `http://localhost:8000/docs`. O lote inteiro são três chamadas:

1. `POST /lotes` — corpo `{"id": "2026-09-L01", "periodos_cobertos": ["2025.2", "2026.1"], "executado_por": "Edinaldo"}`.
2. `POST /lotes/{lote_id}/historicos` — `lote_id` = `2026-09-L01`, `executar` = `true`, e em `arquivos` selecione o `.zip` (ou os PDFs, um por "Add item"). A resposta traz o que foi gravado e os contadores dos passos 1 e 2.
3. Confira (`GET /lotes/{lote_id}`, `GET /lotes/{lote_id}/excecoes`, o dashboard) e então `POST /lotes/{lote_id}/fechar`.

O que segue é o mesmo fluxo pelo terminal.

## Caminho curto: `executar`

Os passos 1 a 3 abaixo (abrir, enviar os PDFs, rodar) são um comando só:

```bash
python scripts/lote.py executar 2026-09-L01 \
  --periodos 2025.2 2026.1 --por "Edinaldo" \
  --historicos /caminho/para/os/historicos/
```

`--historicos` aceita uma pasta (manda todos os `*.pdf` dela), um `.zip`,
PDFs soltos, ou vários desses. Os 56 PDFs originais deste projeto estão em
`backend/app/data/historicos/`.

`fechar` fica de fora de propósito: antes dele vem a conferência do
dashboard e do `fasitech.json` (passos 4 e 5).

**Seguro de repetir.** Se algo falhar no meio (FasiTech fora do ar, PDF
ilegível que você quer trocar antes de rodar o passo 2), corrija e chame
`executar` de novo com os mesmos argumentos: lote já aberto segue, PDF já
enviado é idempotente, passo já executado é pulado.

## Passo a passo (o que `executar` faz, um comando de cada vez)

Os exemplos abaixo usam o id `2026-09-L01`. Troque pelo id real do lote.

### 1. Abrir o lote

```bash
python scripts/lote.py abrir 2026-09-L01 --periodos 2025.2 2026.1 --por "Edinaldo"
```

Cria a linha em `lote` e a pasta `data/raw/lotes/2026-09-L01/historicos/`,
impressa no terminal. Falha com `409` se o id já existir — lote não se abre
duas vezes. **Não crie a pasta à mão antes**: a API cria pasta e registro
juntos e recusa se a pasta já existir.

Os períodos cobertos declarados aqui são o que se espera encontrar; o que
importa de verdade é o que a resposta do FasiTech trouxer. Confira em
`fasitech.json` (gerado no passo seguinte) antes de fechar o lote — se
divergir do que foi informado aqui, registre no `--obs` do `fechar` (ou,
por ora, edite a observação diretamente no banco).

### 2. Enviar os PDFs

```bash
python scripts/lote.py enviar 2026-09-L01 /caminho/para/os/historicos/
# ou
python scripts/lote.py enviar 2026-09-L01 historicos.zip
```

Manda os arquivos para `POST /lotes/2026-09-L01/historicos`, que os grava
em `data/raw/lotes/2026-09-L01/historicos/`. De um `.zip` só saem os
`.pdf` (subpastas achatadas; `__MACOSX/`, `Thumbs.db` e afins aparecem como
`ignorado:` na saída). `.rar` não é aceito — converta para zip.

Reenviar o mesmo PDF não duplica nem sobrescreve. PDF com o mesmo nome e
conteúdo diferente dá `409` e nada é gravado: se precisa trocar um insumo,
é outro lote. Depois que o passo 2 rodou, a rota recusa (`409`) — insumo
não muda depois de lido.

Se a API roda na mesma máquina, copiar direto para a pasta continua
funcionando (é a mesma `./data` montada no container); `enviar` é o caminho
que também funciona com a API em outra máquina.

### 3. Rodar

```bash
python scripts/lote.py rodar 2026-09-L01
```

Consulta `GET /lotes/2026-09-L01` e executa o que falta, em ordem:
`POST /alunos/sincronizar?lote=2026-09-L01` (passo 1: busca o FasiTech,
congela `fasitech.json`) e `POST /alunos/atualizar-crg?lote=2026-09-L01`
(passo 2: lê os PDFs, grava CRG por semestre). Imprime os contadores de
cada passo. Se o passo 1 falhar (ex.: FasiTech fora do ar), o passo 2 não
roda — corrija a causa e rode `rodar` de novo: o passo já executado é
pulado, o pendente roda.

### 4. Conferir o dashboard

Abra `http://localhost:8080`. Deve aparecer o selo do lote (id, data,
contagem de exceções) e os alunos vigentes. Se aparecer "Dados de
demonstração" em vez do selo, o frontend não conseguiu falar com a API —
confira `docker compose logs backend` e `docker compose logs frontend`.

### 5. Fechar

```bash
python scripts/lote.py fechar 2026-09-L01
```

Chama `POST /lotes/2026-09-L01/fechar`. A API confere que os passos 1 e 2
rodaram (recusa se não), gera em `data/raw/lotes/2026-09-L01/`:

- `SHA256SUMS` — hash de todos os insumos do lote, verificável com
  `sha256sum -c SHA256SUMS`.
- `lote.md` — registro humano: id, períodos, quem rodou, contadores de cada
  ingestão, exceções por motivo, lista de arquivos com hash, e a seção
  "Limitações" (campos que a planilha manual preenchia e o FasiTech não
  traz ficam `NULL` neste lote — declarado, não é defeito).

E em `data/processed/2026-09-L01/` (derivado, não entra no repositório de
dados — regenerável a partir do banco e do `raw/`):

- `vigente.csv` — corte transversal de `GET /alunos`, uma linha por
  `(matricula, periodo)`.
- `correspondencia.csv` — uma linha por matrícula: `Matricula, Nome,
  Academico, SocioEconomico, Dado_Faltando`. Sucede os
  `relatorio_correspondencia*.csv` manuais de antes da governança por lote.

Por fim grava `lote.fechado_em`. **Lote fechado não se reabre** nem recebe
mais históricos: `fechar` e `enviar` recusam com `409`. Os caminhos que o
script imprime são os vistos pela API (dentro do container, `/data/...`);
no host correspondem a `./data/...`.

### 6. Commit no repositório privado de dados

`data/raw/` não vai para este repositório (está no `.gitignore`) — vai para
o repositório privado `dashboard-dados` (`docs/governanca_dados.md`, seção
3.4).

```bash
cd data/raw/lotes/2026-09-L01
git -C /caminho/para/dashboard-dados add raw/lotes/2026-09-L01
git -C /caminho/para/dashboard-dados commit -m "2026-09-L01"
```

(Ajuste os caminhos ao clone real do `dashboard-dados` na sua máquina.)

## O que muda no L02

- **PDFs novos do SIGAA**, incluindo os que faltaram no L01 (os alunos que
  hoje caem em `sem_academico`) — o histórico sai a qualquer momento, então
  o L02 é a chance de recuperá-los.
- **Sem passo 3.** O L01 já roda só com API + PDF; não existe mais rota de
  planilha legada para o L02 herdar.
- **Comparar os dois `correspondencia.csv`** (L01 vs. L02) é o jeito de ver
  o que melhorou: quem saiu de `Academico=Não` para `Sim`, por exemplo. Como
  cada lote é append-only e o anterior fica intacto, a comparação é só
  colocar os dois CSVs lado a lado.
