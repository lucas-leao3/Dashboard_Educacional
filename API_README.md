# API de Alunos — Dashboard Educacional

Uma API FastAPI que consolida dados acadêmicos (CRG) e socioeconômicos de alunos da UFPA Cametá, casando-os pela matrícula.

## Visão Geral

A API mantém uma tabela única de alunos que une três fontes de dado:

| Fonte | Dados | Como entra |
|-------|-------|-----------|
| **FasiTech** | Socioeconômico (renda, moradia, saúde mental, etc.) | `POST /sincronizar` |
| **Histórico SIGAA** | CRG oficial + nome + data de nascimento | `POST /atualizar-crg` |
| **Planilha legada** | Campos socioeconômicos adicionais | `POST /preencher-legado` |

A API não calcula nada — importa dado já pronto e resolve conflitos entre fontes.

## Como Rodar Localmente

### Requisitos

- Python 3.14+
- `venvDashboard` (venv) configurada
- Variáveis de ambiente: `FASITECH_URL` e `FASITECH_TOKEN` em `backend/.env`

### Passos

```bash
# 1. Entre na raiz do projeto
cd Dashboard_Educacional

# 2. Ative a venv e set PYTHONPATH
$env:PYTHONPATH = "backend"
venvDashboard\Scripts\python.exe -m uvicorn app.main:app --reload
```

Servidor sobe em `http://127.0.0.1:8000`

- **Documentação interativa (Swagger)**: http://127.0.0.1:8000/docs
- **Health-check**: `GET /` retorna `{"status": "ok"}`

## As 6 Rotas

### 1. `GET /alunos`
Lista todos os alunos no banco.

**Resposta**: `200` com array de alunos (vazio se o banco tá vazio)

```json
[
  {
    "id": 12,
    "matricula": 202016040011,
    "periodo": "2026.1",
    "CRG": 7.9662,
    "nome": "NALBERTH DE LEAO CASTRO",
    "genero": "Masculino",
    "renda": "Até 1 salário mínimo",
    ...
  }
]
```

### 2. `GET /alunos/{matricula}`
Busca um aluno por matrícula (retorna a primeira linha se houver múltiplos períodos).

**Resposta**: 
- `200` — aluno encontrado
- `404` — não existe

### 3. `POST /alunos`
Cadastra um aluno manualmente. Só `matricula` e `periodo` são obrigatórios.

**Body**:
```json
{
  "matricula": 999999,
  "periodo": "2026.1",
  "CRG": 7.5,
  "nome": "Fulano"
}
```

**Resposta**:
- `201` — criado
- `409` — já existe essa matrícula+período
- `422` — falta matrícula ou período

### 4. `POST /alunos/sincronizar`
Busca todos os alunos no FasiTech e salva os que ainda não existem.

**Resposta**: `200` com contadores
```json
{ "importados": 156, "ignorados": 9 }
```

**Status de erro**:
- `502` — FasiTech fora do ar ou respondeu formato inesperado
- `503` — `FASITECH_URL` não configurada

### 5. `POST /alunos/atualizar-crg`
Lê `crg_historico.csv` e preenche CRG + nome + data de nascimento em todos os períodos daquele aluno.

**Resposta**: `200` com contadores
```json
{ "atualizados": 87, "nao_encontrados": 0 }
```

**Status de erro**:
- `503` — `crg_historico.csv` não encontrado em `backend/app/data/`

### 6. `POST /alunos/preencher-legado`
Lê `DadosAgrupados.csv` e preenche **somente campos vazios**. Nunca sobrescreve ou mexe em CRG.

**Resposta**: `200` com contadores
```json
{ "atualizados": 41, "campos_preenchidos": 118 }
```

**Status de erro**:
- `503` — `DadosAgrupados.csv` não encontrado em `backend/app/data/`

## Fluxo de Uso Típico

```bash
# 1. Sincronizar com FasiTech (todos os alunos + socioeconômico)
POST /alunos/sincronizar

# 2. Preencher CRG do histórico (56 alunos ganham CRG)
POST /atualizar-crg

# 3. Completar dados que sobraram (alguns ganham escolaridade dos pais, etc.)
POST /alunos/preencher-legado

# 4. Ver resultado final
GET /alunos
```

Essas rotas são idempotentes — rodar 2x não quebra nada, só reforça o que já está certo.

## Dados Faltantes

Hoje (02/09/2026): 103 alunos distintos, 56 com CRG completo, 47 ainda aguardando histórico.

Um aluno **sem CRG** aparece normal na API com `"CRG": null`. O resto dos dados continua acessível. Quando o histórico dele chegar, é só rodar `/atualizar-crg` de novo.

