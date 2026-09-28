# Operação de um lote

Roteiro de ponta a ponta para importar um lote. O "por quê" está em
`docs/governanca_simplificada.md` (fluxo atual) e `docs/governanca_dados.md`
(fundamentos: append-only, hashes, repositório de dados).

**Um lote = uma importação.** Você informa o responsável e envia um `.zip`
com os históricos do SIGAA em PDF. O sistema gera o id do lote, busca o
FasiTech, lê os históricos, extrai o período e **fecha o lote**. Lote fechado
não se edita, não recebe arquivo e não se reprocessa: dado novo é importação
nova.

## Pré-requisitos

1. **Credenciais do FasiTech.** Copie `backend/.env.example` para
   `backend/.env` e preencha `FASITECH_URL` e `FASITECH_TOKEN`. Troque
   também `POSTGRES_PASSWORD`. Esse arquivo nunca vai pro git.
2. **Docker Compose no ar:**
   ```bash
   docker compose up -d --build
   ```
   Sobe `db` (PostgreSQL, sem porta publicada), `backend` em
   `http://localhost:8000` e `frontend` em `http://localhost:8080`. O backend
   aplica as migrações ao subir. `./data` é montado como `/data` no backend.
3. **O `.zip` dos históricos.** Só os `.pdf` de dentro dele são usados
   (subpastas achatadas; `__MACOSX/`, `Thumbs.db` e afins são ignorados).
   `.rar` não é aceito — converta para zip. Dois PDFs com o mesmo nome e
   conteúdo diferente no mesmo zip são recusados.

## 1. Importar

**Pela tela (recomendado):** `http://localhost:8080/dados` → preencha
*Responsável pela importação*, escolha o `.zip` → **Importar** → confirme.

**Pelo terminal** (Python no host com `httpx`; o script só fala HTTP):

```bash
python scripts/lote.py importar --responsavel "Edinaldo" historicos.zip
# ou uma pasta com os PDFs -- o script compacta antes de enviar
python scripts/lote.py importar --responsavel "Edinaldo" /caminho/para/os/historicos/
```

**Pelo Swagger:** `http://localhost:8000/docs` → `POST /lotes/importar`,
`responsavel` e `arquivo`.

Leva segundos (os 56 PDFs do L01: ~7 s). A resposta traz o id gerado, o
período extraído, os contadores de cada passo e o resumo da integração.

**Se falhar, nada foi gravado** — nem no banco nem em disco. A mensagem diz o
motivo:

| Resposta | Causa | O que fazer |
|---|---|---|
| 400 | arquivo não é `.zip`, zip corrompido, zip sem PDF | refazer o zip |
| 409 | mesmo nome de PDF com conteúdo diferente no zip | remover/renomear a duplicata |
| 413 | mais de 100 MB descomprimidos | dividir em duas importações |
| 422 | responsável vazio; ou nenhum PDF legível (sem período) | preencher; conferir os PDFs |
| 502 / 503 | FasiTech fora do ar ou sem credencial | conferir `backend/.env` e tentar de novo |

## 2. Conferir

Na tela Dados, o relatório do lote aparece logo abaixo:

- **Dados não integrados** — quem ficou fora dos dashboards e por quê
  (sem acadêmico, sem socioeconômico, falha de identificação, matrícula não
  encontrada).
- **Dados integrados** — a base dos dashboards.
- Nos dois: quantos e quais campos ficaram sem resposta, e o percentual de
  preenchimento.

Pelo terminal: `python scripts/lote.py relatorio <id>`.

No dashboard (`http://localhost:8080`), o selo do cabeçalho mostra o lote e
o período. O total de alunos é o de **integrados**.

O que o fechamento deixou em disco:

| Arquivo | Conteúdo |
|---|---|
| `data/raw/lotes/<id>/historicos/*.pdf` | os PDFs do zip |
| `data/raw/lotes/<id>/fasitech.json` | a resposta do FasiTech, congelada |
| `data/raw/lotes/<id>/SHA256SUMS` | hash de cada insumo (`sha256sum -c SHA256SUMS`) |
| `data/raw/lotes/<id>/lote.md` | responsável, período, integração, ingestões, exceções, hashes, limitações |
| `data/processed/<id>/vigente.csv` | corte transversal de todos os vigentes (auditoria) |
| `data/processed/<id>/integrados.csv` | relatório de integrados |
| `data/processed/<id>/nao_integrados.csv` | relatório de não integrados |

## 3. Commit no repositório privado de dados

`data/raw/` não vai para este repositório (está no `.gitignore`) — vai para
o repositório privado `dashboard-dados` (`docs/governanca_dados.md`, seção
3.4).

```bash
git -C /caminho/para/dashboard-dados add raw/lotes/<id>
git -C /caminho/para/dashboard-dados commit -m "<id>"
```

## Próximo lote

Chegaram PDFs que faltavam (alunos hoje em "Possui socioeconômico e não
possui acadêmico")? Faça outra importação. O novo lote busca o FasiTech de
novo, lê os PDFs novos e os alunos passam a integrados. PDF que já entrou
num lote anterior (mesmo hash) não é regravado — conta como `duplicado` e
a matrícula continua reconhecida. O relatório do lote anterior continua como
estava quando ele fechou; comparar os dois mostra o que melhorou.
