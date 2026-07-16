# Dashboard Educacional

Dashboard para visualização da relação entre dados acadêmicos e socioeconômicos de alunos.

## Objetivo

Mostrar como fatores socioeconômicos se relacionam com o desempenho acadêmico dos alunos, através de três visualizações:

1. **Socioeconômico x CRG** — relação entre dados socioeconômicos e a nota (CRG) do aluno
2. **Distribuição** — distribuição dos dados (acadêmicos e/ou socioeconômicos) entre os alunos
3. **Longitudinal** — evolução dos dados ao longo do tempo, por aluno/período

As três visualizações ficam num painel único.

## Stack

- **Backend:** FastAPI
- **ORM:** SQLAlchemy
- **Frontend:** React
- **Persistência:** SQLite
- **Estrutura de repositório:** Monorepo

## Arquitetura

```
dashboard-educacional/
├── backend/
│   ├── app/
│   │   ├── api/                # rotas: CRG, distribuição, longitudinal
│   │   ├── core/
│   │   │   ├── config.py       # variáveis de ambiente (.env)
│   │   │   ├── scheduler.py    # APScheduler — sync com FasiTech
│   │   │   └── rate_limit.py   # slowapi — rate limiting
│   │   ├── db/                 # models SQLAlchemy (SQLite)
│   │   ├── services/
│   │   │   ├── fasitech_client.py   # consome API FasiTech (token)
│   │   │   └── sync_service.py      # sync periódico com validação dupla
│   │   ├── schemas/            # validação Pydantic
│   │   └── main.py
│   ├── Dockerfile              # imagem do backend (Python/uvicorn)
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChartSocioeconomico.tsx
│   │   │   ├── ChartDistribuicao.tsx
│   │   │   └── ChartLongitudinal.tsx
│   │   └── pages/
│   │       └── Dashboard.tsx   # painel único
│   └── Dockerfile              # imagem do frontend (build Node + serve estático)
├── docs/
│   ├── README.md
│   └── dicionario_dados.md     # dicionário de dados do banco
└── docker-compose.yml          # orquestra backend + frontend
```

## Fonte de dados

### Dados socioeconômicos

Consultados via **API do FasiTech**, autenticada por token de acesso (armazenado em variável de ambiente, nunca hardcoded).

- **Sincronização:** automática, via APScheduler, a cada **6 meses**
- **Persistência:** os dados **não são sobrescritos**. A cada sync, novos registros são adicionados para o período correspondente
- **Validação:** dupla checagem por **número de matrícula + período**, para evitar duplicidade de dados no mesmo período
- Esse modelo (snapshot por período, e não upsert simples) é o que sustenta a visualização longitudinal — sem ele, o histórico se perderia a cada sincronização

### Dados acadêmicos

> ⚠️ **Pendente de decisão.** A forma de entrada dos dados acadêmicos (nota/CRG do aluno) ainda não foi definida.
>
> **Sugestão em avaliação** (não implementada, ainda a ser validada pela equipe): reaproveitar o modelo do projeto desenvolvido com o professor Elton — uma aplicação em Streamlit que recebe múltiplos arquivos PDF de registros acadêmicos e converte para JSON. Para este projeto, a proposta seria adaptar esse fluxo para gravar os dados diretamente no banco (SQLite), respeitando a mesma validação dupla por matrícula + período usada nos dados socioeconômicos.
>
> Outras alternativas possíveis a serem avaliadas: upload manual de planilha (xlsx/csv), integração com API do sistema acadêmico da instituição, ou formulário manual via frontend.

## Rate limiting

Como o acesso ao dashboard é **aberto (sem autenticação)**, os endpoints públicos usam **`slowapi`** para limitar requisições por IP, evitando sobrecarga do sistema.

## CORS

O frontend (React) e o backend (FastAPI) rodam em origens diferentes, então o CORS é configurado via `CORSMiddleware` no FastAPI, liberando apenas as origens definidas em variável de ambiente.

**Em caso de erro de CORS:**
- Verificar se a origin do frontend está corretamente listada na configuração (`.env`)
- Confirmar se o frontend está rodando na porta esperada
- O erro costuma aparecer no console do navegador como `blocked by CORS policy` — nesse caso, checar se a requisição está batendo na origin certa antes de investigar o backend

## Escalabilidade

- **Banco de dados:** o projeto inicia com SQLite. Caso o volume de requisições/dados cresça de forma frequente (múltiplas instituições, muitos alunos, acesso concorrente), a migração para **PostgreSQL** é recomendada — a troca é facilitada pelo uso do SQLAlchemy como ORM.

## Testes (sugestão, não prioritário)

Seguir o padrão já usado no projeto Caixa Diário: `pytest` + `ASGITransport`, cobrindo:
- Endpoints principais (CRG, distribuição, longitudinal)
- `sync_service` (validação dupla matrícula + período)

## Logging (sugestão, não prioritário)

`RotatingFileHandler` (mesmo padrão usado no projeto CPR), registrando erros de sincronização com a API FasiTech e falhas de validação de dados.

## Deploy

> ⚠️ **Pendente de decisão.** A forma de deploy ainda não foi definida — decisão a ser tomada pela equipe que assumir o projeto.

## Pendências em aberto

- [ ] Definir forma de entrada dos dados acadêmicos
- [ ] Definir estratégia de deploy
- [ ] Escolher biblioteca de gráficos no frontend (sugestão inicial: Recharts)
