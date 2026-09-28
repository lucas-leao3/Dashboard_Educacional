# Como inserir o primeiro lote (L01)

> **Atualização 25/09/2026 — governança simplificada.** A entrada de dados agora é
> uma importação só (`POST /lotes/importar`: responsável + `.zip`), com período
> extraído dos históricos, lote fechado automaticamente e imutável no banco, e
> dashboards só com alunos integrados. Este roteiro é o do L01, feito pelo fluxo antigo; para um lote novo, siga `docs/operacao_lote.md`. Ver `docs/governanca_simplificada.md`.

Roteiro mínimo, pelo Swagger. O "porquê" de cada coisa está em
`docs/governanca_dados.md`; o roteiro completo (com terminal) em
`docs/operacao_lote.md`.

## Antes de começar (uma vez só)

1. `backend/.env` preenchido: `FASITECH_URL`, `FASITECH_TOKEN` e uma
   `POSTGRES_PASSWORD` sua. (Modelo em `backend/.env.example`.)
2. Subir tudo:
   ```bash
   docker compose up -d --build
   ```
   Confira `http://localhost:8000/` → `{"status": "ok"}`.
3. Compactar os 56 PDFs num zip (mais fácil que selecionar um por um):
   ```bash
   cd backend/app/data/historicos && zip ../historicos_L01.zip *.pdf && cd -
   ```
   Gera `backend/app/data/historicos_L01.zip`. O nome do zip é livre — a API
   só usa a extensão `.zip` e descarta o resto; o que fica gravado no lote
   são os PDFs de dentro dele, com os nomes que têm. Não renomeie os PDFs.

## Pela tela do dashboard (mais simples)

Abra `http://localhost:8080/dados`. Os mesmos três passos, em botões:
**Abrir lote** (id sugerido, períodos `2025.2 2026.1`, seu nome) → **Enviar e rodar**
(selecione o `historicos_L01.zip`) → confira a cobertura que aparece embaixo →
**Fechar lote**. O que segue é o mesmo fluxo pelo Swagger.

## Os três passos

Abra `http://localhost:8000/docs`.

### 1. Abrir o lote — `POST /lotes`

Corpo:
```json
{"id": "2026-09-L01", "periodos_cobertos": ["2025.2", "2026.1"], "executado_por": "Edinaldo"}
```
Esperado: `201`. Se der `409`, o lote já existe — siga para o passo 2.

### 2. Enviar os PDFs e rodar — `POST /lotes/{lote_id}/historicos`

- `lote_id`: `2026-09-L01`
- `executar`: `true`
- `arquivos`: selecione `historicos_L01.zip`

Esperado: `200` com algo como
```json
{
  "gravados": ["...56 nomes..."],
  "sincronizar":  {"importados": 103, "rejeitados": 0, ...},
  "atualizar_crg": {"pdfs_lidos": 56, "alunos_atualizados": 56, "sem_academico": 47, ...}
}
```
`sem_academico: 47` é esperado — são os alunos do FasiTech que ainda não
têm histórico em PDF. Não é erro.

Se falhar (ex.: `502`, FasiTech fora do ar): os PDFs já ficaram gravados.
Corrija a causa e repita esta mesma chamada com o mesmo zip — o que já foi
feito é pulado.

### 3. Conferir e fechar

Confira:
- `GET /lotes/2026-09-L01` — duas ingestões (passos 1 e 2) e `excecoes_por_motivo`.
- `http://localhost:8080` — o dashboard mostra o selo do lote e os alunos.
- `data/raw/lotes/2026-09-L01/fasitech.json` — os períodos batem com
  `2025.2` e `2026.1`? Se não, anote na observação do lote.

Se estiver tudo certo: `POST /lotes/{lote_id}/fechar` com `lote_id` =
`2026-09-L01`. Esperado: `200` com `fechado_em` preenchido e os quatro
arquivos gerados (`SHA256SUMS`, `lote.md`, `vigente.csv`, `correspondencia.csv`).

**Fechar é definitivo.** Lote fechado não se reabre nem recebe mais PDF.
Se algo estiver errado, não feche: abra outro lote (`2026-09-L02`) e repita.

## Depois

Guarde os insumos no repositório privado de dados (não neste repo):
```bash
git -C /caminho/para/dashboard-dados add raw/lotes/2026-09-L01
git -C /caminho/para/dashboard-dados commit -m "2026-09-L01"
```

## O mesmo pelo terminal

```bash
python scripts/lote.py executar 2026-09-L01 --periodos 2025.2 2026.1 \
  --por "Edinaldo" --historicos backend/app/data/historicos/
# conferir
python scripts/lote.py fechar 2026-09-L01
```