```json
{
  "matricula": 202116040005,
  "periodo": "2024.(3 e 4)",
  "CRG": null,              // falta — será preenchido quando histórico chegar
  "genero": "Feminino",     // veio do FasiTech
  "renda": "Até 1 salário mínimo",
  ...
}
```

## Testes

19 testes automatizados cobrindo as 6 rotas. Rodam offline (nenhuma chamada real ao FasiTech).

```bash
PYTHONPATH=backend venvDashboard\Scripts\python.exe -m pytest -v
```

Resultado esperado: **19 passed**

## Arquivos de Configuração

### `backend/.env` (gitignored)
```
FASITECH_URL=https://...
FASITECH_TOKEN=...
```

### `backend/app/data/` (gitignored)
```
crg_historico.csv        # 56 alunos com CRG do histórico
DadosAgrupados.csv       # planilha manual antiga
BancoDeDados.sqlite      # banco SQLite local (auto-criado)
```

## Arquitetura

```
backend/app/
├── main.py                         # FastAPI app + health-check
├── api/alunos.py                   # as 6 rotas (199 linhas)
├── schemas/alunos.py               # Pydantic: AlunoCreate, AlunoOut
├── db/engine.py                    # SQLAlchemy: table Usuarios + engine
├── services/
│   ├── fasitech_client.py          # HTTP client paginado
│   ├── crg_historico.py            # leitor CSV histórico
│   └── dados_legado.py             # leitor CSV planilha antiga
└── core/config.py                  # .env loader

tests/
├── conftest.py                     # fixture client (banco isolado)
└── test_alunos.py                  # 19 testes
```

## Arquivos Criados Nesta Demanda

Todos os arquivos abaixo foram desenvolvidos especificamente para esta API — `db/engine.py` já existia antes e só recebeu ajuste de tipo em dois campos.

| Arquivo | O que faz |
|---|---|
| `schemas/alunos.py` | Contrato de dado (Pydantic). Define `AlunoCreate` e `AlunoOut` — só `matricula` e `periodo` são obrigatórios, o resto é opcional |
| `core/config.py` | Lê `.env` e expõe `FASITECH_URL` e `FASITECH_TOKEN` — único lugar que toca nessas credenciais |
| `services/fasitech_client.py` | Cliente HTTP que busca os alunos socioeconômicos no FasiTech, paginando até trazer tudo |
| `services/crg_historico.py` | Lê `crg_historico.csv` (extraído de 56 PDFs de histórico) e devolve CRG, nome e nascimento por matrícula |
| `services/dados_legado.py` | Lê `DadosAgrupados.csv` e devolve os campos socioeconômicos que ainda faltam, por matrícula+período — nunca inclui CRG |
| `api/alunos.py` | As 6 rotas da API — orquestra os três serviços acima e o banco |
| `main.py` | Cria a aplicação FastAPI, registra as rotas, health-check em `GET /` |
| `tests/conftest.py` | Fixture `client` — sobe a API real com um banco de teste isolado e temporário |
| `tests/test_alunos.py` | 19 testes automatizados cobrindo as 6 rotas, sucesso e erro |
| `db/engine.py` *(editado)* | `qtd_computador` e `qtd_celular` mudaram de número pra texto — a resposta real é categórica (ex: "Acima de 3") |

**Total**: 9 arquivos novos + 1 arquivo ajustado, 721 linhas adicionadas (commit `30a232e`, 02/09/2026).

## Limitações Conhecidas

1. **CRG incompleto**: 47 dos 103 alunos ainda faltam histórico
2. **Planilha legada é estática**: `DadosAgrupados.csv` é uma foto de um ponto no tempo
3. **Multiplicidade por matrícula**: Um aluno pode ter múltiplas linhas (um por período socioeconômico) — isso é proposital, use `GET /alunos` e agregue se quiser "um por aluno"

## Tratamento de Erros

| Status | Significa |
|--------|-----------|
| `502` | Dependência externa falhou (FasiTech indisponível, formato inesperado) |
| `503` | Pré-requisito local ausente (URL não configurada, CSV não encontrado em disco) |
| `404` | Recurso não existe (matrícula não cadastrada) |
| `409` | Conflito (matrícula+período já existe) |
| `422` | Dado inválido (falta campo obrigatório) |

## Próximas Etapas

- [ ] Adicionar 47 históricos faltantes a `crg_historico.csv`
- [ ] Implementar paginação em `GET /alunos` (hoje retorna tudo)
- [ ] Adicionar filtros por período, gênero, renda, etc.

---

**Última atualização**: 02/09/2026  
**Commits**: 19 testes passando, código em `main` branch  
**Documentação técnica completa**: Veja `/docs` no servidor ou consulte `backend/app/` direto
