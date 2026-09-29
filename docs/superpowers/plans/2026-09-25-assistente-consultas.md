# Assistente de consultas — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tela `/ia-chat` onde o usuário pergunta em português e recebe dashboard existente filtrado, dashboard dinâmico, tabela ou texto, sempre com explicação.

**Architecture:** O Groq recebe só a pergunta anonimizada e o catálogo, e devolve uma `ConsultaEstruturada` (JSON). O backend valida essa consulta contra o catálogo, decide a forma da resposta por regras, compila um `Select` do SQLAlchemy Core e o executa com a role `leitor_assistente`. O front aplica filtros pela URL nas telas existentes e desenha o dinâmico com Recharts. O histórico fica no `localStorage`.

**Tech Stack:** FastAPI, SQLAlchemy 2 Core, Pydantic 2, httpx (já instalado), PostgreSQL 17, Alembic, pytest + testcontainers; React 19, react-router 7, Recharts 3, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-25-assistente-consultas-design.md`

## Global Constraints

- **Antes da Task 1:** o trabalho da governança simplificada ainda não commitado precisa ser commitado ou guardado, e o trabalho segue numa branch nova `feat/assistente-consultas`. Os commits deste plano adicionam só os caminhos da tarefa.
- `.gitignore` engole `docs/` e `data/`: arquivo **novo** nesses caminhos entra com `git add -f`.
- Nenhuma dependência nova, nem no backend nem no frontend.
- Só PostgreSQL. Os testes do backend sobem PostgreSQL via testcontainers e exigem Docker. Rodar a partir da raiz: `pytest tests/<arquivo> -v`.
- Frontend: `cd frontend && npx vitest run <arquivo>`; lint `npm run lint`; build `npm run build`.
- **O LLM nunca recebe linha de aluno, resultado de consulta, nome ou matrícula** (spec D2).
- Todo SQL gerado a partir de pergunta passa por `executar_select` (role `leitor_assistente`, `statement_timeout` 5000 ms).
- Ausência nunca vira zero: CRG nulo continua `null`, e resposta vazia vira a categoria explícita (`Sem resposta`, `Sem polo informado`, `Sem turma informada`). Todo grupo carrega `n`.
- Aluno se conta por matrícula distinta. Sem a dimensão `periodo`, cada aluno entra uma vez, pela linha do período mais recente dentro do filtro.
- Textos de interface em português; identificadores em português, como o resto do projeto.

## Review Focus

1. O Groq devolve o JSON embrulhado em ```` ```json ```` ou com texto em volta, e a resposta tem que ser aproveitada (Task 8).
2. O LLM escreve o valor com outra grafia ("cameta", "CAMETÁ"), e ele tem que ser aceito e trocado pela grafia canônica (Task 2).
3. Base sem nenhum lote importado: os itens operacionais respondem "Nenhum lote importado ainda.", sem quebrar (Tasks 6 e 7).
4. `localStorage` indisponível, cheio ou com JSON corrompido: o histórico vem vazio e nada quebra (Task 10).
5. Link `?c=` adulterado: o front mostra "Link de consulta inválido." e o backend responde 422 a uma consulta fora do catálogo (Tasks 8 e 10).

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/core/config.py` (mod) | `GROQ_API_KEY`, `GROQ_MODELO`, `GROQ_URL` |
| `backend/app/schemas/assistente.py` | Contratos: `ConsultaEstruturada`, `RespostaAssistente` e blocos |
| `backend/app/services/assistente/provedor_llm.py` | `ProvedorLLM` (Protocol), `ProvedorGroq`, `LLMIndisponivel` |
| `backend/app/services/assistente/catalogo.py` | Dimensões, métricas, dashboards, `valores_validos`, `validar` |
| `backend/app/services/assistente/anonimizador.py` | Nome/matrícula → `⟨An⟩` e volta |
| `backend/migrations/versions/20260925_d7a2b4c6e810_role_leitor_assistente.py` | Role só-leitura |
| `backend/app/services/assistente/execucao.py` | `executar_select` com role e timeout |
| `backend/app/services/assistente/compilador.py` | Consulta → `Select`; `Resultado`; `resolver_sql` |
| `backend/app/services/assistente/operacionais.py` | Último lote, campos sem resposta, listas do relatório |
| `backend/app/services/assistente/planejador.py` | Forma da resposta + dashboard correspondente |
| `backend/app/services/assistente/visualizacao.py` | Gráfico pela forma do resultado |
| `backend/app/services/assistente/respostas.py` | Explicação, textos, tabela, "não entendi" |
| `backend/app/services/assistente/intencao.py` | Prompt, chamada, validação, nova tentativa |
| `backend/app/services/assistente/pipeline.py` | `perguntar`, `executar`, `responder` |
| `backend/app/api/assistente.py` | `POST /assistente/perguntar`, `POST /assistente/executar` |
| `frontend/src/domain/filtrosUrl.ts`, `hooks/useFiltroUrl.ts` | Filtros na query string |
| `frontend/src/domain/catalogoDashboards.ts` | id do dashboard → rota |
| `frontend/src/domain/historico.ts`, `compartilhar.ts`, `csv.ts`, `graficoDinamico.ts` | Lógica pura do chat |
| `frontend/src/components/assistente/*` | `Explicacao`, `RespostaTabela`, `GraficoDinamico`, `DashboardDinamico`, `RespostaView`, `Historico` |
| `frontend/src/pages/IaChat.tsx` | A tela |

---

### Task 1: Provedor LLM (Groq) e configuração

**Files:**
- Modify: `backend/app/core/config.py` (fim do arquivo)
- Modify: `backend/.env.example` (fim do arquivo)
- Create: `backend/app/services/assistente/__init__.py` (vazio)
- Create: `backend/app/services/assistente/provedor_llm.py`
- Test: `tests/test_assistente_provedor.py`

**Interfaces:**
- Produces: `class LLMIndisponivel(Exception)`; `class ProvedorLLM(Protocol): def completar(self, mensagens: list[dict]) -> str`; `class ProvedorGroq(chave: str, modelo: str, url: str, cliente: httpx.Client | None = None)`; `def provedor_padrao() -> ProvedorLLM`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assistente_provedor.py
"""ProvedorGroq: o único ponto que fala com o LLM. Nenhum teste chama a rede."""
import json

import httpx
import pytest

from app.services.assistente.provedor_llm import LLMIndisponivel, ProvedorGroq


def _groq(handler, chave="k"):
    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    return ProvedorGroq(chave, "modelo-x", "https://groq.test/v1", cliente=cliente)


def test_envia_pedido_json_deterministico_e_devolve_o_conteudo():
    visto = {}

    def handler(req):
        visto["url"] = str(req.url)
        visto["auth"] = req.headers["authorization"]
        visto["corpo"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"tipo": "agregado"}'}}]})

    assert _groq(handler).completar([{"role": "user", "content": "oi"}]) == '{"tipo": "agregado"}'
    assert visto["url"] == "https://groq.test/v1/chat/completions"
    assert visto["auth"] == "Bearer k"
    assert visto["corpo"]["model"] == "modelo-x"
    assert visto["corpo"]["temperature"] == 0
    assert visto["corpo"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status", [429, 500])
def test_erro_http_vira_indisponivel(status):
    with pytest.raises(LLMIndisponivel, match=str(status)):
        _groq(lambda req: httpx.Response(status)).completar([])


def test_falha_de_rede_vira_indisponivel():
    def handler(req):
        raise httpx.ConnectTimeout("lento")
    with pytest.raises(LLMIndisponivel):
        _groq(handler).completar([])


def test_resposta_sem_choices_vira_indisponivel():
    with pytest.raises(LLMIndisponivel):
        _groq(lambda req: httpx.Response(200, json={"erro": "x"})).completar([])


def test_sem_chave_nao_chama_a_rede():
    def handler(req):
        raise AssertionError("não devia chamar a rede")
    with pytest.raises(LLMIndisponivel, match="GROQ_API_KEY"):
        _groq(handler, chave="").completar([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assistente_provedor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.assistente'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/core/config.py`:

```python

# Assistente de consultas (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md).
# Sem GROQ_API_KEY o app sobe normalmente: só POST /assistente/perguntar
# responde 503. /assistente/executar não usa o LLM e segue funcionando.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODELO = os.getenv("GROQ_MODELO", "llama-3.3-70b-versatile")
GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1")
```

Append to `backend/.env.example`:

```
# Assistente de consultas. O Groq recebe só a pergunta anonimizada e o catálogo
# de campos, nunca dado de aluno. Sem chave, o chat responde 503.
# Modelos disponíveis: console do Groq. Troque GROQ_MODELO se este for descontinuado.
GROQ_API_KEY=
GROQ_MODELO=llama-3.3-70b-versatile
GROQ_URL=https://api.groq.com/openai/v1
```

Create `backend/app/services/assistente/__init__.py` empty.

Create `backend/app/services/assistente/provedor_llm.py`:

```python
"""Quem interpreta a pergunta: um LLM atrás de uma interface mínima.

O provedor não sabe nada de catálogo nem de prompt (isso é intencao.py): ele
recebe mensagens no formato de chat e devolve o texto da resposta. Trocar o
Groq por outro provedor compatível com OpenAI é mudar GROQ_URL e GROQ_MODELO;
um provedor de outro formato é uma classe nova com `completar`.

O que sai por aqui é só a pergunta anonimizada e o catálogo (spec, D2).
"""
from typing import Protocol

import httpx

from app.core import config

TIMEOUT_S = 20


class LLMIndisponivel(Exception):
    """Sem chave, fora do ar, timeout, 429 ou resposta sem forma: vira 503."""


class ProvedorLLM(Protocol):
    def completar(self, mensagens: list[dict]) -> str: ...


class ProvedorGroq:
    def __init__(self, chave: str, modelo: str, url: str, cliente: httpx.Client | None = None):
        self.chave = chave
        self.modelo = modelo
        self.url = url.rstrip("/")
        self.cliente = cliente or httpx.Client(timeout=TIMEOUT_S)

    def completar(self, mensagens: list[dict]) -> str:
        if not self.chave:
            raise LLMIndisponivel("GROQ_API_KEY não configurada: o assistente está desligado.")
        try:
            resposta = self.cliente.post(
                f"{self.url}/chat/completions",
                headers={"Authorization": f"Bearer {self.chave}"},
                json={
                    "model": self.modelo,
                    "messages": mensagens,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
        except httpx.HTTPError as erro:
            raise LLMIndisponivel(f"Groq inacessível ({erro.__class__.__name__}).") from erro
        if resposta.status_code != 200:
            raise LLMIndisponivel(f"Groq respondeu HTTP {resposta.status_code}.")
        try:
            return resposta.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as erro:
            raise LLMIndisponivel("Groq devolveu uma resposta sem o formato esperado.") from erro


def provedor_padrao() -> ProvedorLLM:
    return ProvedorGroq(config.GROQ_API_KEY, config.GROQ_MODELO, config.GROQ_URL)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assistente_provedor.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/.env.example backend/app/services/assistente/__init__.py backend/app/services/assistente/provedor_llm.py tests/test_assistente_provedor.py
git commit -m "feat(assistente): provedor LLM Groq atrás de interface própria"
```

---

### Task 2: Contratos e catálogo com validação

**Files:**
- Create: `backend/app/schemas/assistente.py`
- Create: `backend/app/services/assistente/catalogo.py`
- Test: `tests/test_assistente_catalogo.py`

**Interfaces:**
- Consumes: `app.services.relatorio.CAMPOS_SOCIOECONOMICOS`, `MOTIVOS`; `app.db.vigente.aluno_integrado`, `crg_semestre_vigente`.
- Produces (schemas): `Filtro(campo, op, valor)`, `Ordem(campo, direcao)`, `ConsultaEstruturada(tipo, metrica, dimensoes, filtros, ordem, limite, interpretacao)`, `PerguntaIn(pergunta)`, `ExecutarIn(consulta)`, `FiltroAplicado(rotulo, valor)`, `Explicacao(consulta_interpretada, filtros_aplicados, fontes, forma)`, `BlocoDashboard(id, params)`, `Kpi(rotulo, valor, n)`, `Grafico(tipo, titulo, eixo, serie, series, serie_ordinal, rotulo_valor, dados)`, `BlocoDinamico(kpis, graficos)`, `Coluna(id, rotulo)`, `BlocoTabela(colunas, linhas, total)`, `BlocoTexto(mensagem, valor, n)`, `BlocoNaoEntendi(motivo, sugestoes)`, `RespostaAssistente(...)`.
- Produces (catálogo): `ConsultaInvalida(ValueError)`; `Dimensao(id, rotulo, coluna, ausente, temporal, ordinal)`; `DIMENSOES: dict[str, Dimensao]`; `ROTULOS_RESPOSTA: dict[str, str]`; `RESPOSTAS: tuple[str, ...]`; `Metrica(id, rotulo, tipo, dimensoes, filtros, min_dimensoes, max_dimensoes, exige_dimensao)`; `METRICAS: dict[str, Metrica]`; `normalizar(texto) -> str`; `valores_validos(session) -> dict[str, list[str]]`; `validar(consulta, valores) -> ConsultaEstruturada`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assistente_catalogo.py
"""Catálogo: o que não está nele não existe para o assistente."""
import pytest
from sqlalchemy.orm import Session

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.catalogo import ConsultaInvalida, validar, valores_validos

VALORES = {
    "polo": ["Cametá", "Oeiras", "Sem polo informado"],
    "turma": ["2020", "2021", "Sem turma informada"],
    "periodo": ["2025.(1 e 2)", "2025.(3 e 4)"],
    "semestre": ["2024.1", "2024.2"],
    "renda": ["Até 1 salário mínimo", "De 1 a 2 salários mínimos", "Sem resposta"],
    "motivo": ["sem_academico", "sem_socioeconomico"],
}


def _c(**campos):
    return ConsultaEstruturada(**campos)


def test_aceita_consulta_do_catalogo():
    c = _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"],
           filtros=[{"campo": "turma", "op": "=", "valor": "2020"}])
    assert validar(c, VALORES) == c


def test_troca_valor_pela_grafia_canonica():
    c = _c(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "polo", "valor": "CAMETA"}])
    assert validar(c, VALORES).filtros[0].valor == "Cametá"


def test_aceita_numero_onde_o_catalogo_tem_texto():
    c = _c(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "turma", "valor": 2020}])
    assert validar(c, VALORES).filtros[0].valor == "2020"


def test_rejeita_metrica_inexistente_listando_as_validas():
    with pytest.raises(ConsultaInvalida, match="contagem_alunos"):
        validar(_c(tipo="agregado", metrica="evasao"), VALORES)


def test_rejeita_metrica_de_outro_tipo():
    with pytest.raises(ConsultaInvalida):
        validar(_c(tipo="lista", metrica="contagem_alunos"), VALORES)


def test_rejeita_dimensao_que_a_metrica_nao_aceita():
    with pytest.raises(ConsultaInvalida, match="semestre"):
        validar(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["semestre"]), VALORES)


def test_crg_por_semestre_exige_a_dimensao_semestre():
    with pytest.raises(ConsultaInvalida):
        validar(_c(tipo="agregado", metrica="crg_medio_semestre", dimensoes=["turma"]), VALORES)


def test_rejeita_valor_fora_do_catalogo_mostrando_os_validos():
    c = _c(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "polo", "valor": "Belém"}])
    with pytest.raises(ConsultaInvalida, match="Cametá"):
        validar(c, VALORES)


def test_entre_so_em_campo_ordenavel_e_com_dois_valores():
    ok = _c(tipo="agregado", metrica="contagem_alunos",
            filtros=[{"campo": "turma", "op": "entre", "valor": ["2020", "2021"]}])
    assert validar(ok, VALORES).filtros[0].valor == ["2020", "2021"]
    for filtro in ({"campo": "polo", "op": "entre", "valor": ["Cametá", "Oeiras"]},
                   {"campo": "turma", "op": "entre", "valor": ["2020"]}):
        with pytest.raises(ConsultaInvalida):
            validar(_c(tipo="agregado", metrica="contagem_alunos", filtros=[filtro]), VALORES)


def test_matricula_aceita_marcador_ou_digitos_e_nada_mais():
    for valor in ("⟨A1⟩", "202016040001"):
        c = _c(tipo="lista", metrica="alunos", filtros=[{"campo": "matricula", "valor": valor}])
        assert validar(c, VALORES).filtros[0].valor == valor
    with pytest.raises(ConsultaInvalida):
        validar(_c(tipo="lista", metrica="alunos", filtros=[{"campo": "matricula", "valor": "Maria"}]), VALORES)


def test_fora_do_catalogo_passa_direto():
    c = _c(tipo="fora_do_catalogo", interpretacao="Não há dado de evasão.")
    assert validar(c, VALORES) == c


async def test_valores_validos_vem_do_banco_com_o_rotulo_de_ausencia(db_engine, semear):
    semear(202016040001, renda="Até 1 salário mínimo")
    semear(202185940002)
    with Session(db_engine) as s:
        valores = valores_validos(s)
    assert valores["polo"] == ["Cametá", "Oeiras", "Sem polo informado"]
    assert valores["turma"] == ["2020", "2021", "Sem turma informada"]
    assert valores["renda"] == ["Até 1 salário mínimo", "Sem resposta"]
    assert valores["semestre"] == ["2025.1"]
    assert "sem_socioeconomico" in valores["motivo"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assistente_catalogo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.assistente'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/schemas/assistente.py`:

```python
"""Contratos do assistente (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md).

`ConsultaEstruturada` é o que o LLM devolve e o que o histórico guarda: ela é
reexecutável sem LLM por POST /assistente/executar."""
from typing import Any, Literal

from pydantic import BaseModel, Field

Forma = Literal["dashboard", "dinamico", "tabela", "texto", "nao_entendi"]


class Filtro(BaseModel):
    campo: str
    op: Literal["=", "in", "entre"] = "="
    valor: Any


class Ordem(BaseModel):
    campo: str  # "valor" ou uma dimensão da consulta
    direcao: Literal["asc", "desc"] = "desc"


class ConsultaEstruturada(BaseModel):
    tipo: Literal["agregado", "lista", "operacional", "fora_do_catalogo"]
    metrica: str | None = None
    dimensoes: list[str] = Field(default_factory=list, max_length=2)
    filtros: list[Filtro] = Field(default_factory=list)
    ordem: Ordem | None = None
    limite: int | None = Field(default=None, ge=1, le=1000)
    interpretacao: str = ""


class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)


class ExecutarIn(BaseModel):
    consulta: ConsultaEstruturada


class FiltroAplicado(BaseModel):
    rotulo: str
    valor: str


class Explicacao(BaseModel):
    consulta_interpretada: str
    filtros_aplicados: list[FiltroAplicado]
    fontes: list[str]
    forma: Forma


class BlocoDashboard(BaseModel):
    id: str
    params: dict[str, str]


class Kpi(BaseModel):
    rotulo: str
    valor: float | None
    n: int


class Grafico(BaseModel):
    tipo: Literal["barras", "barras_empilhadas", "barras_agrupadas", "linha", "rosca", "histograma"]
    titulo: str
    eixo: str
    serie: str | None = None
    #: valores da série na ordem de exibição (natural, se ordinal)
    series: list[str] = Field(default_factory=list)
    serie_ordinal: bool = False
    rotulo_valor: str
    dados: list[dict[str, Any]]


class BlocoDinamico(BaseModel):
    kpis: list[Kpi] = Field(default_factory=list)
    graficos: list[Grafico] = Field(default_factory=list)


class Coluna(BaseModel):
    id: str
    rotulo: str


class BlocoTabela(BaseModel):
    colunas: list[Coluna]
    linhas: list[dict[str, Any]]
    total: int


class BlocoTexto(BaseModel):
    mensagem: str
    valor: float | None = None
    n: int | None = None


class BlocoNaoEntendi(BaseModel):
    motivo: str
    sugestoes: list[str]


class RespostaAssistente(BaseModel):
    id: str
    pergunta: str | None
    consulta: ConsultaEstruturada | None
    forma: Forma
    explicacao: Explicacao
    dashboard: BlocoDashboard | None = None
    dinamico: BlocoDinamico | None = None
    tabela: BlocoTabela | None = None
    texto: BlocoTexto | None = None
    nao_entendi: BlocoNaoEntendi | None = None
```

Create `backend/app/services/assistente/catalogo.py`:

```python
"""O que o assistente sabe consultar: a fonte única do prompt, da validação e
do planejamento. Quem não está aqui não existe para o assistente.

Respostas socioeconômicas = CAMPOS_SOCIOECONOMICOS do relatório: os campos que
o FasiTech de fato envia. Campo que a fonte não manda (escolaridade dos pais,
computador próprio...) viria nulo para 100% da base; oferecê-lo ao LLM só
geraria gráfico de "Sem resposta".
"""
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from app.db.vigente import aluno_integrado, crg_semestre_vigente
from app.schemas.assistente import ConsultaEstruturada, Filtro
from app.services.relatorio import CAMPOS_SOCIOECONOMICOS, MOTIVOS


class ConsultaInvalida(ValueError):
    """A consulta cita algo fora do catálogo. A mensagem volta ao LLM na nova
    tentativa, então diz o que é aceito."""


@dataclass(frozen=True)
class Dimensao:
    id: str
    rotulo: str
    coluna: str | None  # coluna de aluno_integrado; None = não vem dela
    ausente: str = "Sem resposta"
    temporal: bool = False
    ordinal: bool = False


ROTULOS_RESPOSTA = {
    "genero": "Gênero", "cor_etnia": "Cor/Etnia", "pcd": "PcD", "tipo_deficiencia": "Tipo de deficiência",
    "renda": "Renda familiar", "deslocamento": "Deslocamento", "trabalho": "Trabalho",
    "assistencia_estudantil": "Assistência estudantil", "gasto_internet": "Gasto com internet",
    "saude_mental": "Saúde mental", "estresse": "Estresse", "tipo_moradia": "Tipo de moradia",
    "acesso_internet": "Acesso à internet",
}
RESPOSTAS = tuple(CAMPOS_SOCIOECONOMICOS)

_DIMENSOES = [
    # Os rótulos de ausência de polo e turma são os mesmos do front (SEM_POLO, SEM_TURMA).
    Dimensao("polo", "Polo", "polo_nome", ausente="Sem polo informado"),
    Dimensao("turma", "Turma", "turma", ausente="Sem turma informada", ordinal=True),
    Dimensao("periodo", "Período de coleta", "periodo", temporal=True, ordinal=True),
    Dimensao("semestre", "Semestre letivo", None, temporal=True, ordinal=True),
    Dimensao("matricula", "Matrícula", "matricula"),
    Dimensao("motivo", "Motivo", None),
    *[Dimensao(c, ROTULOS_RESPOSTA[c], c, ordinal=(c == "renda")) for c in RESPOSTAS],
]
DIMENSOES = {d.id: d for d in _DIMENSOES}


@dataclass(frozen=True)
class Metrica:
    id: str
    rotulo: str
    tipo: str  # agregado | lista | operacional
    dimensoes: frozenset[str]
    filtros: frozenset[str]
    min_dimensoes: int = 0
    max_dimensoes: int = 2
    exige_dimensao: str | None = None


_AGRUPAVEIS = frozenset({"polo", "turma", "periodo", *RESPOSTAS})
_FILTRAVEIS = _AGRUPAVEIS | {"matricula"}
_NENHUMA = frozenset()

_METRICAS = [
    Metrica("contagem_alunos", "Contagem de alunos", "agregado", _AGRUPAVEIS, _FILTRAVEIS),
    Metrica("crg_medio", "CRG médio", "agregado", _AGRUPAVEIS, _FILTRAVEIS),
    Metrica("distribuicao_crg", "Distribuição do CRG", "agregado", _NENHUMA, _FILTRAVEIS, max_dimensoes=0),
    Metrica("crg_medio_semestre", "CRG médio por semestre letivo", "agregado",
            frozenset({"semestre", "polo", "turma"}), frozenset({"semestre", "polo", "turma", "matricula"}),
            min_dimensoes=1, exige_dimensao="semestre"),
    Metrica("alunos", "Lista de alunos", "lista", _NENHUMA, _FILTRAVEIS, max_dimensoes=0),
    Metrica("alunos_incompletos", "Alunos integrados com campos sem resposta", "lista", _NENHUMA,
            frozenset({"polo", "turma"}), max_dimensoes=0),
    Metrica("nao_integrados", "Alunos não integrados", "lista", _NENHUMA, frozenset({"motivo"}), max_dimensoes=0),
    Metrica("resumo_ultimo_lote", "Resumo do último lote", "operacional", _NENHUMA, _NENHUMA, max_dimensoes=0),
    Metrica("campos_sem_resposta", "Campos com mais respostas ausentes", "operacional", _NENHUMA, _NENHUMA,
            max_dimensoes=0),
]
METRICAS = {m.id: m for m in _METRICAS}

_ENTRE = frozenset({"turma", "periodo", "semestre"})
_MATRICULA = re.compile(r"⟨A\d+⟩|\d{9,}")


def normalizar(texto: str) -> str:
    """Sem acento, sem caixa, espaços simples: para casar grafias diferentes."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def valores_validos(session: Session) -> dict[str, list[str]]:
    """Valores que cada dimensão tem hoje na base dos dashboards. Lido a cada
    pergunta: a base é pequena e muda a cada lote."""
    valores: dict[str, list[str]] = {}
    for d in _DIMENSOES:
        if d.coluna is None or d.id == "matricula":
            continue
        coluna = aluno_integrado.c[d.coluna]
        brutos = session.execute(select(distinct(coluna)).where(coluna.is_not(None))).scalars()
        valores[d.id] = sorted({str(v) for v in brutos if str(v).strip()}) + [d.ausente]
    valores["semestre"] = sorted(session.execute(select(distinct(crg_semestre_vigente.c.semestre))).scalars())
    valores["motivo"] = sorted(MOTIVOS)
    return valores


def validar(consulta: ConsultaEstruturada, valores: dict[str, list[str]]) -> ConsultaEstruturada:
    """Confere a consulta contra o catálogo e devolve uma cópia com os valores de
    filtro na grafia canônica ("cameta" -> "Cametá"). Levanta ConsultaInvalida."""
    if consulta.tipo == "fora_do_catalogo":
        return consulta
    metrica = METRICAS.get(consulta.metrica or "")
    if metrica is None or metrica.tipo != consulta.tipo:
        aceitas = ", ".join(m.id for m in _METRICAS if m.tipo == consulta.tipo)
        raise ConsultaInvalida(f"metrica {consulta.metrica!r} não existe para tipo {consulta.tipo!r}; use: {aceitas}")
    if len(set(consulta.dimensoes)) != len(consulta.dimensoes):
        raise ConsultaInvalida("dimensão repetida")
    fora = [d for d in consulta.dimensoes if d not in metrica.dimensoes]
    if fora:
        raise ConsultaInvalida(f"dimensões {fora} não se aplicam a {metrica.id}; aceitas: {sorted(metrica.dimensoes)}")
    if not metrica.min_dimensoes <= len(consulta.dimensoes) <= metrica.max_dimensoes:
        raise ConsultaInvalida(f"{metrica.id} aceita de {metrica.min_dimensoes} a {metrica.max_dimensoes} dimensões")
    if metrica.exige_dimensao and metrica.exige_dimensao not in consulta.dimensoes:
        raise ConsultaInvalida(f"{metrica.id} exige a dimensão {metrica.exige_dimensao!r}")
    if consulta.ordem and consulta.ordem.campo not in {"valor", *consulta.dimensoes}:
        raise ConsultaInvalida("ordem.campo deve ser 'valor' ou uma dimensão da consulta")
    filtros = [_validar_filtro(f, metrica, valores) for f in consulta.filtros]
    return consulta.model_copy(update={"filtros": filtros})


def _validar_filtro(filtro: Filtro, metrica: Metrica, valores: dict[str, list[str]]) -> Filtro:
    if filtro.campo not in metrica.filtros:
        raise ConsultaInvalida(f"filtro {filtro.campo!r} não se aplica a {metrica.id}; aceitos: {sorted(metrica.filtros)}")
    brutos = filtro.valor if isinstance(filtro.valor, list) else [filtro.valor]
    if filtro.op == "=" and len(brutos) != 1:
        raise ConsultaInvalida("op '=' recebe um valor só")
    if filtro.op == "in" and not brutos:
        raise ConsultaInvalida("op 'in' recebe uma lista com ao menos um valor")
    if filtro.op == "entre" and (filtro.campo not in _ENTRE or len(brutos) != 2):
        raise ConsultaInvalida(f"op 'entre' só vale para {sorted(_ENTRE)} e recebe [início, fim]")
    if filtro.campo == "matricula":
        canonicos = [str(v) for v in brutos]
        if not all(_MATRICULA.fullmatch(v) for v in canonicos):
            raise ConsultaInvalida("matricula aceita só marcadores ⟨An⟩")
    else:
        canonicos = [_canonico(filtro.campo, str(v), valores) for v in brutos]
    return Filtro(campo=filtro.campo, op=filtro.op, valor=canonicos[0] if filtro.op == "=" else canonicos)


def _canonico(campo: str, valor: str, valores: dict[str, list[str]]) -> str:
    por_forma = {normalizar(v): v for v in valores.get(campo, [])}
    try:
        return por_forma[normalizar(valor)]
    except KeyError:
        raise ConsultaInvalida(f"valor {valor!r} não existe em {campo}; valores: {valores.get(campo, [])}") from None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assistente_catalogo.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/assistente.py backend/app/services/assistente/catalogo.py tests/test_assistente_catalogo.py
git commit -m "feat(assistente): contratos e catálogo com validação contra valores do banco"
```

---

### Task 3: Anonimizador

**Files:**
- Create: `backend/app/services/assistente/anonimizador.py`
- Test: `tests/test_assistente_anonimizador.py`

**Interfaces:**
- Produces: `dobrar(texto) -> str`; `Anonimizada(texto: str, marcadores: dict[str, str])` (marcador → matrícula em texto); `nomes_da_base(session) -> dict[str, str]` (nome dobrado → matrícula); `anonimizar(pergunta, nomes) -> Anonimizada`; `restaurar(texto, marcadores) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assistente_anonimizador.py
"""O que identifica aluno não sai da máquina (spec, D2)."""
from sqlalchemy.orm import Session

from app.services.assistente.anonimizador import anonimizar, nomes_da_base, restaurar

NOMES = {"maria da silva": "202016040001"}


def test_matricula_vira_marcador_e_volta():
    a = anonimizar("Perfil da matrícula 202016040001", {})
    assert a.texto == "Perfil da matrícula ⟨A1⟩"
    assert restaurar(a.texto, a.marcadores) == "Perfil da matrícula 202016040001"


def test_qualquer_sequencia_longa_de_digitos_sai_mesmo_fora_da_base():
    assert anonimizar("aluno 999999999", {}).texto == "aluno ⟨A1⟩"


def test_nome_da_base_casa_sem_caixa_e_sem_acento():
    a = anonimizar("Mostre a MARIA DA SÍLVA", NOMES)
    assert a.texto == "Mostre a ⟨A1⟩"
    assert a.marcadores == {"⟨A1⟩": "202016040001"}


def test_nome_e_matricula_do_mesmo_aluno_viram_o_mesmo_marcador():
    a = anonimizar("Maria da Silva, matrícula 202016040001", NOMES)
    assert a.texto == "⟨A1⟩, matrícula ⟨A1⟩"


def test_palavra_solta_e_trecho_de_palavra_nao_casam():
    assert anonimizar("alunos de Maria", NOMES).texto == "alunos de Maria"
    assert anonimizar("rosemaria da silvana", NOMES).texto == "rosemaria da silvana"


async def test_nomes_da_base_ignora_nome_de_uma_palavra(db_engine, semear):
    semear(202016040001, nome="MARIA DA SILVA")
    semear(202016040002, nome="JOSE")
    with Session(db_engine) as s:
        assert nomes_da_base(s) == {"maria da silva": "202016040001"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assistente_anonimizador.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/assistente/anonimizador.py
"""Tira da pergunta o que identifica aluno antes de ela sair para o LLM (spec, D2).

Matrícula (qualquer sequência de 9+ dígitos) e nome da base (2+ palavras,
comparado sem caixa e sem acento) viram marcadores ⟨A1⟩, ⟨A2⟩... O mapa fica
na requisição; o LLM usa o marcador como valor do filtro `matricula` e o
pipeline troca de volta. Nome de uma palavra só fica de fora de propósito:
casaria com palavra comum da pergunta.
"""
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import Historico, Usuarios

_DIGITOS = re.compile(r"\d{9,}")
_MARCADOR = re.compile(r"⟨A\d+⟩")


def _dobrar(c: str) -> str:
    base = "".join(x for x in unicodedata.normalize("NFKD", c) if not unicodedata.combining(x)).lower()
    return base[:1] or c


def dobrar(texto: str) -> str:
    """Sem acento e em minúscula, caractere a caractere: o resultado tem o mesmo
    tamanho do original, então uma posição achada nele vale no original."""
    return "".join(_dobrar(c) for c in texto)


@dataclass
class Anonimizada:
    texto: str
    marcadores: dict[str, str] = field(default_factory=dict)  # "⟨A1⟩" -> "202016040001"


def nomes_da_base(session: Session) -> dict[str, str]:
    nomes: dict[str, str] = {}
    for tabela in (Historico, Usuarios):
        linhas = session.execute(select(tabela.nome, tabela.matricula).where(tabela.nome.is_not(None)))
        for nome, matricula in linhas:
            chave = " ".join(dobrar(nome).split())
            if len(chave.split()) >= 2:
                nomes.setdefault(chave, str(matricula))
    return nomes


def anonimizar(pergunta: str, nomes: dict[str, str]) -> Anonimizada:
    texto = " ".join(pergunta.split())
    marcadores: dict[str, str] = {}
    por_matricula: dict[str, str] = {}

    def marcar(matricula: str) -> str:
        if matricula not in por_matricula:
            por_matricula[matricula] = f"⟨A{len(por_matricula) + 1}⟩"
            marcadores[por_matricula[matricula]] = matricula
        return por_matricula[matricula]

    texto = _DIGITOS.sub(lambda m: marcar(m.group()), texto)
    dobrado = dobrar(texto)
    trechos: list[tuple[int, int, str]] = []
    for nome in sorted(nomes, key=len, reverse=True):  # o nome mais longo ganha
        for achado in re.finditer(rf"(?<!\w){re.escape(nome)}(?!\w)", dobrado):
            if not any(achado.start() < fim and inicio < achado.end() for inicio, fim, _ in trechos):
                trechos.append((achado.start(), achado.end(), marcar(nomes[nome])))
    for inicio, fim, marcador in sorted(trechos, reverse=True):
        texto = texto[:inicio] + marcador + texto[fim:]
    return Anonimizada(texto, marcadores)


def restaurar(texto: str, marcadores: dict[str, str]) -> str:
    return _MARCADOR.sub(lambda m: marcadores.get(m.group(), m.group()), texto)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assistente_anonimizador.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/assistente/anonimizador.py tests/test_assistente_anonimizador.py
git commit -m "feat(assistente): anonimizador de nome e matrícula antes do LLM"
```

---

### Task 4: Role só-leitura e execução protegida

**Files:**
- Create: `backend/migrations/versions/20260925_d7a2b4c6e810_role_leitor_assistente.py`
- Create: `backend/app/services/assistente/execucao.py`
- Test: `tests/test_assistente_execucao.py`

**Interfaces:**
- Produces: `ROLE = "leitor_assistente"`; `class ConsultaDemorada(Exception)`; `executar_select(session, consulta: Select, timeout_ms: int = 5000) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assistente_execucao.py
"""Segunda camada de defesa: mesmo que o compilador erre, o banco recusa."""
import pytest
from sqlalchemy import func, literal_column, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.vigente import aluno_integrado
from app.services.assistente.execucao import ConsultaDemorada, executar_select


@pytest.mark.parametrize("sql", [
    "INSERT INTO polo (codigo, nome) VALUES ('9999', 'X')",
    "UPDATE polo SET nome = 'X'",
    "DELETE FROM usuarios",
    "DROP VIEW aluno_integrado",
    "ALTER TABLE usuarios ADD COLUMN x int",
    "TRUNCATE usuarios",
    "SELECT * FROM usuarios",  # tabela crua: fora da whitelist
])
async def test_role_do_assistente_so_le_as_views_liberadas(db_engine, sql):
    with Session(db_engine) as s:
        s.execute(text("SET LOCAL ROLE leitor_assistente"))
        with pytest.raises(ProgrammingError, match="permission denied|must be owner"):
            s.execute(text(sql))


async def test_executa_como_a_role_e_devolve_dicionarios(db_engine, semear):
    semear(202016040001)
    with Session(db_engine) as s:
        linhas = executar_select(s, select(literal_column("current_user").label("quem"),
                                           select(func.count()).select_from(aluno_integrado).scalar_subquery().label("n")))
        assert linhas == [{"quem": "leitor_assistente", "n": 1}]
        # role e timeout morrem com a transação
        assert s.execute(text("SELECT current_user")).scalar() != "leitor_assistente"


async def test_recusa_o_que_nao_e_select(db_engine):
    with Session(db_engine) as s, pytest.raises(TypeError):
        executar_select(s, text("DELETE FROM usuarios"))


async def test_consulta_lenta_e_cancelada(db_engine):
    with Session(db_engine) as s, pytest.raises(ConsultaDemorada):
        executar_select(s, select(func.pg_sleep(1)), timeout_ms=100)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assistente_execucao.py -v`
Expected: FAIL. Os testes da role falham com `role "leitor_assistente" does not exist`, e os demais com `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/migrations/versions/20260925_d7a2b4c6e810_role_leitor_assistente.py
"""role leitor_assistente: só leitura, só nas views do assistente

Revision ID: d7a2b4c6e810
Revises: c5e8a1f3d920
Create Date: 2026-09-25

O assistente de consultas executa SQL montado a partir da pergunta de um
usuário. O compilador só produz SELECT, mas a garantia não pode depender só
dele: a execução assume esta role (SET LOCAL ROLE), que tem SELECT apenas nas
duas views que o compilador usa. INSERT, UPDATE, DELETE, DROP, ALTER e
TRUNCATE são recusados pelo próprio banco. Os itens operacionais (relatório
do lote) não passam por aqui: são código fixo, sem SQL derivado da pergunta.

A role é do cluster, não do banco: o downgrade revoga os privilégios mas não a
apaga, porque outros bancos do mesmo servidor (os clones da suíte de testes,
por exemplo) podem ter grants para ela.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd7a2b4c6e810'
down_revision: Union[str, Sequence[str], None] = 'c5e8a1f3d920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE = "leitor_assistente"
VIEWS = "aluno_integrado, crg_semestre_vigente"


def upgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE} NOLOGIN;
            END IF;
        END $$""")
    op.execute(f"GRANT {ROLE} TO CURRENT_USER")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT ON {VIEWS} TO {ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE SELECT ON {VIEWS} FROM {ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE}")
```

```python
# backend/app/services/assistente/execucao.py
"""Executa o SELECT do compilador com o mínimo de privilégio (spec, Execução)."""
from sqlalchemy import Select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

ROLE = "leitor_assistente"
TIMEOUT_MS = 5000
_CANCELADA = "57014"  # query_canceled: statement_timeout


class ConsultaDemorada(Exception):
    """Passou do statement_timeout: vira 504 na API."""


def executar_select(session: Session, consulta: Select, timeout_ms: int = TIMEOUT_MS) -> list[dict]:
    """Roda `consulta` como leitor_assistente, com timeout, e encerra a transação.

    SET LOCAL vale até o fim da transação; o rollback no finally garante que
    nem a role nem o timeout sobrevivem para a próxima consulta da sessão.
    Não há nada a desfazer: é só leitura."""
    if not isinstance(consulta, Select):
        raise TypeError("O assistente só executa SELECT montado pelo compilador.")
    try:
        session.execute(text(f"SET LOCAL ROLE {ROLE}"))
        session.execute(text(f"SET LOCAL statement_timeout = {int(timeout_ms)}"))
        return [dict(linha) for linha in session.execute(consulta).mappings()]
    except OperationalError as erro:
        if getattr(erro.orig, "sqlstate", None) == _CANCELADA:
            raise ConsultaDemorada() from erro
        raise
    finally:
        session.rollback()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assistente_execucao.py tests/test_schema.py -v`
Expected: tudo passa (`test_schema.py` confirma que a revisão nova não quebra as migrações).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/20260925_d7a2b4c6e810_role_leitor_assistente.py backend/app/services/assistente/execucao.py tests/test_assistente_execucao.py
git commit -m "feat(assistente): role leitor_assistente e execução com timeout"
```

---

### Task 5: Compilador (agregados e lista de alunos)

**Files:**
- Create: `backend/app/services/assistente/compilador.py`
- Test: `tests/test_assistente_compilador.py`

**Interfaces:**
- Consumes: `DIMENSOES`, `RESPOSTAS` (Task 2); `executar_select` (Task 4).
- Produces: `Resultado(colunas: list[str], linhas: list[dict], fontes: list[str], total: int | None = None)`; `compilar(consulta) -> Select`; `fontes(consulta) -> list[str]`; `resolver_sql(session, consulta) -> Resultado`. Chaves das linhas: agregados trazem os ids das dimensões + `valor` + `n` (`crg_medio_semestre` traz `semestre`; `distribuicao_crg` traz `faixa`); a lista traz `matricula, nome, polo, turma, periodo, crg` + os campos de resposta filtrados.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assistente_compilador.py
"""Os números do assistente têm que ser os mesmos das telas."""
from sqlalchemy.orm import Session

from app.db.engine import CrgSemestre
from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.compilador import resolver_sql

A, B, C, D = 202016040001, 202016040002, 202185940003, 202216040004


def _cenario(semear):
    """A: Cametá/2020, dois períodos, mudou de renda. B: Cametá/2020, sem renda.
    C: Oeiras/2021, sem CRG. D: só socioeconômico (não integrado)."""
    semear(A, periodo="2025.(1 e 2)", renda="Até 1 salário mínimo", CRG=6.0)
    semear(A, periodo="2025.(3 e 4)", renda="De 1 a 2 salários mínimos", CRG=6.0)
    semear(B, periodo="2025.(3 e 4)", CRG=8.0)
    semear(C, periodo="2025.(3 e 4)", renda="Até 1 salário mínimo")
    semear(D, periodo="2025.(3 e 4)", academico=False)


def _rodar(db_engine, **consulta):
    with Session(db_engine) as s:
        return resolver_sql(s, ConsultaEstruturada(**consulta))


def _por(resultado, chave):
    return {l[chave]: l["valor"] for l in resultado.linhas}


async def test_contagem_por_polo_bate_com_get_alunos(client, db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"])
    esperado: dict[str, set] = {}
    for a in (await client.get("/alunos")).json():
        esperado.setdefault(a["polo_nome"], set()).add(a["matricula"])
    assert _por(r, "polo") == {p: len(m) for p, m in esperado.items()} == {"Cametá": 2, "Oeiras": 1}
    assert r.fontes == ["aluno_integrado"]


async def test_aluno_conta_uma_vez_pela_resposta_mais_recente(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"])
    assert _por(r, "renda") == {"De 1 a 2 salários mínimos": 1, "Até 1 salário mínimo": 1, "Sem resposta": 1}


async def test_por_periodo_o_aluno_entra_em_cada_periodo(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="contagem_alunos", dimensoes=["periodo"])
    assert _por(r, "periodo") == {"2025.(1 e 2)": 1, "2025.(3 e 4)": 3}


async def test_crg_medio_usa_um_crg_por_aluno_e_ignora_nulo(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="crg_medio")
    assert r.linhas == [{"valor": 7.0, "n": 2}]  # (6 + 8) / 2; por período seria 6,67


async def test_filtro_por_turma_sem_dimensao(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="contagem_alunos",
               filtros=[{"campo": "turma", "valor": "2020"}])
    assert r.linhas == [{"valor": 2, "n": 2}]


async def test_crg_por_semestre_bate_com_get_crg_semestres_e_preserva_nulo(client, db_engine, semear):
    _cenario(semear)
    with Session(db_engine) as s:
        passo2 = semear.ingestoes[2]
        s.add_all([CrgSemestre(matricula=A, semestre="2025.2", crg=5.0, ingestao_id=passo2),
                   CrgSemestre(matricula=B, semestre="2025.2", crg=None, ingestao_id=passo2),
                   CrgSemestre(matricula=A, semestre="2024.2", crg=None, ingestao_id=passo2)])
        s.commit()
    r = _rodar(db_engine, tipo="agregado", metrica="crg_medio_semestre", dimensoes=["semestre"])
    notas: dict[str, list] = {}
    for p in (await client.get("/crg-semestres")).json():
        notas.setdefault(p["semestre"], []).append(p["crg"])
    esperado = {s: (round(sum(v for v in vs if v is not None) / len([v for v in vs if v is not None]), 2)
                    if any(v is not None for v in vs) else None) for s, vs in notas.items()}
    assert _por(r, "semestre") == esperado
    assert _por(r, "semestre")["2024.2"] is None
    assert r.fontes == ["crg_semestre_vigente", "aluno_integrado"]


async def test_distribuicao_do_crg_em_faixas_inteiras(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="agregado", metrica="distribuicao_crg")
    assert _por(r, "faixa") == {6: 1, 8: 1}


async def test_lista_de_alunos_do_polo_com_total(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="lista", metrica="alunos", filtros=[{"campo": "polo", "valor": "Cametá"}])
    assert [l["matricula"] for l in r.linhas] == [A, B]
    assert r.linhas[0]["periodo"] == "2025.(3 e 4)"
    assert r.total == 2
    assert "total" not in r.colunas


async def test_filtro_pela_categoria_de_ausencia(db_engine, semear):
    _cenario(semear)
    r = _rodar(db_engine, tipo="lista", metrica="alunos", filtros=[{"campo": "renda", "valor": "Sem resposta"}])
    assert [l["matricula"] for l in r.linhas] == [B]
    assert "renda" in r.colunas
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assistente_compilador.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/assistente/compilador.py
"""ConsultaEstruturada -> SELECT do SQLAlchemy Core (spec, compilador).

Recebe só consulta já validada pelo catálogo. As regras da base moram aqui,
onde o LLM não as alcança:
- aluno se conta por matrícula distinta;
- sem a dimensão `periodo`, cada aluno entra uma vez, pela linha do período
  mais recente (o `vigente` do dashboard). O CRG de aluno_integrado é
  constante por aluno; contar por período daria peso a quem tem mais períodos;
- trajetória por semestre vem só de crg_semestre_vigente, e nulo é lacuna;
- resposta vazia é uma categoria explícita, nunca descartada.

As categorias são calculadas numa subconsulta e agrupadas por fora: agrupar
por um rótulo que tem o mesmo nome de uma coluna de entrada (polo, renda...)
faria o PostgreSQL agrupar pela coluna crua.
"""
from dataclasses import dataclass

from sqlalchemy import Integer, Select, String, asc, cast, desc, distinct, func, literal, or_, select
from sqlalchemy.orm import Session

from app.db.vigente import aluno_integrado as ai
from app.db.vigente import crg_semestre_vigente as csv
from app.schemas.assistente import ConsultaEstruturada, Filtro
from app.services.assistente.catalogo import DIMENSOES, RESPOSTAS, Dimensao
from app.services.assistente.execucao import executar_select

LIMITE_LISTA = 1000


@dataclass
class Resultado:
    colunas: list[str]
    linhas: list[dict]
    fontes: list[str]
    total: int | None = None


def _condicao(coluna, dimensao: Dimensao, filtro: Filtro):
    valores = filtro.valor if isinstance(filtro.valor, list) else [filtro.valor]
    if dimensao.id == "matricula":
        return coluna.in_([int(v) for v in valores])
    if filtro.op == "entre":
        return coluna.between(valores[0], valores[1])
    presentes = [v for v in valores if v != dimensao.ausente]
    partes = [coluna.in_(presentes)] if presentes else []
    if len(presentes) < len(valores):
        partes.append(or_(coluna.is_(None), func.trim(cast(coluna, String)) == ""))
    return or_(*partes)


def _categoria(coluna, dimensao: Dimensao):
    return func.coalesce(func.nullif(func.trim(coluna), ""), literal(dimensao.ausente)).label(dimensao.id)


def _base(consulta: ConsultaEstruturada):
    """aluno_integrado já filtrada por período; uma linha por aluno, salvo
    quando a própria dimensão é o período."""
    por_periodo = [_condicao(ai.c.periodo, DIMENSOES["periodo"], f) for f in consulta.filtros if f.campo == "periodo"]
    if "periodo" in consulta.dimensoes:
        return select(ai).where(*por_periodo).subquery("base")
    ordem = func.row_number().over(partition_by=ai.c.matricula, order_by=ai.c.periodo.desc()).label("ordem_periodo")
    recente = select(ai, ordem).where(*por_periodo).subquery("recente")
    return select(recente).where(recente.c.ordem_periodo == 1).subquery("base")


def _filtros(base, consulta: ConsultaEstruturada) -> list:
    return [_condicao(base.c[DIMENSOES[f.campo].coluna], DIMENSOES[f.campo], f)
            for f in consulta.filtros if f.campo != "periodo"]


def _ordenar(q: Select, consulta: ConsultaEstruturada, grupos: list) -> Select:
    if consulta.ordem:
        direcao = desc if consulta.ordem.direcao == "desc" else asc
        q = q.order_by(direcao(consulta.ordem.campo).nulls_last())
    else:
        q = q.order_by(*grupos)
    return q.limit(consulta.limite) if consulta.limite else q


def _agregado(consulta: ConsultaEstruturada) -> Select:
    if consulta.metrica == "crg_medio_semestre":
        return _por_semestre(consulta)
    base = _base(consulta)
    dims = [DIMENSOES[d] for d in consulta.dimensoes]
    cats = (select(base.c.matricula, base.c.CRG.label("crg"), *[_categoria(base.c[d.coluna], d) for d in dims])
            .where(*_filtros(base, consulta)).subquery("cats"))
    if consulta.metrica == "distribuicao_crg":
        faixa = cast(func.floor(cats.c.crg), Integer)
        return (select(faixa.label("faixa"), func.count().label("valor"), func.count().label("n"))
                .where(cats.c.crg.is_not(None)).group_by(faixa).order_by(faixa))
    grupos = [cats.c[d.id] for d in dims]
    if consulta.metrica == "contagem_alunos":
        valor = n = func.count(distinct(cats.c.matricula))
    else:  # crg_medio
        valor, n = func.avg(cats.c.crg), func.count(cats.c.crg)
    q = select(*grupos, valor.label("valor"), n.label("n"))
    return _ordenar(q.group_by(*grupos) if grupos else q, consulta, grupos)


def _por_semestre(consulta: ConsultaEstruturada) -> Select:
    alunos = select(ai.c.matricula, ai.c.turma, ai.c.polo_nome).distinct().subquery("alunos")
    dims = [DIMENSOES[d] for d in consulta.dimensoes if d != "semestre"]

    def coluna(campo: str):
        if campo == "semestre":
            return csv.c.semestre
        if campo == "matricula":
            return csv.c.matricula
        return alunos.c[DIMENSOES[campo].coluna]  # polo, turma

    cats = (select(csv.c.semestre, csv.c.crg, *[_categoria(alunos.c[d.coluna], d) for d in dims])
            .select_from(csv.join(alunos, alunos.c.matricula == csv.c.matricula))
            .where(*[_condicao(coluna(f.campo), DIMENSOES[f.campo], f) for f in consulta.filtros])
            .subquery("cats"))
    grupos = [cats.c.semestre, *[cats.c[d.id] for d in dims]]
    q = select(*grupos, func.avg(cats.c.crg).label("valor"), func.count(cats.c.crg).label("n")).group_by(*grupos)
    return _ordenar(q, consulta, grupos)


def _lista(consulta: ConsultaEstruturada) -> Select:
    base = _base(consulta)
    extras = list(dict.fromkeys(f.campo for f in consulta.filtros if f.campo in RESPOSTAS))
    limite = min(consulta.limite or LIMITE_LISTA, LIMITE_LISTA)
    return (select(base.c.matricula, base.c.nome, base.c.polo_nome.label("polo"), base.c.turma, base.c.periodo,
                   base.c.CRG.label("crg"), *[base.c[c] for c in extras], func.count().over().label("total"))
            .where(*_filtros(base, consulta))
            .order_by(base.c.nome.asc().nulls_last(), base.c.matricula)
            .limit(limite))


def compilar(consulta: ConsultaEstruturada) -> Select:
    if consulta.tipo == "agregado":
        return _agregado(consulta)
    if consulta.tipo == "lista" and consulta.metrica == "alunos":
        return _lista(consulta)
    raise ValueError(f"{consulta.tipo}/{consulta.metrica} não é compilado para SQL")


def fontes(consulta: ConsultaEstruturada) -> list[str]:
    if consulta.metrica == "crg_medio_semestre":
        return ["crg_semestre_vigente", "aluno_integrado"]
    return ["aluno_integrado"]


def resolver_sql(session: Session, consulta: ConsultaEstruturada) -> Resultado:
    linhas = executar_select(session, compilar(consulta))
    total = None
    if consulta.tipo == "lista":
        total = linhas[0]["total"] if linhas else 0
        for linha in linhas:
            linha.pop("total")
    for linha in linhas:
        if isinstance(linha.get("valor"), float):
            linha["valor"] = round(linha["valor"], 2)
    return Resultado(list(linhas[0]) if linhas else [], linhas, fontes(consulta), total)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assistente_compilador.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/assistente/compilador.py tests/test_assistente_compilador.py
git commit -m "feat(assistente): compilador de consultas com as regras da base"
```

---

### Task 6: Itens operacionais e listas do relatório

**Files:**
- Create: `backend/app/services/assistente/operacionais.py`
- Test: `tests/test_assistente_operacionais.py`

**Interfaces:**
- Consumes: `relatorio_do_lote` (existente); `Resultado` (Task 5); `DIMENSOES`, `ROTULOS_RESPOSTA` (Task 2); `polo_da_matricula`, `turma_da_matricula` (existentes, `app.db.matricula`).
- Produces: `FONTES_RELATORIO: list[str]`; `ultimo_lote(session) -> str | None`; `resolver_operacional(session, consulta) -> Resultado`. Linhas: `resumo_ultimo_lote` → `lote, fechado_em, registros_lidos, registros_aceitos, integrados, nao_integrados`; `campos_sem_resposta` → `campo, valor, n`; `alunos_incompletos` → `matricula, nome, polo, turma, campos_sem_resposta, preenchimento`; `nao_integrados` → `matricula, nome, motivo, detalhe`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assistente_operacionais.py
"""Operacionais: os mesmos números da tela /dados (relatorio_do_lote)."""
from sqlalchemy.orm import Session

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.operacionais import resolver_operacional
from app.services.relatorio import CAMPOS_SOCIOECONOMICOS
from conftest import historico, zip_de

COMPLETO = {campo: "x" for campo in CAMPOS_SOCIOECONOMICOS} | {"pcd": "Não", "tipo_deficiencia": None}
INTEGRADO, INCOMPLETO, SO_SOCIO, SO_HIST = 202016040001, 202016040002, 202185940003, 202216040004


async def _importar(importar, fontes) -> str:
    fontes.fasitech = [
        {"matricula": INTEGRADO, "periodo": "2026.1", **COMPLETO},
        {"matricula": INCOMPLETO, "periodo": "2026.1", "genero": "Feminino"},
        {"matricula": SO_SOCIO, "periodo": "2026.1", "genero": "Masculino"},
    ]
    fontes.historicos = {"h1": historico(INTEGRADO, {"2025.1": 8.0}, nome="Um"),
                         "h2": historico(INCOMPLETO, {"2025.1": 7.0}, nome="Dois"),
                         "h4": historico(SO_HIST, {"2025.1": 6.0}, nome="Quatro")}
    resposta = await importar(zip_de(["h1.pdf", "h2.pdf", "h4.pdf"]))
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()["id"]


def _rodar(db_engine, **consulta):
    with Session(db_engine) as s:
        return resolver_operacional(s, ConsultaEstruturada(**consulta))


async def test_nao_integrados_por_motivo(db_engine, importar, fontes):
    await _importar(importar, fontes)
    sem_socio = _rodar(db_engine, tipo="lista", metrica="nao_integrados",
                       filtros=[{"campo": "motivo", "valor": "sem_socioeconomico"}])
    assert [l["matricula"] for l in sem_socio.linhas] == [SO_HIST]
    todos = _rodar(db_engine, tipo="lista", metrica="nao_integrados")
    assert {l["matricula"] for l in todos.linhas} == {SO_HIST, SO_SOCIO}


async def test_incompletos_com_polo_e_turma_da_matricula(db_engine, importar, fontes):
    await _importar(importar, fontes)
    r = _rodar(db_engine, tipo="lista", metrica="alunos_incompletos")
    assert [(l["matricula"], l["polo"], l["turma"]) for l in r.linhas] == [(INCOMPLETO, "Cametá", "2020")]
    vazio = _rodar(db_engine, tipo="lista", metrica="alunos_incompletos", filtros=[{"campo": "polo", "valor": "Oeiras"}])
    assert vazio.linhas == []


async def test_campos_sem_resposta_bate_com_o_relatorio(client, db_engine, importar, fontes):
    lote = await _importar(importar, fontes)
    r = _rodar(db_engine, tipo="operacional", metrica="campos_sem_resposta")
    relatorio = (await client.get(f"/lotes/{lote}/relatorio")).json()
    total = sum(l["qtd_campos_sem_resposta"] for l in relatorio["integrados"])
    assert sum(l["valor"] for l in r.linhas) == total
    assert {l["n"] for l in r.linhas} == {len(relatorio["integrados"])}


async def test_resumo_do_ultimo_lote(db_engine, importar, fontes):
    lote = await _importar(importar, fontes)
    [linha] = _rodar(db_engine, tipo="operacional", metrica="resumo_ultimo_lote").linhas
    assert (linha["lote"], linha["integrados"], linha["nao_integrados"]) == (lote, 2, 2)


async def test_sem_lote_nenhum_devolve_vazio(db_engine):
    r = _rodar(db_engine, tipo="operacional", metrica="resumo_ultimo_lote")
    assert (r.linhas, r.total) == ([], 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assistente_operacionais.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/assistente/operacionais.py
"""Itens operacionais e listas de relatório. Reaproveitam relatorio_do_lote
para os números saírem iguais aos da tela /dados. Rodam como o dono, não como
leitor_assistente: é código fixo, sem SQL derivado da pergunta."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.engine import Ingestao, Lote
from app.db.matricula import polo_da_matricula, turma_da_matricula
from app.schemas.assistente import ConsultaEstruturada, Filtro
from app.services.assistente.catalogo import DIMENSOES, ROTULOS_RESPOSTA
from app.services.assistente.compilador import Resultado
from app.services.relatorio import relatorio_do_lote

FONTES_RELATORIO = ["usuarios", "crg_semestre", "historico", "excecao", "lote", "ingestao"]


def ultimo_lote(session: Session) -> str | None:
    """O lote da ingestão mais recente: o que a tela /dados mostra como vigente."""
    return session.execute(select(Ingestao.lote_id).order_by(Ingestao.id.desc()).limit(1)).scalar()


def _passa(filtros: list[Filtro], campo: str, valor) -> bool:
    for f in filtros:
        if f.campo != campo:
            continue
        valores = f.valor if isinstance(f.valor, list) else [f.valor]
        ok = valores[0] <= valor <= valores[1] if f.op == "entre" else valor in valores
        if not ok:
            return False
    return True


def _resultado(linhas: list[dict]) -> Resultado:
    return Resultado(list(linhas[0]) if linhas else [], linhas, FONTES_RELATORIO, len(linhas))


def resolver_operacional(session: Session, consulta: ConsultaEstruturada) -> Resultado:
    lote_id = ultimo_lote(session)
    if lote_id is None:
        return Resultado([], [], FONTES_RELATORIO, 0)
    relatorio = relatorio_do_lote(session, lote_id)
    metrica = consulta.metrica
    if metrica == "resumo_ultimo_lote":
        return _resumo(session, lote_id, relatorio)
    if metrica == "campos_sem_resposta":
        return _campos(relatorio)
    if metrica == "alunos_incompletos":
        return _incompletos(relatorio, consulta)
    if metrica == "nao_integrados":
        return _resultado([
            {"matricula": l["matricula"], "nome": l["nome"], "motivo": l["motivo_descricao"], "detalhe": l["detalhe"]}
            for l in relatorio["nao_integrados"] if _passa(consulta.filtros, "motivo", l["motivo"])
        ])
    raise ValueError(f"{metrica} não é operacional")


def _resumo(session: Session, lote_id: str, relatorio: dict) -> Resultado:
    lote = session.get(Lote, lote_id)
    lidos, aceitos = session.execute(
        select(func.coalesce(func.sum(Ingestao.registros_lidos), 0), func.coalesce(func.sum(Ingestao.registros_aceitos), 0))
        .where(Ingestao.lote_id == lote_id)
    ).one()
    resumo = relatorio["resumo"]
    return _resultado([{
        "lote": lote_id, "fechado_em": lote.fechado_em.isoformat() if lote.fechado_em else None,
        "registros_lidos": lidos, "registros_aceitos": aceitos,
        "integrados": resumo["integrados"], "nao_integrados": resumo["nao_integrados"],
    }])


def _campos(relatorio: dict) -> Resultado:
    integrados = relatorio["integrados"]
    contagem: dict[str, int] = {}
    for linha in integrados:
        for campo in linha["campos_sem_resposta"]:
            contagem[campo] = contagem.get(campo, 0) + 1
    ordem = sorted(contagem.items(), key=lambda item: (-item[1], item[0]))
    return _resultado([{"campo": ROTULOS_RESPOSTA.get(c, c), "valor": q, "n": len(integrados)} for c, q in ordem])


def _incompletos(relatorio: dict, consulta: ConsultaEstruturada) -> Resultado:
    linhas = []
    for l in relatorio["integrados"]:
        if not l["qtd_campos_sem_resposta"]:
            continue
        polo = polo_da_matricula(l["matricula"]) or DIMENSOES["polo"].ausente
        turma = turma_da_matricula(l["matricula"]) or DIMENSOES["turma"].ausente
        if not (_passa(consulta.filtros, "polo", polo) and _passa(consulta.filtros, "turma", turma)):
            continue
        linhas.append({
            "matricula": l["matricula"], "nome": l["nome"], "polo": polo, "turma": turma,
            "campos_sem_resposta": ", ".join(ROTULOS_RESPOSTA.get(c, c) for c in l["campos_sem_resposta"]),
            "preenchimento": l["percentual_preenchimento"],
        })
    return _resultado(linhas)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assistente_operacionais.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/assistente/operacionais.py tests/test_assistente_operacionais.py
git commit -m "feat(assistente): itens operacionais sobre o relatório do lote"
```

---

### Task 7: Planejador, visualização e respostas

**Files:**
- Modify: `backend/app/services/assistente/catalogo.py` (acrescenta dashboards ao fim)
- Create: `backend/app/services/assistente/planejador.py`
- Create: `backend/app/services/assistente/visualizacao.py`
- Create: `backend/app/services/assistente/respostas.py`
- Test: `tests/test_assistente_planejamento.py`

**Interfaces:**
- Consumes: `METRICAS`, `DIMENSOES`, `ROTULOS_RESPOSTA` (Task 2); `Resultado` (Task 5).
- Produces: `Dashboard(id, rotulo, tipo, metricas, dimensoes, obrigatorios, opcionais, param_dimensao)`, `DASHBOARDS` (em catalogo); `Plano(forma, dashboard)`, `planejar(consulta) -> Plano`, `params_do_dashboard(dashboard, consulta) -> dict[str, str]`; `chave_renda(valor) -> float`, `titulo_de(consulta) -> str`, `montar_dinamico(consulta, resultado) -> BlocoDinamico`; `SUGESTOES`, `filtros_aplicados(consulta) -> list[FiltroAplicado]`, `descrever(consulta) -> str`, `texto_para(consulta, resultado) -> BlocoTexto`, `tabela_para(resultado) -> BlocoTabela`, `nao_entendi(motivo) -> BlocoNaoEntendi`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assistente_planejamento.py
"""Regras determinísticas: forma da resposta, gráfico e textos."""
import pytest

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.compilador import Resultado
from app.services.assistente.planejador import params_do_dashboard, planejar
from app.services.assistente.respostas import descrever, filtros_aplicados, tabela_para, texto_para
from app.services.assistente.visualizacao import chave_renda, montar_dinamico


def _c(**campos):
    return ConsultaEstruturada(**campos)


# Os casos de aceitação do spec, já como ConsultaEstruturada.
CASOS = [
    ("Quantos alunos existem por polo?", _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"]), "dashboard", "polos"),
    ("Mostre os alunos do polo de Cametá", _c(tipo="lista", metrica="alunos", filtros=[{"campo": "polo", "valor": "Cametá"}]), "dashboard", "turmas"),
    ("Evolução por semestre", _c(tipo="agregado", metrica="crg_medio_semestre", dimensoes=["semestre"]), "dashboard", "longitudinal"),
    ("Distribuição de renda", _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]), "dinamico", None),
    ("Compare renda por polo", _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo", "renda"]), "dinamico", None),
    ("Campos com mais ausentes", _c(tipo="operacional", metrica="campos_sem_resposta"), "dinamico", None),
    ("Ingressaram em 2020", _c(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "turma", "valor": "2020"}]), "texto", None),
    ("Registros do último lote", _c(tipo="operacional", metrica="resumo_ultimo_lote"), "texto", None),
    ("Alunos com dados incompletos", _c(tipo="lista", metrica="alunos_incompletos"), "tabela", None),
    ("Sem socioeconômico", _c(tipo="lista", metrica="nao_integrados", filtros=[{"campo": "motivo", "valor": "sem_socioeconomico"}]), "tabela", None),
    ("Polos com maior evasão", _c(tipo="fora_do_catalogo", interpretacao="Não há dado de evasão."), "nao_entendi", None),
]


@pytest.mark.parametrize("pergunta,consulta,forma,dashboard", CASOS, ids=[c[0] for c in CASOS])
def test_casos_de_aceitacao(pergunta, consulta, forma, dashboard):
    plano = planejar(consulta)
    assert plano.forma == forma
    assert (plano.dashboard.id if plano.dashboard else None) == dashboard


def test_params_do_dashboard_levam_filtros_e_dimensao():
    c = _c(tipo="agregado", metrica="crg_medio", dimensoes=["renda"], filtros=[{"campo": "polo", "valor": "Cametá"}])
    plano = planejar(c)
    assert plano.dashboard.id == "bidimensional"
    assert params_do_dashboard(plano.dashboard, c) == {"polo": "Cametá", "dimensao": "renda"}


def test_filtro_que_o_dashboard_nao_tem_vira_dinamico():
    c = _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"], filtros=[{"campo": "renda", "valor": "x"}])
    assert planejar(c).forma == "dinamico"


def test_lista_com_filtro_fora_do_dashboard_vira_tabela():
    c = _c(tipo="lista", metrica="alunos", filtros=[{"campo": "polo", "valor": "Cametá"}, {"campo": "renda", "valor": "x"}])
    assert planejar(c).forma == "tabela"


# --- visualização --------------------------------------------------------

def _res(linhas):
    return Resultado(list(linhas[0]) if linhas else [], linhas, ["aluno_integrado"])


def test_ordem_natural_da_renda():
    rendas = ["Sem resposta", "Acima de 3 salários mínimos", "De 1 a 2 salários mínimos", "Até 1 salário mínimo"]
    assert sorted(rendas, key=chave_renda) == [
        "Até 1 salário mínimo", "De 1 a 2 salários mínimos", "Acima de 3 salários mínimos", "Sem resposta"]


def test_sem_dimensao_vira_kpi():
    bloco = montar_dinamico(_c(tipo="agregado", metrica="crg_medio"), _res([{"valor": 7.0, "n": 2}]))
    assert (bloco.kpis[0].valor, bloco.kpis[0].n, bloco.graficos) == (7.0, 2, [])


def test_distribuicao_do_crg_vira_histograma():
    g = montar_dinamico(_c(tipo="agregado", metrica="distribuicao_crg"), _res([{"faixa": 6, "valor": 1, "n": 1}])).graficos[0]
    assert (g.tipo, g.eixo) == ("histograma", "faixa")


def test_semestre_vira_linha_cronologica_com_nulo_preservado():
    linhas = [{"semestre": "2025.1", "valor": 7.0, "n": 2}, {"semestre": "2024.2", "valor": None, "n": 0}]
    g = montar_dinamico(_c(tipo="agregado", metrica="crg_medio_semestre", dimensoes=["semestre"]), _res(linhas)).graficos[0]
    assert g.tipo == "linha"
    assert [(d["semestre"], d["valor"]) for d in g.dados] == [("2024.2", None), ("2025.1", 7.0)]


def test_semestre_e_turma_vira_uma_linha_por_turma():
    linhas = [{"semestre": "2025.1", "turma": "2021", "valor": 7.0, "n": 1},
              {"semestre": "2025.1", "turma": "2020", "valor": 6.0, "n": 1}]
    g = montar_dinamico(_c(tipo="agregado", metrica="crg_medio_semestre", dimensoes=["semestre", "turma"]), _res(linhas)).graficos[0]
    assert (g.tipo, g.eixo, g.serie, g.series, g.serie_ordinal) == ("linha", "semestre", "turma", ["2020", "2021"], True)


def test_duas_dimensoes_de_contagem_viram_barras_empilhadas_100():
    linhas = [{"polo": "Cametá", "renda": "Sem resposta", "valor": 1, "n": 1},
              {"polo": "Cametá", "renda": "Até 1 salário mínimo", "valor": 3, "n": 3},
              {"polo": "Oeiras", "renda": "Até 1 salário mínimo", "valor": 1, "n": 1}]
    g = montar_dinamico(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo", "renda"]), _res(linhas)).graficos[0]
    assert g.tipo == "barras_empilhadas"
    assert g.series == ["Até 1 salário mínimo", "Sem resposta"]
    assert sum(d["percentual"] for d in g.dados if d["polo"] == "Cametá") == 100.0


def test_duas_dimensoes_de_media_viram_barras_agrupadas():
    linhas = [{"polo": "Cametá", "genero": "Feminino", "valor": 7.0, "n": 2}]
    g = montar_dinamico(_c(tipo="agregado", metrica="crg_medio", dimensoes=["polo", "genero"]), _res(linhas)).graficos[0]
    assert g.tipo == "barras_agrupadas"


def test_poucas_categorias_nominais_viram_rosca_com_percentual():
    linhas = [{"genero": "Feminino", "valor": 3, "n": 3}, {"genero": "Masculino", "valor": 1, "n": 1}]
    g = montar_dinamico(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["genero"]), _res(linhas)).graficos[0]
    assert g.tipo == "rosca"
    assert [d["percentual"] for d in g.dados] == [75.0, 25.0]


def test_ordinal_vira_barras_na_ordem_natural_mesmo_com_poucas_categorias():
    linhas = [{"renda": "De 1 a 2 salários mínimos", "valor": 5, "n": 5}, {"renda": "Até 1 salário mínimo", "valor": 1, "n": 1}]
    g = montar_dinamico(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]), _res(linhas)).graficos[0]
    assert g.tipo == "barras"
    assert [d["renda"] for d in g.dados] == ["Até 1 salário mínimo", "De 1 a 2 salários mínimos"]


def test_nominal_com_muitas_categorias_vira_barras_por_valor_com_ausencia_no_fim():
    nomes = ["A", "B", "C", "D", "E"]
    linhas = [{"cor_etnia": n, "valor": i + 1, "n": i + 1} for i, n in enumerate(nomes)] + [
        {"cor_etnia": "Sem resposta", "valor": 99, "n": 99}]
    g = montar_dinamico(_c(tipo="agregado", metrica="contagem_alunos", dimensoes=["cor_etnia"]), _res(linhas)).graficos[0]
    assert g.tipo == "barras"
    assert [d["cor_etnia"] for d in g.dados] == ["E", "D", "C", "B", "A", "Sem resposta"]


# --- respostas -----------------------------------------------------------

def test_filtros_aplicados_e_descricao():
    c = _c(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"],
           filtros=[{"campo": "turma", "op": "entre", "valor": ["2020", "2022"]},
                    {"campo": "renda", "op": "in", "valor": ["A", "B"]}])
    assert [(f.rotulo, f.valor) for f in filtros_aplicados(c)] == [("Turma", "2020 a 2022"), ("Renda familiar", "A, B")]
    assert descrever(c) == "Contagem de alunos por Polo com Turma: 2020 a 2022, Renda familiar: A, B"


def test_textos():
    turma = [{"campo": "turma", "valor": "2020"}]
    assert texto_para(_c(tipo="agregado", metrica="contagem_alunos", filtros=turma),
                      _res([{"valor": 2, "n": 2}])).mensagem == "2 aluno(s) integrado(s) com Turma: 2020."
    assert texto_para(_c(tipo="agregado", metrica="contagem_alunos"),
                      _res([{"valor": 0, "n": 0}])).mensagem == "Nenhum aluno com esses filtros."
    assert texto_para(_c(tipo="agregado", metrica="crg_medio"),
                      _res([{"valor": 7.0, "n": 2}])).mensagem == "CRG médio de 7,00, sobre 2 aluno(s) com CRG apurado."
    assert texto_para(_c(tipo="operacional", metrica="resumo_ultimo_lote"), _res([])).mensagem == "Nenhum lote importado ainda."
    resumo = {"lote": "2026-09-L02", "fechado_em": None, "registros_lidos": 10, "registros_aceitos": 9,
              "integrados": 7, "nao_integrados": 3}
    assert texto_para(_c(tipo="operacional", metrica="resumo_ultimo_lote"), _res([resumo])).mensagem == (
        "No lote 2026-09-L02 foram lidos 10 registros e aceitos 9. Na base consolidada até ele, "
        "7 aluno(s) estão integrados e 3 não integrados.")


def test_tabela_rotula_as_colunas():
    t = tabela_para(Resultado(["matricula", "renda"], [{"matricula": 1, "renda": "x"}], ["aluno_integrado"], 1))
    assert [(c.id, c.rotulo) for c in t.colunas] == [("matricula", "Matrícula"), ("renda", "Renda familiar")]
    assert t.total == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assistente_planejamento.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.assistente.planejador'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/services/assistente/catalogo.py`:

```python


@dataclass(frozen=True)
class Dashboard:
    """Um dashboard existente e as consultas que ele já responde. A rota fica no
    front (domain/catalogoDashboards.ts): aqui só o id e os parâmetros."""
    id: str
    rotulo: str
    tipo: str
    metricas: frozenset[str]
    dimensoes: tuple[frozenset[str], ...]  # conjuntos de dimensões aceitos
    obrigatorios: frozenset[str] = frozenset()
    opcionais: frozenset[str] = frozenset()
    param_dimensao: str | None = None  # parâmetro de URL que recebe a dimensão


_CONTAGEM_OU_CRG = frozenset({"contagem_alunos", "crg_medio"})
_PERIODO = frozenset({"periodo"})
_SEM_DIMENSAO = (frozenset(),)

# A ordem importa: o primeiro que casa ganha (contagem por polo -> Polos, não Bidimensional).
DASHBOARDS = (
    Dashboard("polos", "Visão Geral dos Polos", "agregado", _CONTAGEM_OU_CRG, (frozenset({"polo"}),), opcionais=_PERIODO),
    Dashboard("turmas", "Turmas do polo", "agregado", _CONTAGEM_OU_CRG, (frozenset({"turma"}),),
              obrigatorios=frozenset({"polo"}), opcionais=_PERIODO),
    Dashboard("turmas", "Turmas do polo", "lista", frozenset({"alunos"}), _SEM_DIMENSAO,
              obrigatorios=frozenset({"polo"}), opcionais=_PERIODO),
    Dashboard("alunos_turma", "Alunos da turma", "lista", frozenset({"alunos"}), _SEM_DIMENSAO,
              obrigatorios=frozenset({"polo", "turma"}), opcionais=_PERIODO),
    Dashboard("perfil", "Perfil do aluno", "lista", frozenset({"alunos"}), _SEM_DIMENSAO,
              obrigatorios=frozenset({"matricula"})),
    # Os eixos que a tela Bidimensional oferece (domain/analises.ts, EIXOS_X).
    Dashboard("bidimensional", "Análise Bidimensional", "agregado", frozenset({"crg_medio"}),
              tuple(frozenset({e}) for e in ("cor_etnia", "genero", "renda", "trabalho", "polo", "turma")),
              opcionais=frozenset({"polo", "periodo"}), param_dimensao="dimensao"),
    Dashboard("distribuicao", "Distribuição do CRG", "agregado", frozenset({"distribuicao_crg"}), _SEM_DIMENSAO,
              opcionais=frozenset({"polo", "periodo"})),
    # O longitudinal não segue o filtro de período: o eixo é o semestre letivo.
    Dashboard("longitudinal", "Análise Longitudinal", "agregado", frozenset({"crg_medio_semestre"}),
              (frozenset({"semestre"}), frozenset({"semestre", "turma"})), opcionais=frozenset({"polo", "turma"})),
)
```

```python
# backend/app/services/assistente/planejador.py
"""Decide a forma da resposta (spec, planejador). Regras, nesta ordem:
fora do catálogo -> não entendi; cabe num dashboard -> dashboard; lista ->
tabela; um número só -> texto; o resto -> dashboard dinâmico."""
from dataclasses import dataclass

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.catalogo import DASHBOARDS, Dashboard


@dataclass(frozen=True)
class Plano:
    forma: str
    dashboard: Dashboard | None = None


def _dashboard_para(consulta: ConsultaEstruturada) -> Dashboard | None:
    if consulta.ordem is not None or consulta.limite is not None:
        return None  # dashboard não ordena nem corta: a pergunta pede um ranking
    campos = [f.campo for f in consulta.filtros]
    if len(set(campos)) != len(campos) or any(f.op != "=" for f in consulta.filtros):
        return None  # a URL das telas leva um valor por filtro
    for d in DASHBOARDS:
        if (consulta.tipo == d.tipo and consulta.metrica in d.metricas
                and frozenset(consulta.dimensoes) in d.dimensoes
                and d.obrigatorios <= set(campos) <= d.obrigatorios | d.opcionais):
            return d
    return None


def planejar(consulta: ConsultaEstruturada) -> Plano:
    if consulta.tipo == "fora_do_catalogo":
        return Plano("nao_entendi")
    dashboard = _dashboard_para(consulta)
    if dashboard:
        return Plano("dashboard", dashboard)
    if consulta.tipo == "lista":
        return Plano("tabela")
    if consulta.metrica == "resumo_ultimo_lote":
        return Plano("texto")
    if consulta.tipo == "agregado" and not consulta.dimensoes and consulta.metrica != "distribuicao_crg":
        return Plano("texto")
    return Plano("dinamico")


def params_do_dashboard(dashboard: Dashboard, consulta: ConsultaEstruturada) -> dict[str, str]:
    params = {f.campo: str(f.valor) for f in consulta.filtros}
    if dashboard.param_dimensao:
        params[dashboard.param_dimensao] = consulta.dimensoes[0]
    return params
```

```python
# backend/app/services/assistente/visualizacao.py
"""Escolhe o gráfico pela forma do resultado (spec, Regras de visualização).
Determinístico: a mesma consulta dá sempre o mesmo gráfico."""
import re

from app.schemas.assistente import BlocoDinamico, ConsultaEstruturada, Grafico, Kpi
from app.services.assistente.catalogo import DIMENSOES, METRICAS
from app.services.assistente.compilador import Resultado

MAX_FATIAS_ROSCA = 5
ROTULO_VALOR = {
    "contagem_alunos": "Alunos", "crg_medio": "CRG médio", "crg_medio_semestre": "CRG médio",
    "distribuicao_crg": "Alunos", "campos_sem_resposta": "Alunos sem resposta",
}


def chave_renda(valor: str) -> float:
    """Ordem natural das faixas: 'Até 1' < 'De 1 a 2' < 'Acima de 3'; sem número no fim."""
    texto = str(valor).lower()
    achado = re.search(r"\d+(?:[.,]\d+)?", texto)
    if not achado:
        return float("inf")
    numero = float(achado.group().replace(",", "."))
    if texto.startswith("até"):
        return numero - 0.5
    if texto.startswith(("acima", "mais de")):
        return numero + 0.5
    return numero


def _eh_ordinal(dimensao: str | None) -> bool:
    return bool(dimensao) and dimensao in DIMENSOES and DIMENSOES[dimensao].ordinal


def _chave(dimensao: str | None):
    """Chave de ordenação de uma categoria: ausência ('Sem ...') sempre no fim."""
    if dimensao == "renda":
        return lambda v: (chave_renda(v), str(v))
    return lambda v: (str(v).startswith("Sem "), str(v))


def _ordenar(linhas: list[dict], eixo: str, serie: str | None) -> list[dict]:
    chave_serie = _chave(serie)

    def pela_serie(linha):
        return chave_serie(linha[serie]) if serie else (False, "")

    if _eh_ordinal(eixo):
        chave_eixo = _chave(eixo)
        return sorted(linhas, key=lambda l: (chave_eixo(l[eixo]), pela_serie(l)))
    totais: dict = {}
    for l in linhas:
        totais[l[eixo]] = totais.get(l[eixo], 0) + (l["valor"] or 0)
    return sorted(linhas, key=lambda l: (str(l[eixo]).startswith("Sem "), -totais[l[eixo]], str(l[eixo]), pela_serie(l)))


def _com_percentual(linhas: list[dict], eixo: str | None) -> list[dict]:
    totais: dict = {}
    for l in linhas:
        k = l[eixo] if eixo else None
        totais[k] = totais.get(k, 0) + (l["valor"] or 0)
    return [{**l, "percentual": round(100 * (l["valor"] or 0) / totais[l[eixo] if eixo else None], 1)
             if totais[l[eixo] if eixo else None] else None} for l in linhas]


def titulo_de(consulta: ConsultaEstruturada) -> str:
    titulo = METRICAS[consulta.metrica].rotulo
    if consulta.dimensoes:
        titulo += " por " + " e ".join(DIMENSOES[d].rotulo for d in consulta.dimensoes)
    return titulo


def montar_dinamico(consulta: ConsultaEstruturada, resultado: Resultado) -> BlocoDinamico:
    metrica, linhas = consulta.metrica, resultado.linhas
    rotulo, titulo = ROTULO_VALOR[metrica], titulo_de(consulta)
    ordenar = (lambda ls, e, s: ls) if consulta.ordem else _ordenar  # ranking pedido: vale a ordem do SQL

    def grafico(tipo: str, eixo: str, dados: list[dict], serie: str | None = None) -> BlocoDinamico:
        series = sorted({str(d[serie]) for d in dados}, key=_chave(serie)) if serie else []
        return BlocoDinamico(graficos=[Grafico(
            tipo=tipo, titulo=titulo, eixo=eixo, serie=serie, series=series,
            serie_ordinal=_eh_ordinal(serie), rotulo_valor=rotulo, dados=dados)])

    if metrica == "distribuicao_crg":
        return grafico("histograma", "faixa", linhas)
    if metrica == "campos_sem_resposta":
        return grafico("barras", "campo", linhas)
    dims = list(consulta.dimensoes)
    if not dims:
        return BlocoDinamico(kpis=[Kpi(rotulo=rotulo, valor=linhas[0]["valor"], n=linhas[0]["n"])])
    temporais = [d for d in dims if DIMENSOES[d].temporal]
    if temporais:
        eixo = temporais[0]
        serie = next((d for d in dims if d != eixo), None)
        return grafico("linha", eixo, ordenar(linhas, eixo, serie), serie)
    if len(dims) == 2:
        eixo, serie = dims
        if metrica == "contagem_alunos":
            return grafico("barras_empilhadas", eixo, ordenar(_com_percentual(linhas, eixo), eixo, serie), serie)
        return grafico("barras_agrupadas", eixo, ordenar(linhas, eixo, serie), serie)
    eixo = dims[0]
    if metrica == "contagem_alunos" and not _eh_ordinal(eixo) and len(linhas) <= MAX_FATIAS_ROSCA:
        return grafico("rosca", eixo, ordenar(_com_percentual(linhas, None), eixo, None))
    return grafico("barras", eixo, ordenar(linhas, eixo, None))
```

```python
# backend/app/services/assistente/respostas.py
"""Tudo o que o usuário lê: explicação, textos, tabela, 'não entendi'.
Texto sai de template preenchido com o resultado; o resultado nunca volta ao LLM."""
from app.schemas.assistente import (BlocoNaoEntendi, BlocoTabela, BlocoTexto, Coluna, ConsultaEstruturada,
                                    FiltroAplicado)
from app.services.assistente.catalogo import DIMENSOES, METRICAS, ROTULOS_RESPOSTA
from app.services.assistente.compilador import Resultado

SUGESTOES = [
    "Quantos alunos existem por polo?",
    "Qual a distribuição de renda familiar dos alunos?",
    "Compare renda familiar por polo",
    "Mostre a evolução do CRG por semestre",
    "Liste os alunos com dados incompletos",
]
ROTULOS_COLUNA = {
    "matricula": "Matrícula", "nome": "Nome", "polo": "Polo", "turma": "Turma", "periodo": "Período",
    "crg": "CRG", "campos_sem_resposta": "Campos sem resposta", "preenchimento": "% preenchido",
    "motivo": "Motivo", "detalhe": "Detalhe", **ROTULOS_RESPOSTA,
}


def _num(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def filtros_aplicados(consulta: ConsultaEstruturada) -> list[FiltroAplicado]:
    aplicados = []
    for f in consulta.filtros:
        valores = [str(v) for v in (f.valor if isinstance(f.valor, list) else [f.valor])]
        texto = f"{valores[0]} a {valores[1]}" if f.op == "entre" else ", ".join(valores)
        aplicados.append(FiltroAplicado(rotulo=DIMENSOES[f.campo].rotulo, valor=texto))
    return aplicados


def _sufixo(consulta: ConsultaEstruturada) -> str:
    aplicados = filtros_aplicados(consulta)
    return " com " + ", ".join(f"{f.rotulo}: {f.valor}" for f in aplicados) if aplicados else ""


def descrever(consulta: ConsultaEstruturada) -> str:
    """O que foi executado, descrito a partir da consulta, e não da paráfrase do LLM."""
    if consulta.tipo == "fora_do_catalogo":
        return consulta.interpretacao or "Pergunta fora do que o assistente sabe consultar."
    texto = METRICAS[consulta.metrica].rotulo
    if consulta.dimensoes:
        texto += " por " + " e ".join(DIMENSOES[d].rotulo for d in consulta.dimensoes)
    return texto + _sufixo(consulta)


def texto_para(consulta: ConsultaEstruturada, resultado: Resultado) -> BlocoTexto:
    if not resultado.linhas:
        vazio = "Nenhum lote importado ainda." if consulta.tipo == "operacional" else "Nenhum aluno com esses filtros."
        return BlocoTexto(mensagem=vazio)
    linha = resultado.linhas[0]
    if consulta.metrica == "resumo_ultimo_lote":
        return BlocoTexto(
            mensagem=(f"No lote {linha['lote']} foram lidos {linha['registros_lidos']} registros e aceitos "
                      f"{linha['registros_aceitos']}. Na base consolidada até ele, {linha['integrados']} aluno(s) "
                      f"estão integrados e {linha['nao_integrados']} não integrados."),
            valor=linha["integrados"])
    sufixo = _sufixo(consulta)
    if consulta.metrica == "contagem_alunos":
        if not linha["valor"]:
            return BlocoTexto(mensagem="Nenhum aluno com esses filtros.", valor=0, n=0)
        return BlocoTexto(mensagem=f"{linha['valor']} aluno(s) integrado(s){sufixo}.", valor=linha["valor"], n=linha["n"])
    if linha["valor"] is None:
        return BlocoTexto(mensagem=f"Nenhum aluno com CRG apurado{sufixo}.", n=0)
    return BlocoTexto(mensagem=f"CRG médio de {_num(linha['valor'])}{sufixo}, sobre {linha['n']} aluno(s) com CRG apurado.",
                      valor=linha["valor"], n=linha["n"])


def tabela_para(resultado: Resultado) -> BlocoTabela:
    colunas = [Coluna(id=c, rotulo=ROTULOS_COLUNA.get(c, c)) for c in resultado.colunas]
    total = resultado.total if resultado.total is not None else len(resultado.linhas)
    return BlocoTabela(colunas=colunas, linhas=resultado.linhas, total=total)


def nao_entendi(motivo: str) -> BlocoNaoEntendi:
    return BlocoNaoEntendi(motivo=motivo, sugestoes=SUGESTOES)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assistente_planejamento.py -v`
Expected: 27 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/assistente/catalogo.py backend/app/services/assistente/planejador.py backend/app/services/assistente/visualizacao.py backend/app/services/assistente/respostas.py tests/test_assistente_planejamento.py
git commit -m "feat(assistente): planejador, regras de visualização e textos de resposta"
```

---

### Task 8: Intenção, pipeline e API

**Files:**
- Create: `backend/app/services/assistente/intencao.py`
- Create: `backend/app/services/assistente/pipeline.py`
- Create: `backend/app/api/assistente.py`
- Modify: `backend/app/main.py` (import + `include_router`)
- Modify: `tests/conftest.py` (acrescenta `ProvedorFalso` e fixture `llm`)
- Test: `tests/test_assistente_api.py`

**Interfaces:**
- Consumes: tudo das Tasks 1–7.
- Produces: `montar_mensagens(pergunta, valores) -> list[dict]`; `interpretar(provedor, pergunta, valores) -> ConsultaEstruturada | None`; `pipeline.perguntar(session, provedor, pergunta) -> RespostaAssistente`; `pipeline.executar(session, consulta) -> RespostaAssistente`; `pipeline.resolver(session, consulta) -> Resultado`; `api.assistente.obter_provedor() -> ProvedorLLM`; rotas `POST /assistente/perguntar` (`PerguntaIn`) e `POST /assistente/executar` (`ExecutarIn`).

- [ ] **Step 1: Write the failing test**

Append to `tests/conftest.py`:

```python


# ---------------------------------------------------------------------------
# Assistente: LLM falsificado. Nenhum teste da suíte padrão chama o Groq.
# ---------------------------------------------------------------------------

class ProvedorFalso:
    """Devolve `respostas` em ordem (texto, ou exceção a levantar) e guarda em
    `chamadas` cada lista de mensagens recebida -- é por ela que os testes
    conferem o que sairia da máquina."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas: list[list[dict]] = []

    def completar(self, mensagens):
        self.chamadas.append(mensagens)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


@pytest.fixture()
def llm(client):
    """O provedor falso no lugar do Groq; `llm.respostas.append(...)` define o que ele diz."""
    from app.api.assistente import obter_provedor

    falso = ProvedorFalso()
    app.dependency_overrides[obter_provedor] = lambda: falso
    return falso
```

```python
# tests/test_assistente_api.py
"""POST /assistente/perguntar e /executar, com o LLM falsificado."""
import json

from app.services.assistente import pipeline
from app.services.assistente.execucao import ConsultaDemorada
from app.services.assistente.provedor_llm import LLMIndisponivel

A, B = 202016040001, 202016040002


def _json(**consulta):
    return json.dumps(consulta, ensure_ascii=False)


async def _perguntar(client, pergunta="pergunta"):
    return await client.post("/assistente/perguntar", json={"pergunta": pergunta})


async def test_forma_dashboard_nao_executa_e_explica(client, llm):
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"]))
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "dashboard"
    assert corpo["dashboard"] == {"id": "polos", "params": {}}
    assert corpo["explicacao"] == {"consulta_interpretada": "Contagem de alunos por Polo", "filtros_aplicados": [],
                                   "fontes": ["aluno_integrado"], "forma": "dashboard"}


async def test_forma_texto(client, llm, semear):
    semear(A)
    semear(B)
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", filtros=[{"campo": "turma", "valor": "2020"}]))
    corpo = (await _perguntar(client, "Quantos alunos ingressaram em 2020?")).json()
    assert corpo["forma"] == "texto"
    assert corpo["texto"]["mensagem"] == "2 aluno(s) integrado(s) com Turma: 2020."


async def test_forma_tabela(client, llm, semear):
    semear(A, renda="Até 1 salário mínimo")
    semear(B)
    llm.respostas.append(_json(tipo="lista", metrica="alunos", filtros=[{"campo": "renda", "valor": "até 1 salário mínimo"}]))
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "tabela"
    assert corpo["tabela"]["total"] == 1
    assert corpo["explicacao"]["filtros_aplicados"] == [{"rotulo": "Renda familiar", "valor": "Até 1 salário mínimo"}]


async def test_forma_dinamica(client, llm, semear):
    semear(A, renda="Até 1 salário mínimo")
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]))
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "dinamico"
    assert corpo["dinamico"]["graficos"][0]["tipo"] == "barras"


async def test_resultado_vazio_vira_texto(client, llm):
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]))
    corpo = (await _perguntar(client)).json()
    assert (corpo["forma"], corpo["texto"]["mensagem"]) == ("texto", "Nenhum aluno com esses filtros.")


async def test_fora_do_catalogo(client, llm):
    llm.respostas.append(_json(tipo="fora_do_catalogo", interpretacao="A base não tem dado de evasão."))
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "nao_entendi"
    assert "evasão" in corpo["nao_entendi"]["motivo"]
    assert corpo["nao_entendi"]["sugestoes"]


async def test_nova_tentativa_manda_o_erro_ao_modelo(client, llm):
    llm.respostas += [_json(tipo="agregado", metrica="inexistente"),
                      _json(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"])]
    corpo = (await _perguntar(client)).json()
    assert corpo["forma"] == "dashboard"
    assert len(llm.chamadas) == 2
    assert "inexistente" in llm.chamadas[1][-1]["content"]


async def test_duas_respostas_invalidas_viram_nao_entendi(client, llm):
    llm.respostas += ["isto não é json", _json(tipo="agregado", metrica="inexistente")]
    assert (await _perguntar(client)).json()["forma"] == "nao_entendi"


async def test_json_embrulhado_em_markdown_e_aproveitado(client, llm):
    llm.respostas.append("```json\n" + _json(tipo="agregado", metrica="contagem_alunos", dimensoes=["polo"]) + "\n```")
    assert (await _perguntar(client)).json()["forma"] == "dashboard"


async def test_llm_indisponivel_vira_503(client, llm):
    llm.respostas.append(LLMIndisponivel("Groq respondeu HTTP 429."))
    resposta = await _perguntar(client)
    assert (resposta.status_code, resposta.json()["detail"]) == (503, "Groq respondeu HTTP 429.")


async def test_consulta_demorada_vira_504(client, llm, semear, monkeypatch):
    semear(A)
    def lenta(session, consulta):
        raise ConsultaDemorada()
    monkeypatch.setattr(pipeline, "resolver", lenta)
    llm.respostas.append(_json(tipo="agregado", metrica="contagem_alunos", dimensoes=["renda"]))
    assert (await _perguntar(client)).status_code == 504


async def test_nada_que_identifica_aluno_sai_para_o_llm(client, llm, semear):
    semear(A, nome="MARIA DA SILVA", CRG=6.5)
    llm.respostas.append(_json(tipo="lista", metrica="alunos", filtros=[{"campo": "matricula", "valor": "⟨A1⟩"}],
                               interpretacao="Perfil de ⟨A1⟩"))
    corpo = (await _perguntar(client, f"Mostre a Maria da Silva, matrícula {A}")).json()
    assert corpo["forma"] == "dashboard"
    assert corpo["dashboard"] == {"id": "perfil", "params": {"matricula": str(A)}}
    assert corpo["consulta"]["interpretacao"] == f"Perfil de {A}"
    enviado = json.dumps(llm.chamadas, ensure_ascii=False).lower()
    assert str(A) not in enviado
    assert "maria" not in enviado
    assert len(llm.chamadas) == 1  # resultado nunca volta ao modelo


async def test_executar_nao_chama_o_llm(client, llm, semear):
    semear(A, renda="Até 1 salário mínimo")
    consulta = {"tipo": "agregado", "metrica": "contagem_alunos", "dimensoes": ["renda"]}
    corpo = (await client.post("/assistente/executar", json={"consulta": consulta})).json()
    assert corpo["forma"] == "dinamico"
    assert llm.chamadas == []


async def test_executar_consulta_fora_do_catalogo_e_422(client, llm):
    resposta = await client.post("/assistente/executar", json={"consulta": {"tipo": "agregado", "metrica": "evasao"}})
    assert resposta.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assistente_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.assistente'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/assistente/intencao.py
"""Pergunta (já anonimizada) -> ConsultaEstruturada, com uma chamada ao LLM.

O prompt leva o catálogo inteiro: métricas, dimensões e os valores válidos de
cada uma (opções do questionário, polos, turmas, períodos). Nenhuma linha de
aluno. Se a resposta não validar, o erro volta ao modelo uma vez."""
import json
import re

from pydantic import ValidationError

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.catalogo import DIMENSOES, METRICAS, ConsultaInvalida, validar
from app.services.assistente.provedor_llm import ProvedorLLM

SISTEMA = """Você traduz perguntas sobre alunos de um curso de graduação para uma consulta estruturada.
Responda APENAS um objeto JSON com as chaves:
  tipo: "agregado" | "lista" | "operacional" | "fora_do_catalogo"
  metrica: id de métrica do catálogo (null se fora_do_catalogo)
  dimensoes: lista de ids de dimensão para agrupar (0 a 2)
  filtros: lista de {"campo": id, "op": "=" | "in" | "entre", "valor": valor ou lista}
  ordem: {"campo": "valor" ou id de dimensão, "direcao": "asc" | "desc"} ou null
  limite: inteiro ou null
  interpretacao: uma frase em português dizendo o que você entendeu
Regras:
- Use só ids e valores que aparecem no catálogo, com a grafia exata.
- Marcadores como ⟨A1⟩ representam um aluno: use-os como valor do campo "matricula".
- "Mostre/liste alunos" é tipo "lista" com metrica "alunos". "Quantos" sem agrupamento é "agregado" sem dimensões.
- Turma é o ano de ingresso: "ingressaram em 2020" é o filtro turma = "2020".
- Se a pergunta pede algo que o catálogo não tem, use tipo "fora_do_catalogo" e diga em interpretacao o que falta."""


def descrever_catalogo(valores: dict[str, list[str]]) -> str:
    linhas = ["MÉTRICAS (id [tipo]: descrição; dimensões aceitas; filtros aceitos):"]
    for m in METRICAS.values():
        linhas.append(f"- {m.id} [{m.tipo}]: {m.rotulo}; dimensões: {', '.join(sorted(m.dimensoes)) or 'nenhuma'}; "
                      f"filtros: {', '.join(sorted(m.filtros)) or 'nenhum'}")
    linhas.append("DIMENSÕES (id (rótulo): valores válidos):")
    for d in DIMENSOES.values():
        if d.id == "matricula":
            linhas.append("- matricula (Matrícula): só marcadores ⟨An⟩ presentes na pergunta")
        else:
            linhas.append(f"- {d.id} ({d.rotulo}): {json.dumps(valores.get(d.id, []), ensure_ascii=False)}")
    return "\n".join(linhas)


def montar_mensagens(pergunta: str, valores: dict[str, list[str]]) -> list[dict]:
    return [{"role": "system", "content": f"{SISTEMA}\n\nCATÁLOGO\n{descrever_catalogo(valores)}"},
            {"role": "user", "content": pergunta}]


def _extrair_json(texto: str) -> str:
    """Alguns modelos embrulham o JSON em ```json ... ``` mesmo em JSON mode."""
    achado = re.search(r"\{.*\}", texto, re.DOTALL)
    return achado.group() if achado else texto


def interpretar(provedor: ProvedorLLM, pergunta: str, valores: dict[str, list[str]]) -> ConsultaEstruturada | None:
    mensagens = montar_mensagens(pergunta, valores)
    for _ in range(2):
        texto = provedor.completar(mensagens)
        try:
            return validar(ConsultaEstruturada.model_validate_json(_extrair_json(texto)), valores)
        except (ValidationError, ConsultaInvalida) as erro:
            mensagens = [*mensagens, {"role": "assistant", "content": texto},
                         {"role": "user", "content": f"Resposta inválida: {erro}. Corrija e responda só o JSON."}]
    return None
```

```python
# backend/app/services/assistente/pipeline.py
"""Pergunta -> resposta: anonimiza, interpreta, planeja, executa, descreve."""
import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.schemas.assistente import BlocoDashboard, ConsultaEstruturada, Explicacao, RespostaAssistente
from app.services.assistente.anonimizador import anonimizar, nomes_da_base, restaurar
from app.services.assistente.catalogo import validar, valores_validos
from app.services.assistente.compilador import Resultado, fontes, resolver_sql
from app.services.assistente.intencao import interpretar
from app.services.assistente.operacionais import resolver_operacional
from app.services.assistente.planejador import params_do_dashboard, planejar
from app.services.assistente.provedor_llm import ProvedorLLM
from app.services.assistente.respostas import (descrever, filtros_aplicados, nao_entendi, tabela_para,
                                               texto_para)
from app.services.assistente.visualizacao import montar_dinamico

log = logging.getLogger("app.assistente")
_NAO_TRADUZIDA = "Não consegui traduzir a pergunta para o que o assistente sabe consultar."


def resolver(session: Session, consulta: ConsultaEstruturada) -> Resultado:
    if consulta.tipo == "operacional" or consulta.metrica in ("alunos_incompletos", "nao_integrados"):
        return resolver_operacional(session, consulta)
    return resolver_sql(session, consulta)


def _restaurar(consulta: ConsultaEstruturada, marcadores: dict[str, str]) -> ConsultaEstruturada | None:
    """Troca ⟨An⟩ pela matrícula. Marcador que a pergunta não tinha (inventado
    pelo modelo) torna a consulta inválida."""
    filtros = []
    for f in consulta.filtros:
        if f.campo == "matricula":
            valores = f.valor if isinstance(f.valor, list) else [f.valor]
            reais = [marcadores.get(v, v) for v in valores]
            if not all(v.isdigit() for v in reais):
                return None
            f = f.model_copy(update={"valor": reais if isinstance(f.valor, list) else reais[0]})
        filtros.append(f)
    return consulta.model_copy(update={"filtros": filtros, "interpretacao": restaurar(consulta.interpretacao, marcadores)})


def _resposta(pergunta, consulta, forma, fontes_usadas, **bloco) -> RespostaAssistente:
    explicacao = Explicacao(
        consulta_interpretada=descrever(consulta) if consulta else _NAO_TRADUZIDA,
        filtros_aplicados=filtros_aplicados(consulta) if consulta else [],
        fontes=fontes_usadas, forma=forma)
    return RespostaAssistente(id=uuid.uuid4().hex, pergunta=pergunta, consulta=consulta, forma=forma,
                              explicacao=explicacao, **bloco)


def responder(session: Session, consulta: ConsultaEstruturada | None, pergunta: str | None) -> RespostaAssistente:
    if consulta is None:
        return _resposta(pergunta, None, "nao_entendi", [], nao_entendi=nao_entendi(_NAO_TRADUZIDA))
    plano = planejar(consulta)
    if plano.forma == "nao_entendi":
        return _resposta(pergunta, consulta, "nao_entendi", [], nao_entendi=nao_entendi(consulta.interpretacao or _NAO_TRADUZIDA))
    if plano.forma == "dashboard":
        bloco = BlocoDashboard(id=plano.dashboard.id, params=params_do_dashboard(plano.dashboard, consulta))
        return _resposta(pergunta, consulta, "dashboard", fontes(consulta), dashboard=bloco)
    resultado = resolver(session, consulta)
    vazio = not resultado.linhas or (consulta.metrica == "contagem_alunos" and not consulta.dimensoes
                                     and not resultado.linhas[0]["valor"])
    if vazio or plano.forma == "texto":
        return _resposta(pergunta, consulta, "texto", resultado.fontes, texto=texto_para(consulta, resultado))
    if plano.forma == "tabela":
        return _resposta(pergunta, consulta, "tabela", resultado.fontes, tabela=tabela_para(resultado))
    return _resposta(pergunta, consulta, "dinamico", resultado.fontes, dinamico=montar_dinamico(consulta, resultado))


def perguntar(session: Session, provedor: ProvedorLLM, pergunta: str) -> RespostaAssistente:
    inicio = time.monotonic()
    anonima = anonimizar(pergunta, nomes_da_base(session))
    interpretada = interpretar(provedor, anonima.texto, valores_validos(session))
    consulta = _restaurar(interpretada, anonima.marcadores) if interpretada else None
    resposta = responder(session, consulta, pergunta)
    # Só o que já saiu para o LLM vai ao log: pergunta e consulta anonimizadas.
    log.info("assistente pergunta=%r consulta=%s forma=%s duracao_ms=%d", anonima.texto,
             interpretada.model_dump_json() if interpretada else None, resposta.forma,
             (time.monotonic() - inicio) * 1000)
    return resposta


def executar(session: Session, consulta: ConsultaEstruturada) -> RespostaAssistente:
    """Reexecuta uma consulta salva (histórico, link compartilhado), sem LLM."""
    return responder(session, validar(consulta, valores_validos(session)), None)
```

```python
# backend/app/api/assistente.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.engine import get_session
from app.schemas.assistente import ExecutarIn, PerguntaIn, RespostaAssistente
from app.services.assistente import pipeline
from app.services.assistente.catalogo import ConsultaInvalida
from app.services.assistente.execucao import ConsultaDemorada
from app.services.assistente.provedor_llm import LLMIndisponivel, ProvedorLLM, provedor_padrao

router = APIRouter(prefix="/assistente", tags=["assistente"])

# Só leitura. O LLM recebe a pergunta anonimizada e o catálogo, nunca dado de
# aluno (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md).

_DEMORADA = "A consulta passou de 5 s e foi cancelada."


def obter_provedor() -> ProvedorLLM:
    """Dependência: os testes trocam pelo ProvedorFalso."""
    return provedor_padrao()


@router.post("/perguntar", response_model=RespostaAssistente)
def perguntar(corpo: PerguntaIn, session: Session = Depends(get_session),
              provedor: ProvedorLLM = Depends(obter_provedor)):
    """POST /assistente/perguntar -> a resposta na forma escolhida, com explicação.
    503 se o LLM estiver indisponível; /executar continua funcionando."""
    try:
        return pipeline.perguntar(session, provedor, corpo.pergunta)
    except LLMIndisponivel as erro:
        raise HTTPException(503, str(erro)) from erro
    except ConsultaDemorada as erro:
        raise HTTPException(504, _DEMORADA) from erro


@router.post("/executar", response_model=RespostaAssistente)
def executar(corpo: ExecutarIn, session: Session = Depends(get_session)):
    """POST /assistente/executar -> reexecuta uma ConsultaEstruturada sem LLM
    (histórico, link compartilhado). 422 se ela citar algo fora do catálogo."""
    try:
        return pipeline.executar(session, corpo.consulta)
    except ConsultaInvalida as erro:
        raise HTTPException(422, str(erro)) from erro
    except ConsultaDemorada as erro:
        raise HTTPException(504, _DEMORADA) from erro
```

In `backend/app/main.py`, add next to the other router imports and includes:

```python
from app.api.assistente import router as assistente_router
```

```python
app.include_router(assistente_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assistente_api.py -v && pytest`
Expected: 14 passed no arquivo novo; a suíte inteira verde.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/assistente/intencao.py backend/app/services/assistente/pipeline.py backend/app/api/assistente.py backend/app/main.py tests/conftest.py tests/test_assistente_api.py
git commit -m "feat(assistente): interpretação pelo LLM, pipeline e rotas /assistente"
```

---

### Task 9: Filtros das telas na URL

**Files:**
- Create: `frontend/src/domain/filtrosUrl.ts`
- Create: `frontend/src/hooks/useFiltroUrl.ts`
- Modify: `frontend/src/hooks/DadosProvider.tsx` (período lido de `?periodo=`)
- Modify: `frontend/src/components/ChartBidimensional.tsx:39-40`, `ChartDistribuicao.tsx:22`, `ChartLongitudinal.tsx:26-27`
- Test: `frontend/src/domain/filtrosUrl.test.ts`, `frontend/src/pages/paginas.test.tsx` (acrescenta casos)

**Interfaces:**
- Produces: `lerFiltro(params, nome, padrao) -> string`; `comFiltro(params, nome, valor, padrao) -> URLSearchParams`; `queryDe(params: Record<string, string | undefined>) -> string` (`''` ou `'?a=b'`); `useFiltroUrl(nome, padrao) -> [string, (v: string) => void]`. Parâmetros de URL: `periodo` (global), `dimensao` e `polo` (Bidimensional), `polo` (Distribuição), `polo` e `turma` (Longitudinal).

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/domain/filtrosUrl.test.ts
import { describe, expect, test } from 'vitest';
import { comFiltro, lerFiltro, queryDe } from './filtrosUrl';

describe('filtros na URL', () => {
  test('ausente = padrão', () => {
    expect(lerFiltro(new URLSearchParams(''), 'polo', 'Todos')).toBe('Todos');
    expect(lerFiltro(new URLSearchParams('polo=Oeiras'), 'polo', 'Todos')).toBe('Oeiras');
  });
  test('valor padrão sai da URL e os outros filtros ficam', () => {
    const p = comFiltro(new URLSearchParams('polo=Oeiras&dimensao=renda'), 'polo', 'Todos', 'Todos');
    expect(p.toString()).toBe('dimensao=renda');
    expect(comFiltro(p, 'polo', 'Cametá', 'Todos').get('polo')).toBe('Cametá');
  });
  test('queryDe ignora vazios e codifica acento', () => {
    expect(queryDe({ polo: 'Cametá', periodo: undefined, turma: '' })).toBe('?polo=Camet%C3%A1');
    expect(queryDe({})).toBe('');
  });
});
```

Append to the `describe` block of `frontend/src/pages/paginas.test.tsx` (the file already renders the Análises routes):

```ts
  test('Bidimensional abre com a dimensão e o polo da URL', () => {
    const html = render('/analises/bidimensional?dimensao=renda&polo=Camet%C3%A1');
    expect(html).toMatch(/<option value="renda" selected="">/);
    expect(html).toMatch(/<option value="Cametá" selected="">/);
  });
  test('Distribuição e Longitudinal abrem com o polo da URL', () => {
    expect(render('/analises/distribuicao?polo=Oeiras')).toMatch(/<option value="Oeiras" selected="">/);
    expect(render('/analises/longitudinal?polo=Oeiras')).toMatch(/<option value="Oeiras" selected="">/);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/domain/filtrosUrl.test.ts src/pages/paginas.test.tsx`
Expected: FAIL (`Failed to resolve import "./filtrosUrl"`; os casos novos de páginas não acham `selected=""`)

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/domain/filtrosUrl.ts
/**
 * Filtros das telas na query string: o assistente abre uma tela já filtrada
 * (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md) e o link
 * copiado da barra reproduz a mesma visão.
 */

export function lerFiltro(params: URLSearchParams, nome: string, padrao: string): string {
  return params.get(nome) ?? padrao;
}

/** Nova query string com o filtro. O valor padrão sai da URL, para o link ficar limpo. */
export function comFiltro(params: URLSearchParams, nome: string, valor: string, padrao: string): URLSearchParams {
  const nova = new URLSearchParams(params);
  if (valor === padrao) nova.delete(nome);
  else nova.set(nome, valor);
  return nova;
}

/** `?a=b&c=d` a partir de um objeto, sem os vazios; `''` se não sobrar nada. */
export function queryDe(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [nome, valor] of Object.entries(params)) if (valor) q.set(nome, valor);
  const texto = q.toString();
  return texto ? `?${texto}` : '';
}
```

```ts
// frontend/src/hooks/useFiltroUrl.ts
import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { comFiltro, lerFiltro } from '../domain/filtrosUrl';

/** Como useState, mas o valor mora na URL (`?nome=valor`). */
export function useFiltroUrl(nome: string, padrao: string): [string, (valor: string) => void] {
  const [params, setParams] = useSearchParams();
  const definir = useCallback(
    (valor: string) => setParams((atuais) => comFiltro(atuais, nome, valor, padrao), { replace: true }),
    [nome, padrao, setParams],
  );
  return [lerFiltro(params, nome, padrao), definir];
}
```

In `ChartBidimensional.tsx`, replace the two `useState` lines (39–40) and add the import:

```ts
import { useFiltroUrl } from '../hooks/useFiltroUrl';
// ...
  const [eixoX, setEixoX] = useFiltroUrl('dimensao', 'cor_etnia');
  const [polo, setPolo] = useFiltroUrl('polo', TODOS);
```

In `ChartDistribuicao.tsx`, replace `const [polo, setPolo] = useState(TODOS);` with `const [polo, setPolo] = useFiltroUrl('polo', TODOS);` and add the same import.

In `ChartLongitudinal.tsx`, replace lines 26–27 (the `matricula` state stays in `useState`):

```ts
  const [polo, setPolo] = useFiltroUrl('polo', TODOS);
  const [turma, setTurma] = useFiltroUrl('turma', TODOS);
```

Remove `useState` from the React import where it became unused (ChartBidimensional, ChartDistribuicao).

In `DadosProvider.tsx`, add `import { useSearchParams } from 'react-router-dom';` and, right after the `useState` declarations:

```ts
  // O período também pode chegar pela URL (?periodo=), quando o assistente abre
  // uma tela filtrada. Links internos não levam o parâmetro, então navegar
  // entre telas mantém o período escolhido no seletor.
  const [params] = useSearchParams();
  const periodoDaUrl = params.get('periodo');
  useEffect(() => {
    if (periodoDaUrl !== null) setPeriodo(periodoDaUrl);
  }, [periodoDaUrl]);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run && npm run lint`
Expected: todos os testes passam; lint sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/domain/filtrosUrl.ts frontend/src/domain/filtrosUrl.test.ts frontend/src/hooks/useFiltroUrl.ts frontend/src/hooks/DadosProvider.tsx frontend/src/components/ChartBidimensional.tsx frontend/src/components/ChartDistribuicao.tsx frontend/src/components/ChartLongitudinal.tsx frontend/src/pages/paginas.test.tsx
git commit -m "feat(frontend): filtros das telas de análise e período na URL"
```

---

### Task 10: Camada de dados do chat (tipos, API, rotas, histórico, link, CSV, gráfico)

**Files:**
- Modify: `frontend/src/data/tipos.ts` (fim do arquivo), `frontend/src/data/api.ts` (fim do arquivo), `frontend/src/theme/cores.ts` (exporta `PALETA_CATEGORICA`)
- Create: `frontend/src/domain/catalogoDashboards.ts`, `historico.ts`, `compartilhar.ts`, `csv.ts`, `graficoDinamico.ts`
- Test: `frontend/src/data/api.test.ts` (acrescenta), `frontend/src/domain/assistente.test.ts`

**Interfaces:**
- Consumes: `queryDe` (Task 9); `chamar`/`ErroApi` (existentes em `api.ts`); `corDaEntidade`, `RAMPA_TURMA`, `COR_SINALIZACAO`, `COR_PRIMARIA` (existentes em `cores.ts`).
- Produces: tipos `FormaResposta`, `FiltroConsulta`, `ConsultaEstruturada`, `ExplicacaoAssistente`, `GraficoDinamico`, `BlocoTabela`, `BlocoDinamico`, `RespostaAssistente`; `perguntarAssistente(pergunta, opcoes?)`, `executarConsulta(consulta, opcoes?)`; `rotaDoDashboard(id, params) -> string | null`; `ItemHistorico`, `LIMITE_HISTORICO`, `carregarHistorico(armazenamento?)`, `salvarHistorico(itens, armazenamento?)`, `adicionar(itens, novo)`, `alternarFavorito(itens, id)`, `ordenarParaExibir(itens)`; `codificarConsulta(c)`, `decodificarConsulta(codigo) -> ConsultaEstruturada | null`, `linkDeCompartilhamento(item, origem)`; `paraCsv(colunas, linhas)`; `pivotar(dados, eixo, serie, campo, ordemSeries)`, `ehAusente(valor)`, `corDaSerie(nome, series, dimensao, ordinal)`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/domain/assistente.test.ts
import { describe, expect, test } from 'vitest';
import type { ConsultaEstruturada } from '../data/tipos';
import { rotaDoDashboard } from './catalogoDashboards';
import { adicionar, alternarFavorito, carregarHistorico, LIMITE_HISTORICO, ordenarParaExibir, salvarHistorico } from './historico';
import type { ItemHistorico } from './historico';
import { codificarConsulta, decodificarConsulta, linkDeCompartilhamento } from './compartilhar';
import { paraCsv } from './csv';
import { corDaSerie, pivotar } from './graficoDinamico';

const consulta: ConsultaEstruturada = {
  tipo: 'agregado', metrica: 'contagem_alunos', dimensoes: ['polo'],
  filtros: [{ campo: 'polo', op: '=', valor: 'Cametá' }], ordem: null, limite: null, interpretacao: 'Alunos em Cametá',
};
const item = (id: string, favorito = false): ItemHistorico => ({
  id, pergunta: `p${id}`, consulta, forma: 'dinamico', quando: '2026-09-25T00:00:00Z', favorito, rota: null,
});

describe('rotas dos dashboards', () => {
  test('cada id monta a rota com os filtros', () => {
    expect(rotaDoDashboard('polos', {})).toBe('/');
    expect(rotaDoDashboard('polos', { periodo: '2025.(3 e 4)' })).toBe('/?periodo=2025.%283+e+4%29');
    expect(rotaDoDashboard('turmas', { polo: 'Cametá' })).toBe('/polo/Camet%C3%A1');
    expect(rotaDoDashboard('alunos_turma', { polo: 'Oeiras', turma: '2021' })).toBe('/polo/Oeiras/turma/2021');
    expect(rotaDoDashboard('perfil', { matricula: '202016040001' })).toBe('/aluno/202016040001');
    expect(rotaDoDashboard('bidimensional', { dimensao: 'renda' })).toBe('/analises/bidimensional?dimensao=renda');
    expect(rotaDoDashboard('longitudinal', { turma: '2020' })).toBe('/analises/longitudinal?turma=2020');
    expect(rotaDoDashboard('inexistente', {})).toBeNull();
  });
});

describe('histórico', () => {
  test('mais recente primeiro; ao passar do limite sai o não favorito mais antigo', () => {
    let itens: ItemHistorico[] = [item('antigo-favorito', true)];
    for (let i = 0; i < LIMITE_HISTORICO; i++) itens = adicionar(itens, item(String(i)));
    expect(itens).toHaveLength(LIMITE_HISTORICO);
    expect(itens[0].id).toBe(String(LIMITE_HISTORICO - 1));
    expect(itens.some((i) => i.id === 'antigo-favorito')).toBe(true);
    expect(itens.some((i) => i.id === '0')).toBe(false);
  });
  test('favoritos no topo da exibição', () => {
    const itens = alternarFavorito([item('a'), item('b')], 'b');
    expect(ordenarParaExibir(itens).map((i) => i.id)).toEqual(['b', 'a']);
  });
  test('armazenamento corrompido, indisponível ou cheio não quebra', () => {
    expect(carregarHistorico({ getItem: () => '{nao json', setItem: () => {} })).toEqual([]);
    expect(carregarHistorico({ getItem: () => { throw new Error('bloqueado'); }, setItem: () => {} })).toEqual([]);
    expect(() => salvarHistorico([item('a')], { getItem: () => null, setItem: () => { throw new Error('cota'); } })).not.toThrow();
  });
  test('ida e volta pelo armazenamento', () => {
    const memoria = new Map<string, string>();
    const armazenamento = { getItem: (k: string) => memoria.get(k) ?? null, setItem: (k: string, v: string) => { memoria.set(k, v); } };
    salvarHistorico([item('a')], armazenamento);
    expect(carregarHistorico(armazenamento).map((i) => i.id)).toEqual(['a']);
  });
});

describe('compartilhar', () => {
  test('codifica e decodifica com acento', () => {
    expect(decodificarConsulta(codificarConsulta(consulta))).toEqual(consulta);
  });
  test('código adulterado vira null', () => {
    expect(decodificarConsulta('%%%')).toBeNull();
    expect(decodificarConsulta(btoa('[1,2]'))).toBeNull();
  });
  test('dashboard compartilha a rota; o resto compartilha a consulta', () => {
    expect(linkDeCompartilhamento({ ...item('a'), rota: '/polo/Oeiras' }, 'http://x')).toBe('http://x/polo/Oeiras');
    expect(linkDeCompartilhamento(item('a'), 'http://x')).toBe(`http://x/ia-chat?c=${codificarConsulta(consulta)}`);
  });
});

describe('csv', () => {
  test('separador ;, decimal com vírgula, aspas quando precisa e BOM', () => {
    const csv = paraCsv([{ id: 'nome', rotulo: 'Nome' }, { id: 'crg', rotulo: 'CRG' }],
      [{ nome: 'Ana; Maria', crg: 7.5 }, { nome: null, crg: null }]);
    expect(csv).toBe('﻿Nome;CRG\r\n"Ana; Maria";7,5\r\n;');
  });
});

describe('gráfico dinâmico', () => {
  test('pivota por série na ordem dada', () => {
    const dados = [{ polo: 'Cametá', renda: 'B', percentual: 60 }, { polo: 'Cametá', renda: 'A', percentual: 40 },
      { polo: 'Oeiras', renda: 'A', percentual: 100 }];
    expect(pivotar(dados, 'polo', 'renda', 'percentual', ['A', 'B'])).toEqual({
      linhas: [{ polo: 'Cametá', B: 60, A: 40 }, { polo: 'Oeiras', A: 100 }], series: ['A', 'B'],
    });
    expect(pivotar([{ polo: 'Cametá', valor: 2 }], 'polo', null, 'valor', [])).toEqual({
      linhas: [{ polo: 'Cametá', valor: 2 }], series: ['valor'],
    });
  });
  test('ausência é cinza; ordinal segue a rampa; polo mantém a cor fixa', () => {
    expect(corDaSerie('Sem resposta', ['A', 'Sem resposta'], 'renda', true)).toBe('#94a3b8');
    const rampa = ['A', 'B', 'C'].map((s) => corDaSerie(s, ['A', 'B', 'C'], 'renda', true));
    expect(new Set(rampa).size).toBe(3);
    expect(corDaSerie('Cametá', ['Cametá', 'Oeiras'], 'polo', false)).toBe('#2563eb');
  });
});
```

Append to `frontend/src/data/api.test.ts`:

```ts
import { executarConsulta, perguntarAssistente } from './api';

describe('assistente', () => {
  test('pergunta por POST em JSON', async () => {
    // Objeto, e não `let`: o TS estreitaria um `let x = null` atribuído dentro do callback para `never`.
    const visto: { url?: string; init?: RequestInit } = {};
    const fetchFalso = async (url: RequestInfo | URL, init?: RequestInit) => {
      visto.url = String(url);
      visto.init = init;
      return new Response(JSON.stringify({ id: 'r1' }), { status: 200 });
    };
    const resposta = await perguntarAssistente('Quantos alunos?', { baseUrl: '/api', fetchFn: fetchFalso as typeof fetch });
    expect(resposta.id).toBe('r1');
    expect(visto.url).toBe('/api/assistente/perguntar');
    expect(visto.init?.method).toBe('POST');
    expect(JSON.parse(String(visto.init?.body))).toEqual({ pergunta: 'Quantos alunos?' });
  });
  test('503 vira ErroApi com o detail', async () => {
    const fetchFalso = async () => new Response(JSON.stringify({ detail: 'Groq respondeu HTTP 429.' }), { status: 503 });
    await expect(executarConsulta({} as never, { baseUrl: '/api', fetchFn: fetchFalso })).rejects.toMatchObject({
      status: 503, detail: 'Groq respondeu HTTP 429.',
    });
  });
});
```

(Move the new `import` line to the top of `api.test.ts`, merging it with the existing `import ... from './api'`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/domain/assistente.test.ts src/data/api.test.ts`
Expected: FAIL (`Failed to resolve import "./catalogoDashboards"`, `perguntarAssistente is not exported`)

- [ ] **Step 3: Write minimal implementation**

Append to `frontend/src/data/tipos.ts`:

```ts

/* Assistente de consultas: espelho de backend/app/schemas/assistente.py */

export type FormaResposta = 'dashboard' | 'dinamico' | 'tabela' | 'texto' | 'nao_entendi';

export interface FiltroConsulta {
  campo: string;
  op: '=' | 'in' | 'entre';
  valor: string | string[];
}

export interface ConsultaEstruturada {
  tipo: 'agregado' | 'lista' | 'operacional' | 'fora_do_catalogo';
  metrica: string | null;
  dimensoes: string[];
  filtros: FiltroConsulta[];
  ordem: { campo: string; direcao: 'asc' | 'desc' } | null;
  limite: number | null;
  interpretacao: string;
}

export interface ExplicacaoAssistente {
  consulta_interpretada: string;
  filtros_aplicados: { rotulo: string; valor: string }[];
  fontes: string[];
  forma: FormaResposta;
}

export type Celula = string | number | null;

export interface GraficoDinamico {
  tipo: 'barras' | 'barras_empilhadas' | 'barras_agrupadas' | 'linha' | 'rosca' | 'histograma';
  titulo: string;
  eixo: string;
  serie: string | null;
  series: string[];
  serie_ordinal: boolean;
  rotulo_valor: string;
  dados: Record<string, Celula>[];
}

export interface BlocoDinamico {
  kpis: { rotulo: string; valor: number | null; n: number }[];
  graficos: GraficoDinamico[];
}

export interface BlocoTabela {
  colunas: { id: string; rotulo: string }[];
  linhas: Record<string, Celula>[];
  total: number;
}

export interface RespostaAssistente {
  id: string;
  pergunta: string | null;
  consulta: ConsultaEstruturada | null;
  forma: FormaResposta;
  explicacao: ExplicacaoAssistente;
  dashboard: { id: string; params: Record<string, string> } | null;
  dinamico: BlocoDinamico | null;
  tabela: BlocoTabela | null;
  texto: { mensagem: string; valor: number | null; n: number | null } | null;
  nao_entendi: { motivo: string; sugestoes: string[] } | null;
}
```

Append to `frontend/src/data/api.ts` (and add `ConsultaEstruturada, RespostaAssistente` to the existing `import type ... from './tipos'`):

```ts

const JSON_POST = { method: 'POST', headers: { 'Content-Type': 'application/json' } } as const;

/** POST /assistente/perguntar: a pergunta em português; a API anonimiza antes do LLM. */
export function perguntarAssistente(pergunta: string, opcoes: Opcoes = {}): Promise<RespostaAssistente> {
  return chamar('/assistente/perguntar', { ...JSON_POST, body: JSON.stringify({ pergunta }) }, opcoes) as Promise<RespostaAssistente>;
}

/** POST /assistente/executar: reexecuta uma consulta salva, sem LLM (histórico, link). */
export function executarConsulta(consulta: ConsultaEstruturada, opcoes: Opcoes = {}): Promise<RespostaAssistente> {
  return chamar('/assistente/executar', { ...JSON_POST, body: JSON.stringify({ consulta }) }, opcoes) as Promise<RespostaAssistente>;
}
```

In `frontend/src/theme/cores.ts`, change `const PALETA_CATEGORICA` to `export const PALETA_CATEGORICA`.

```ts
// frontend/src/domain/catalogoDashboards.ts
import { queryDe } from './filtrosUrl';

type Params = Record<string, string>;

/**
 * id de dashboard (backend: catalogo.DASHBOARDS) -> rota com os filtros.
 * As rotas moram aqui, junto de main.tsx, e não no backend.
 */
const ROTAS: Record<string, (p: Params) => string> = {
  polos: (p) => `/${queryDe({ periodo: p.periodo })}`,
  turmas: (p) => `/polo/${encodeURIComponent(p.polo)}${queryDe({ periodo: p.periodo })}`,
  alunos_turma: (p) => `/polo/${encodeURIComponent(p.polo)}/turma/${encodeURIComponent(p.turma)}${queryDe({ periodo: p.periodo })}`,
  perfil: (p) => `/aluno/${encodeURIComponent(p.matricula)}`,
  bidimensional: (p) => `/analises/bidimensional${queryDe({ dimensao: p.dimensao, polo: p.polo, periodo: p.periodo })}`,
  distribuicao: (p) => `/analises/distribuicao${queryDe({ polo: p.polo, periodo: p.periodo })}`,
  longitudinal: (p) => `/analises/longitudinal${queryDe({ polo: p.polo, turma: p.turma })}`,
};

export function rotaDoDashboard(id: string, params: Params): string | null {
  const rota = ROTAS[id];
  return rota ? rota(params) : null;
}
```

```ts
// frontend/src/domain/historico.ts
import type { ConsultaEstruturada, FormaResposta } from '../data/tipos';

/** Uma pergunta feita neste navegador. Não há login: o histórico é local. */
export interface ItemHistorico {
  id: string;
  pergunta: string;
  consulta: ConsultaEstruturada;
  forma: FormaResposta;
  quando: string;
  favorito: boolean;
  /** Rota do dashboard, quando a resposta foi abrir um. */
  rota: string | null;
}

export interface Armazenamento {
  getItem(chave: string): string | null;
  setItem(chave: string, valor: string): void;
}

export const CHAVE_HISTORICO = 'assistente.historico';
export const LIMITE_HISTORICO = 100;

/** localStorage, se o navegador deixar: em janela privada ou com dados de site bloqueados, até ler a propriedade lança. */
function armazenamentoPadrao(): Armazenamento | undefined {
  try {
    return globalThis.localStorage ?? undefined;
  } catch {
    return undefined;
  }
}

export function carregarHistorico(armazenamento: Armazenamento | undefined = armazenamentoPadrao()): ItemHistorico[] {
  try {
    const bruto = armazenamento?.getItem(CHAVE_HISTORICO);
    const lido: unknown = bruto ? JSON.parse(bruto) : [];
    return Array.isArray(lido) ? (lido as ItemHistorico[]) : [];
  } catch {
    return [];
  }
}

export function salvarHistorico(itens: ItemHistorico[], armazenamento: Armazenamento | undefined = armazenamentoPadrao()): void {
  try {
    armazenamento?.setItem(CHAVE_HISTORICO, JSON.stringify(itens));
  } catch {
    /* cota cheia ou armazenamento bloqueado: o histórico só não persiste */
  }
}

/** Novo no topo. Passando do limite, sai o não favorito mais antigo. */
export function adicionar(itens: ItemHistorico[], novo: ItemHistorico): ItemHistorico[] {
  const lista = [novo, ...itens];
  if (lista.length <= LIMITE_HISTORICO) return lista;
  const descartar = lista.map((i) => i.favorito).lastIndexOf(false);
  return descartar === -1 ? lista : lista.filter((_, i) => i !== descartar);
}

export function alternarFavorito(itens: ItemHistorico[], id: string): ItemHistorico[] {
  return itens.map((i) => (i.id === id ? { ...i, favorito: !i.favorito } : i));
}

export function ordenarParaExibir(itens: ItemHistorico[]): ItemHistorico[] {
  return [...itens.filter((i) => i.favorito), ...itens.filter((i) => !i.favorito)];
}
```

```ts
// frontend/src/domain/compartilhar.ts
import type { ConsultaEstruturada } from '../data/tipos';
import type { ItemHistorico } from './historico';

/** base64url do JSON em UTF-8: cabe na URL e aguenta acento. */
export function codificarConsulta(consulta: ConsultaEstruturada): string {
  let binario = '';
  new TextEncoder().encode(JSON.stringify(consulta)).forEach((b) => { binario += String.fromCharCode(b); });
  return btoa(binario).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** null para qualquer coisa que não seja uma consulta: link adulterado não quebra a tela. */
export function decodificarConsulta(codigo: string): ConsultaEstruturada | null {
  try {
    const b64 = codigo.replace(/-/g, '+').replace(/_/g, '/');
    const binario = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4));
    const lido: unknown = JSON.parse(new TextDecoder().decode(Uint8Array.from(binario, (c) => c.charCodeAt(0))));
    if (!lido || typeof lido !== 'object' || Array.isArray(lido) || typeof (lido as { tipo?: unknown }).tipo !== 'string') return null;
    return lido as ConsultaEstruturada;
  } catch {
    return null;
  }
}

/** Dashboard: a própria URL da tela filtrada. Demais formas: /ia-chat?c=, que reexecuta sem LLM. */
export function linkDeCompartilhamento(item: Pick<ItemHistorico, 'consulta' | 'rota'>, origem: string): string {
  return item.rota ? `${origem}${item.rota}` : `${origem}/ia-chat?c=${codificarConsulta(item.consulta)}`;
}
```

```ts
// frontend/src/domain/csv.ts
import type { Celula } from '../data/tipos';

/** CSV que o Excel em pt-BR abre certo: `;`, decimal com vírgula, BOM UTF-8. */
export function paraCsv(colunas: { id: string; rotulo: string }[], linhas: Record<string, Celula>[]): string {
  const celula = (v: Celula | undefined) => {
    const texto = v === null || v === undefined ? '' : typeof v === 'number' ? String(v).replace('.', ',') : v;
    return /[";\r\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
  };
  const cabecalho = colunas.map((c) => celula(c.rotulo)).join(';');
  const corpo = linhas.map((l) => colunas.map((c) => celula(l[c.id])).join(';'));
  return '﻿' + [cabecalho, ...corpo].join('\r\n');
}
```

```ts
// frontend/src/domain/graficoDinamico.ts
import type { Celula } from '../data/tipos';
import { COR_SINALIZACAO, corDaEntidade, PALETA_CATEGORICA, RAMPA_TURMA } from '../theme/cores';

export interface Pivotado {
  linhas: Record<string, Celula>[];
  series: string[];
}

/**
 * Formato longo (uma linha por eixo × série, como vem da API) -> uma linha por
 * categoria do eixo, com uma chave por série, que é o que o Recharts desenha.
 * Sem série, a chave do valor é `valor`.
 */
export function pivotar(dados: Record<string, Celula>[], eixo: string, serie: string | null, campo: string, ordemSeries: string[]): Pivotado {
  if (!serie) return { linhas: dados.map((d) => ({ [eixo]: d[eixo], valor: d[campo] })), series: ['valor'] };
  const porEixo = new Map<string, Record<string, Celula>>();
  for (const d of dados) {
    const chave = String(d[eixo]);
    const linha = porEixo.get(chave) ?? { [eixo]: d[eixo] };
    linha[String(d[serie])] = d[campo];
    porEixo.set(chave, linha);
  }
  return { linhas: [...porEixo.values()], series: ordemSeries };
}

/** "Sem resposta", "Sem polo informado", "Sem turma informada": não coletado, nunca um valor. */
export function ehAusente(valor: string): boolean {
  return valor.startsWith('Sem ');
}

/** Cor de uma série: ausência em cinza; polo com a cor fixa dele; ordinal na rampa de um hue só; nominal na paleta categórica. */
export function corDaSerie(nome: string, series: string[], dimensao: string | null, ordinal: boolean): string {
  if (ehAusente(nome)) return COR_SINALIZACAO.sem_dado.hex;
  const presentes = series.filter((s) => !ehAusente(s));
  if (dimensao === 'polo') return corDaEntidade(nome, presentes);
  const i = presentes.indexOf(nome);
  if (ordinal) {
    const passo = presentes.length <= 1 ? RAMPA_TURMA.length - 1 : Math.round((i / (presentes.length - 1)) * (RAMPA_TURMA.length - 1));
    return RAMPA_TURMA[passo];
  }
  return PALETA_CATEGORICA[i] ?? '#64748b';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run && npm run lint`
Expected: todos os testes passam; lint sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/data/tipos.ts frontend/src/data/api.ts frontend/src/data/api.test.ts frontend/src/theme/cores.ts frontend/src/domain/catalogoDashboards.ts frontend/src/domain/historico.ts frontend/src/domain/compartilhar.ts frontend/src/domain/csv.ts frontend/src/domain/graficoDinamico.ts frontend/src/domain/assistente.test.ts
git commit -m "feat(frontend): tipos, API, rotas, histórico, link e CSV do assistente"
```

---

### Task 11: Tela IA Chat, componentes e aviso nas telas abertas pelo assistente

**Files:**
- Create: `frontend/src/components/assistente/Explicacao.tsx`, `RespostaTabela.tsx`, `GraficoDinamico.tsx`, `DashboardDinamico.tsx`, `RespostaView.tsx`, `Historico.tsx`
- Create: `frontend/src/pages/IaChat.tsx`
- Modify: `frontend/src/main.tsx` (rota `/ia-chat` → `IaChat`; remove `EmConstrucao`)
- Modify: `frontend/src/components/layout/AppShell.tsx` (faixa "Aberto pelo assistente")
- Test: `frontend/src/components/assistente/assistente.test.tsx`, `frontend/src/pages/paginas.test.tsx` (acrescenta casos)

**Interfaces:**
- Consumes: tudo da Task 10; `KpiCard` (existente: `label`, `value`, `hint`); `AppShell` (existente: `titulo`, `subtitulo`, `migalhas`, `semFiltros`).
- Produces: `<RespostaView resposta onSugestao />`; `<Historico itens onRepetir onEditar onFavoritar onCompartilhar />`; `ROTULO_FORMA`; estado de navegação `{ assistente: ExplicacaoAssistente }`, lido pelo AppShell.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/assistente/assistente.test.tsx
import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import type { ReactElement } from 'react';
import type { RespostaAssistente } from '../../data/tipos';
import Explicacao from './Explicacao';
import RespostaView from './RespostaView';
import Historico from './Historico';

const html = (el: ReactElement) => renderToString(el).replace(/<!-- -->/g, '');
const explicacao = {
  consulta_interpretada: 'Contagem de alunos por Polo', filtros_aplicados: [{ rotulo: 'Turma', valor: '2020' }],
  fontes: ['aluno_integrado'], forma: 'tabela' as const,
};
function resposta(parcial: Partial<RespostaAssistente>): RespostaAssistente {
  return { id: 'r1', pergunta: 'Pergunta?', consulta: null, forma: 'texto', explicacao, dashboard: null,
    dinamico: null, tabela: null, texto: null, nao_entendi: null, ...parcial };
}
const nada = () => {};

describe('respostas do assistente', () => {
  test('explicação mostra o que entendeu, filtros, fonte e forma', () => {
    const h = html(<Explicacao explicacao={explicacao} />);
    for (const t of ['Consulta interpretada', 'Contagem de alunos por Polo', 'Turma: 2020', 'aluno_integrado', 'Tabela']) expect(h).toContain(t);
    expect(html(<Explicacao explicacao={{ ...explicacao, filtros_aplicados: [] }} />)).toContain('Nenhum');
  });
  test('tabela pagina de 25 em 25, mostra o total e exporta', () => {
    const linhas = Array.from({ length: 30 }, (_, i) => ({ matricula: 202016040000 + i, crg: 7.5 }));
    const h = html(<RespostaView resposta={resposta({ forma: 'tabela', tabela: { colunas: [{ id: 'matricula', rotulo: 'Matrícula' }, { id: 'crg', rotulo: 'CRG' }], linhas, total: 30 } })} onSugestao={nada} />);
    expect(h).toContain('30 registro(s)');
    expect(h).toContain('Página 1 de 2');
    expect(h).toContain('Exportar CSV');
    expect(h.match(/<tr/g)).toHaveLength(26);
    expect(h).toContain('202016040000'); // matrícula sem separador de milhar
    expect(h).toContain('7,5');
  });
  test('texto', () => {
    expect(html(<RespostaView resposta={resposta({ texto: { mensagem: '2 aluno(s) integrado(s).', valor: 2, n: 2 } })} onSugestao={nada} />))
      .toContain('2 aluno(s) integrado(s).');
  });
  test('não entendi traz o motivo e as sugestões', () => {
    const h = html(<RespostaView resposta={resposta({ forma: 'nao_entendi', nao_entendi: { motivo: 'Não há dado de evasão.', sugestoes: ['Quantos alunos existem por polo?'] } })} onSugestao={nada} />);
    expect(h).toContain('Não há dado de evasão.');
    expect(h).toContain('Quantos alunos existem por polo?');
  });
  test('dinâmico mostra título e o n de cada grupo', () => {
    const grafico = { tipo: 'barras' as const, titulo: 'Contagem de alunos por Polo', eixo: 'polo', serie: null, series: [],
      serie_ordinal: false, rotulo_valor: 'Alunos', dados: [{ polo: 'Cametá', valor: 2, n: 2 }, { polo: 'Oeiras', valor: 1, n: 1 }] };
    const h = html(<RespostaView resposta={resposta({ forma: 'dinamico', dinamico: { kpis: [], graficos: [grafico] } })} onSugestao={nada} />);
    expect(h).toContain('Contagem de alunos por Polo');
    expect(h).toContain('Cametá n=2');
    expect(h).toContain('Oeiras n=1');
  });
  test('histórico lista favoritos primeiro, com as quatro ações', () => {
    const consulta = { tipo: 'agregado' as const, metrica: 'x', dimensoes: [], filtros: [], ordem: null, limite: null, interpretacao: '' };
    const itens = [
      { id: 'a', pergunta: 'Primeira', consulta, forma: 'texto' as const, quando: '', favorito: false, rota: null },
      { id: 'b', pergunta: 'Favorita', consulta, forma: 'texto' as const, quando: '', favorito: true, rota: null },
    ];
    const h = html(<Historico itens={itens} onRepetir={nada} onEditar={nada} onFavoritar={nada} onCompartilhar={nada} />);
    expect(h.indexOf('Favorita')).toBeLessThan(h.indexOf('Primeira'));
    for (const acao of ['Repetir', 'Editar', 'Desfavoritar', 'Compartilhar']) expect(h).toContain(acao);
  });
});
```

Append to `frontend/src/pages/paginas.test.tsx`. Add `import IaChat from './IaChat';` to the imports and `<Route path="/ia-chat" element={<IaChat />} />` inside `renderComContexto`'s `<Routes>`; then inside the `describe`:

```tsx
  test('IA Chat avisa que precisa da API em modo demonstração', () => {
    expect(render('/ia-chat')).toContain('modo demonstração');
  });
  test('tela aberta pelo assistente mostra o que foi aplicado', () => {
    const html = renderToString(
      <Contexto.Provider value={dados}>
        <MemoryRouter initialEntries={[{ pathname: '/', state: { assistente: {
          consulta_interpretada: 'Contagem de alunos por Polo', filtros_aplicados: [{ rotulo: 'Período', valor: '2025.(3 e 4)' }],
          fontes: ['aluno_integrado'], forma: 'dashboard' } } }]}>
          <Routes><Route path="/" element={<Polos />} /></Routes>
        </MemoryRouter>
      </Contexto.Provider>,
    ).replace(/<!-- -->/g, '');
    expect(html).toContain('Aberto pelo assistente');
    expect(html).toContain('Período: 2025.(3 e 4)');
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/assistente src/pages/paginas.test.tsx`
Expected: FAIL (`Failed to resolve import "./Explicacao"`, `"./IaChat"`)

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/assistente/Explicacao.tsx
import type { ExplicacaoAssistente, FormaResposta } from '../../data/tipos';

export const ROTULO_FORMA: Record<FormaResposta, string> = {
  dashboard: 'Dashboard existente', dinamico: 'Dashboard dinâmico', tabela: 'Tabela', texto: 'Texto', nao_entendi: 'Não entendi',
};

/** As quatro respostas que toda consulta deve (spec, Resposta explicável). */
export default function Explicacao({ explicacao }: { explicacao: ExplicacaoAssistente }) {
  const filtros = explicacao.filtros_aplicados.map((f) => `${f.rotulo}: ${f.valor}`).join(' · ');
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
      <dt className="font-semibold text-slate-700">Consulta interpretada</dt><dd>{explicacao.consulta_interpretada}</dd>
      <dt className="font-semibold text-slate-700">Filtros aplicados</dt><dd>{filtros || 'Nenhum'}</dd>
      <dt className="font-semibold text-slate-700">Fonte dos dados</dt><dd>{explicacao.fontes.join(', ') || '—'}</dd>
      <dt className="font-semibold text-slate-700">Forma de resposta</dt><dd>{ROTULO_FORMA[explicacao.forma]}</dd>
    </dl>
  );
}
```

```tsx
// frontend/src/components/assistente/RespostaTabela.tsx
import { useState } from 'react';
import type { BlocoTabela, Celula } from '../../data/tipos';
import { paraCsv } from '../../domain/csv';

const POR_PAGINA = 25;

/** Inteiro cru (matrícula não ganha separador de milhar); decimal em pt-BR; vazio vira "—". */
function formatar(v: Celula | undefined): string {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  return v;
}

export default function RespostaTabela({ tabela }: { tabela: BlocoTabela }) {
  const [pagina, setPagina] = useState(0);
  const paginas = Math.max(1, Math.ceil(tabela.linhas.length / POR_PAGINA));
  const visiveis = tabela.linhas.slice(pagina * POR_PAGINA, (pagina + 1) * POR_PAGINA);

  const exportar = () => {
    const url = URL.createObjectURL(new Blob([paraCsv(tabela.colunas, tabela.linhas)], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'consulta.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <p>{tabela.total} registro(s){tabela.total > tabela.linhas.length ? ` · mostrando os primeiros ${tabela.linhas.length}` : ''}</p>
        <button type="button" onClick={exportar} className="rounded-lg border border-slate-300 px-3 py-1 font-semibold text-slate-700 hover:border-blue-400">Exportar CSV</button>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead><tr>{tabela.colunas.map((c) => <th key={c.id} scope="col" className="px-2 py-1 text-left font-semibold text-slate-700">{c.rotulo}</th>)}</tr></thead>
          <tbody>
            {visiveis.map((linha, i) => (
              <tr key={i} className="border-t border-slate-100">{tabela.colunas.map((c) => <td key={c.id} className="px-2 py-1">{formatar(linha[c.id])}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {paginas > 1 && (
        <nav aria-label="Paginação" className="flex items-center gap-3 text-xs">
          <button type="button" disabled={pagina === 0} onClick={() => setPagina((p) => p - 1)} className="font-semibold text-blue-700 disabled:text-slate-400">Anterior</button>
          <span>Página {pagina + 1} de {paginas}</span>
          <button type="button" disabled={pagina >= paginas - 1} onClick={() => setPagina((p) => p + 1)} className="font-semibold text-blue-700 disabled:text-slate-400">Próxima</button>
        </nav>
      )}
    </div>
  );
}
```

```tsx
// frontend/src/components/assistente/GraficoDinamico.tsx
import type { ReactElement } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { GraficoDinamico as Grafico } from '../../data/tipos';
import { corDaSerie, pivotar } from '../../domain/graficoDinamico';
import { COR_PRIMARIA } from '../../theme/cores';

/** "Cametá n=2 · Oeiras n=1": o n fica sempre visível, somado por categoria do eixo. */
function legendaN(g: Grafico): string {
  const porEixo = new Map<string, number>();
  for (const d of g.dados) porEixo.set(String(d[g.eixo]), (porEixo.get(String(d[g.eixo])) ?? 0) + Number(d.n ?? 0));
  return [...porEixo].map(([k, n]) => `${k} n=${n}`).join(' · ');
}

export default function GraficoDinamico({ grafico: g }: { grafico: Grafico }) {
  const campo = g.tipo === 'barras_empilhadas' ? 'percentual' : 'valor';
  const { linhas, series } = pivotar(g.dados, g.eixo, g.serie, campo, g.series);
  const cor = (s: string) => (g.serie ? corDaSerie(s, series, g.serie, g.serie_ordinal) : COR_PRIMARIA);
  const nome = (s: string) => (g.serie ? s : g.rotulo_valor);

  let grafico: ReactElement;
  if (g.tipo === 'rosca') {
    const fatias = g.dados.map((d) => String(d[g.eixo]));
    grafico = (
      <PieChart>
        <Pie data={g.dados} dataKey="valor" nameKey={g.eixo} innerRadius="55%" outerRadius="80%">
          {fatias.map((f) => <Cell key={f} fill={corDaSerie(f, fatias, g.eixo, false)} />)}
        </Pie>
        <Tooltip /><Legend />
      </PieChart>
    );
  } else if (g.tipo === 'linha') {
    grafico = (
      <LineChart data={linhas}>
        <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey={g.eixo} /><YAxis /><Tooltip /><Legend />
        {/* Semestre sem nota é lacuna, nunca zero */}
        {series.map((s) => <Line key={s} dataKey={s} name={nome(s)} stroke={cor(s)} connectNulls={false} />)}
      </LineChart>
    );
  } else if (g.tipo === 'histograma') {
    grafico = (
      <BarChart data={linhas}>
        <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey={g.eixo} /><YAxis allowDecimals={false} /><Tooltip />
        <Bar dataKey="valor" name={g.rotulo_valor} fill={COR_PRIMARIA} />
      </BarChart>
    );
  } else {
    const empilhado = g.tipo === 'barras_empilhadas';
    grafico = (
      <BarChart data={linhas} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" domain={empilhado ? [0, 100] : undefined} unit={empilhado ? '%' : undefined} />
        <YAxis type="category" dataKey={g.eixo} width={160} /><Tooltip />{g.serie && <Legend />}
        {series.map((s) => <Bar key={s} dataKey={s} name={nome(s)} fill={cor(s)} stackId={empilhado ? 'total' : undefined} />)}
      </BarChart>
    );
  }

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-semibold text-slate-800">{g.titulo}</figcaption>
      <div className="h-72"><ResponsiveContainer width="100%" height="100%">{grafico}</ResponsiveContainer></div>
      <p className="text-[11px] text-slate-500">{legendaN(g)}</p>
    </figure>
  );
}
```

```tsx
// frontend/src/components/assistente/DashboardDinamico.tsx
import type { BlocoDinamico } from '../../data/tipos';
import KpiCard from '../ui/KpiCard';
import GraficoDinamico from './GraficoDinamico';

export default function DashboardDinamico({ bloco }: { bloco: BlocoDinamico }) {
  return (
    <div className="space-y-4">
      {bloco.kpis.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {bloco.kpis.map((k) => <KpiCard key={k.rotulo} label={k.rotulo} value={k.valor === null ? '—' : k.valor.toLocaleString('pt-BR')} hint={`n=${k.n}`} />)}
        </div>
      )}
      {bloco.graficos.map((g) => <GraficoDinamico key={g.titulo} grafico={g} />)}
    </div>
  );
}
```

```tsx
// frontend/src/components/assistente/RespostaView.tsx
import type { RespostaAssistente } from '../../data/tipos';
import DashboardDinamico from './DashboardDinamico';
import Explicacao from './Explicacao';
import RespostaTabela from './RespostaTabela';

interface Props {
  resposta: RespostaAssistente;
  onSugestao: (pergunta: string) => void;
}

export default function RespostaView({ resposta, onSugestao }: Props) {
  return (
    <article aria-label={resposta.pergunta ?? 'Consulta'} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      {resposta.pergunta && <p className="text-sm font-semibold text-slate-900">{resposta.pergunta}</p>}
      {resposta.texto && <p className="text-base text-slate-800">{resposta.texto.mensagem}</p>}
      {resposta.tabela && <RespostaTabela tabela={resposta.tabela} />}
      {resposta.dinamico && <DashboardDinamico bloco={resposta.dinamico} />}
      {resposta.nao_entendi && (
        <div className="space-y-2">
          <p className="text-sm text-slate-700">{resposta.nao_entendi.motivo}</p>
          <p className="text-xs text-slate-500">Experimente:</p>
          <ul className="flex flex-wrap gap-2">
            {resposta.nao_entendi.sugestoes.map((s) => (
              <li key={s}><button type="button" onClick={() => onSugestao(s)} className="rounded-full border border-slate-300 px-3 py-1 text-xs hover:border-blue-400">{s}</button></li>
            ))}
          </ul>
        </div>
      )}
      <Explicacao explicacao={resposta.explicacao} />
    </article>
  );
}
```

```tsx
// frontend/src/components/assistente/Historico.tsx
import type { ItemHistorico } from '../../domain/historico';
import { ordenarParaExibir } from '../../domain/historico';

interface Props {
  itens: ItemHistorico[];
  onRepetir: (item: ItemHistorico) => void;
  onEditar: (item: ItemHistorico) => void;
  onFavoritar: (item: ItemHistorico) => void;
  onCompartilhar: (item: ItemHistorico) => void;
}

const ACAO = 'font-semibold text-blue-700 hover:underline';

export default function Historico({ itens, onRepetir, onEditar, onFavoritar, onCompartilhar }: Props) {
  const ordenados = ordenarParaExibir(itens);
  return (
    <aside aria-labelledby="titulo-historico" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <h2 id="titulo-historico" className="text-sm font-bold text-slate-900">Histórico</h2>
      {!ordenados.length ? (
        <p className="text-xs text-slate-500">Suas perguntas ficam aqui, só neste navegador.</p>
      ) : (
        <ul className="space-y-2">
          {ordenados.map((i) => (
            <li key={i.id} className="border-t border-slate-100 pt-2 text-xs">
              <p className="font-medium text-slate-800">{i.favorito && <span aria-label="Favorita">★ </span>}{i.pergunta}</p>
              <div className="mt-1 flex flex-wrap gap-3">
                <button type="button" className={ACAO} onClick={() => onRepetir(i)}>Repetir</button>
                <button type="button" className={ACAO} onClick={() => onEditar(i)}>Editar</button>
                <button type="button" className={ACAO} onClick={() => onFavoritar(i)} aria-pressed={i.favorito}>{i.favorito ? 'Desfavoritar' : 'Favoritar'}</button>
                <button type="button" className={ACAO} onClick={() => onCompartilhar(i)}>Compartilhar</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
```

```tsx
// frontend/src/pages/IaChat.tsx
import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import Historico from '../components/assistente/Historico';
import RespostaView from '../components/assistente/RespostaView';
import { ErroApi, executarConsulta, perguntarAssistente } from '../data/api';
import type { RespostaAssistente } from '../data/tipos';
import { rotaDoDashboard } from '../domain/catalogoDashboards';
import { decodificarConsulta, linkDeCompartilhamento } from '../domain/compartilhar';
import { adicionar, alternarFavorito, carregarHistorico, salvarHistorico } from '../domain/historico';
import type { ItemHistorico } from '../domain/historico';
import { useDados } from '../hooks/useDados';

/** Assistente de consultas (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md). */
export default function IaChat() {
  const { origem, carregando } = useDados();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [pergunta, setPergunta] = useState('');
  const [respostas, setRespostas] = useState<RespostaAssistente[]>([]);
  const [historico, setHistorico] = useState<ItemHistorico[]>(() => carregarHistorico());
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);

  useEffect(() => { salvarHistorico(historico); }, [historico]);

  const registrar = useCallback((r: RespostaAssistente, texto: string) => {
    const rota = r.dashboard ? rotaDoDashboard(r.dashboard.id, r.dashboard.params) : null;
    const consulta = r.consulta;
    if (consulta) {
      setHistorico((atual) => adicionar(atual, { id: r.id, pergunta: texto, consulta, forma: r.forma, quando: new Date().toISOString(), favorito: false, rota }));
    }
    // A tela de destino mostra a explicação (AppShell lê o state).
    if (rota) navigate(rota, { state: { assistente: r.explicacao } });
    else setRespostas((atual) => [r, ...atual]);
  }, [navigate]);

  const rodar = useCallback(async (acao: () => Promise<RespostaAssistente>, texto: string) => {
    setEnviando(true);
    setErro(null);
    try {
      registrar(await acao(), texto);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.detail : 'Falha inesperada ao consultar.');
    } finally {
      setEnviando(false);
    }
  }, [registrar]);

  // Link compartilhado: /ia-chat?c=<consulta> reexecuta sem LLM, assim que a API estiver de pé.
  const codigo = params.get('c');
  useEffect(() => {
    if (!codigo || origem !== 'api') return;
    setParams({}, { replace: true });
    const consulta = decodificarConsulta(codigo);
    if (!consulta) {
      setErro('Link de consulta inválido.');
      return;
    }
    void rodar(() => executarConsulta(consulta), consulta.interpretacao || 'Consulta compartilhada');
  }, [codigo, origem, rodar, setParams]);

  const enviar = (e: FormEvent) => {
    e.preventDefault();
    const texto = pergunta.trim();
    if (texto) void rodar(() => perguntarAssistente(texto), texto);
  };

  const compartilhar = (item: ItemHistorico) => {
    const url = linkDeCompartilhamento(item, window.location.origin);
    setLink(url);
    void navigator.clipboard?.writeText(url).catch(() => {});
  };

  const semApi = origem !== 'api';
  return (
    <AppShell
      titulo="IA Chat"
      subtitulo="Pergunte em português. O assistente abre o dashboard certo, monta um gráfico, lista ou responde em texto, e mostra o que entendeu."
      migalhas={[{ rotulo: 'IA Chat' }]}
      semFiltros
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-label="Conversa" className="space-y-4">
          {!carregando && semApi && (
            <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              O assistente consulta o banco pela API, que não está disponível (modo demonstração).
            </p>
          )}
          <form onSubmit={enviar} className="flex gap-2">
            <label htmlFor="pergunta" className="sr-only">Pergunta</label>
            <input
              id="pergunta" value={pergunta} onChange={(e) => setPergunta(e.target.value)} maxLength={500}
              placeholder="Ex.: Compare renda familiar por polo" disabled={semApi || enviando}
              className="flex-1 rounded-xl border border-slate-300 px-4 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            />
            <button type="submit" disabled={semApi || enviando || !pergunta.trim()} className="rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-300">
              {enviando ? 'Consultando…' : 'Perguntar'}
            </button>
          </form>
          {erro && <p role="alert" className="text-sm text-red-700">{erro}</p>}
          {link && <p className="text-xs text-slate-600">Link copiado: <span className="break-all">{link}</span></p>}
          {respostas.map((r) => <RespostaView key={r.id} resposta={r} onSugestao={setPergunta} />)}
        </section>
        <Historico
          itens={historico}
          onRepetir={(i) => void rodar(() => executarConsulta(i.consulta), i.pergunta)}
          onEditar={(i) => setPergunta(i.pergunta)}
          onFavoritar={(i) => setHistorico((h) => alternarFavorito(h, i.id))}
          onCompartilhar={compartilhar}
        />
      </div>
    </AppShell>
  );
}
```

In `frontend/src/main.tsx`: delete the `EmConstrucao` function, add `import IaChat from './pages/IaChat'`, and replace the `/ia-chat` route with:

```tsx
          {/* Assistente de consultas (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md) */}
          <Route path="/ia-chat" element={<IaChat />} />
```

In `frontend/src/components/layout/AppShell.tsx`: add `useLocation` to the `react-router-dom` import and `import type { ExplicacaoAssistente } from '../../data/tipos';`. At the top of the component body, add:

```tsx
  // Tela aberta pelo assistente: mostra o que ele entendeu e aplicou.
  const assistente = (useLocation().state as { assistente?: ExplicacaoAssistente } | null)?.assistente;
```

and render, immediately before `{children}`:

```tsx
        {assistente && (
          <div role="status" className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            <p><strong>Aberto pelo assistente:</strong> {assistente.consulta_interpretada}</p>
            <p className="mt-1 text-xs">
              Filtros: {assistente.filtros_aplicados.length ? assistente.filtros_aplicados.map((f) => `${f.rotulo}: ${f.valor}`).join(' · ') : 'nenhum'}
              {' · '}Fonte: {assistente.fontes.join(', ')}
            </p>
          </div>
        )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run && npm run lint && npm run build`
Expected: todos os testes passam, lint limpo, build sem erro de tipo.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/assistente frontend/src/pages/IaChat.tsx frontend/src/main.tsx frontend/src/components/layout/AppShell.tsx frontend/src/pages/paginas.test.tsx
git commit -m "feat(frontend): tela IA Chat com as quatro formas de resposta e histórico"
```

---

### Task 12: Avaliação da interpretação e documentação

**Files:**
- Create: `tests/avaliacao_assistente.json`
- Create: `tests/test_assistente_avaliacao.py`
- Modify: `API_README.md` (seção nova ao fim), `docs/frontend_dashboards.md` (linha na tabela de rotas + parágrafo), `docs/superpowers/specs/2026-09-25-assistente-consultas-design.md` (seção "Ajustes do plano")

**Interfaces:**
- Consumes: `interpretar` (Task 8), `provedor_padrao` (Task 1), `valores_validos` (Task 2).

- [ ] **Step 1: Write the evaluation (skipped by default)**

```python
# tests/test_assistente_avaliacao.py
"""Taxa de acerto da interpretação contra o Groq REAL (métrica para a dissertação).

Fora da suíte padrão: rode com
    AVALIAR_LLM=1 GROQ_API_KEY=... pytest tests/test_assistente_avaliacao.py -s
AVALIAR_LLM_MINIMO=0.8 faz o teste falhar abaixo de 80%.

Os `valores` do JSON são os do banco real, gerados como descrito no Step 3 da
Task 12 do plano. Acerto = mesmo tipo, métrica, dimensões e filtros."""
import json
import os
from pathlib import Path

import pytest

from app.schemas.assistente import ConsultaEstruturada
from app.services.assistente.intencao import interpretar
from app.services.assistente.provedor_llm import provedor_padrao

pytestmark = pytest.mark.skipif(os.getenv("AVALIAR_LLM") != "1", reason="avaliação contra o LLM real: AVALIAR_LLM=1")
ARQUIVO = Path(__file__).with_name("avaliacao_assistente.json")


def _chave(c: ConsultaEstruturada):
    filtros = frozenset((f.campo, json.dumps(f.valor, ensure_ascii=False)) for f in c.filtros)
    return c.tipo, c.metrica, frozenset(c.dimensoes), filtros


def test_taxa_de_acerto_da_interpretacao():
    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    provedor = provedor_padrao()
    acertos, relatorio = 0, []
    for caso in dados["casos"]:
        obtida = interpretar(provedor, caso["pergunta"], dados["valores"])
        ok = obtida is not None and _chave(obtida) == _chave(ConsultaEstruturada(**caso["esperado"]))
        acertos += ok
        relatorio.append(f"{'OK ' if ok else 'ERR'} {caso['pergunta']} -> {obtida.model_dump_json() if obtida else None}")
    taxa = acertos / len(dados["casos"])
    print("\n".join(relatorio), f"\ntaxa de acerto: {taxa:.0%} ({acertos}/{len(dados['casos'])})")
    assert taxa >= float(os.getenv("AVALIAR_LLM_MINIMO", "0"))
```

```json
{
  "valores": {
    "polo": ["Cametá", "Limoeiro", "Oeiras", "Sem polo informado"],
    "turma": ["2019", "2020", "2021", "2022", "2023", "2024", "2025", "Sem turma informada"],
    "periodo": ["2025.(1 e 2)", "2025.(3 e 4)"],
    "semestre": ["2023.1", "2023.2", "2024.1", "2024.2", "2025.1", "2025.2"],
    "renda": ["Até 1 salário mínimo", "De 1 a 2 salários mínimos", "De 2 a 3 salários mínimos", "Acima de 3 salários mínimos", "Sem resposta"],
    "motivo": ["falha_identificacao", "matricula_nao_encontrada", "sem_academico", "sem_socioeconomico"]
  },
  "casos": [
    {"pergunta": "Quantos alunos existem por polo?", "esperado": {"tipo": "agregado", "metrica": "contagem_alunos", "dimensoes": ["polo"]}},
    {"pergunta": "Mostre os alunos do polo de Cametá.", "esperado": {"tipo": "lista", "metrica": "alunos", "filtros": [{"campo": "polo", "valor": "Cametá"}]}},
    {"pergunta": "Qual a distribuição de renda familiar dos alunos?", "esperado": {"tipo": "agregado", "metrica": "contagem_alunos", "dimensoes": ["renda"]}},
    {"pergunta": "Quantos alunos ingressaram em 2020?", "esperado": {"tipo": "agregado", "metrica": "contagem_alunos", "filtros": [{"campo": "turma", "valor": "2020"}]}},
    {"pergunta": "Quais polos possuem maior evasão?", "esperado": {"tipo": "fora_do_catalogo"}},
    {"pergunta": "Mostre a evolução dos indicadores acadêmicos por semestre.", "esperado": {"tipo": "agregado", "metrica": "crg_medio_semestre", "dimensoes": ["semestre"]}},
    {"pergunta": "Compare renda familiar por polo.", "esperado": {"tipo": "agregado", "metrica": "contagem_alunos", "dimensoes": ["polo", "renda"]}},
    {"pergunta": "Liste os alunos com dados incompletos.", "esperado": {"tipo": "lista", "metrica": "alunos_incompletos"}},
    {"pergunta": "Quais alunos não possuem dados socioeconômicos?", "esperado": {"tipo": "lista", "metrica": "nao_integrados", "filtros": [{"campo": "motivo", "valor": "sem_socioeconomico"}]}},
    {"pergunta": "Quantos registros foram integrados no último lote?", "esperado": {"tipo": "operacional", "metrica": "resumo_ultimo_lote"}},
    {"pergunta": "Quais campos possuem mais respostas ausentes?", "esperado": {"tipo": "operacional", "metrica": "campos_sem_resposta"}}
  ]
}
```

Save the JSON as `tests/avaliacao_assistente.json`.

- [ ] **Step 2: Confirm it is skipped in the default suite**

Run: `pytest tests/test_assistente_avaliacao.py -v`
Expected: `1 skipped`

- [ ] **Step 3: Replace `valores` with the real ones (needs the compose database running)**

Run from `backend/` (with `backend/.env` pointing at the real database):

```bash
python -c "import json; from app.db.engine import SessionLocal; from app.services.assistente.catalogo import valores_validos; s = SessionLocal(); print(json.dumps(valores_validos(s), ensure_ascii=False, indent=2))"
```

Paste the output over the `valores` key in `tests/avaliacao_assistente.json`. It holds only answer options, polos, cohorts, periods and semesters, no student data. Fix any `esperado` value whose spelling differs from the real options (for example, the income brackets).

- [ ] **Step 4: Document**

Append to `API_README.md`:

````markdown
## Assistente de consultas — `POST /assistente/perguntar`, `POST /assistente/executar`

Pergunta em português → resposta na forma mais adequada (`dashboard`, `dinamico`, `tabela`, `texto` ou `nao_entendi`), sempre com `explicacao` (consulta interpretada, filtros, fontes, forma). Desenho: `docs/superpowers/specs/2026-09-25-assistente-consultas-design.md`.

```bash
curl -X POST localhost:8000/assistente/perguntar -H 'Content-Type: application/json' -d '{"pergunta": "Compare renda familiar por polo"}'
```

- **O que sai para o Groq:** só a pergunta, com nome e matrícula trocados por `⟨A1⟩`, e o catálogo de campos. Nunca linha de aluno nem resultado.
- **SQL:** montado pelo backend a partir da `consulta` (o modelo não escreve SQL) e executado com a role `leitor_assistente` (só `SELECT` em `aluno_integrado` e `crg_semestre_vigente`), com timeout de 5 s.
- `POST /assistente/executar {"consulta": {...}}` reexecuta uma `consulta` salva sem LLM (histórico e link compartilhado). Uma consulta fora do catálogo recebe 422.
- **Erros:** 503 LLM indisponível (sem `GROQ_API_KEY`, fora do ar, 429); 504 consulta passou de 5 s.
- **Configuração:** `GROQ_API_KEY`, `GROQ_MODELO`, `GROQ_URL` em `backend/.env` (ver `.env.example`).
- **Avaliação:** `AVALIAR_LLM=1 pytest tests/test_assistente_avaliacao.py -s` mede a taxa de acerto da interpretação.
````

In `docs/frontend_dashboards.md`, add a row to the routes table:

```markdown
| `/ia-chat` | Assistente de consultas: pergunta em português → dashboard filtrado, gráfico dinâmico, tabela ou texto, com explicação e histórico local | `docs/superpowers/specs/2026-09-25-assistente-consultas-design.md` |
```

and, after the table, the paragraph:

```markdown
### Filtros na URL

As telas que o assistente abre leem os filtros da query string: `?periodo=` (global, em qualquer tela), `/analises/bidimensional?dimensao=&polo=`, `/analises/distribuicao?polo=`, `/analises/longitudinal?polo=&turma=`. Mudar o filtro na tela atualiza a URL, então copiar o endereço compartilha a visão. Quando a tela foi aberta pelo assistente, o cabeçalho mostra a faixa "Aberto pelo assistente" com a consulta, os filtros e a fonte.
```

Append to the spec:

```markdown
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
- **Testes** em `tests/test_assistente_*.py` (padrão plano do projeto); avaliação por `AVALIAR_LLM=1` com JSON (sem PyYAML).
```

- [ ] **Step 5: Run everything and commit**

Run: `pytest && (cd frontend && npx vitest run && npm run lint && npm run build)`
Expected: tudo verde; a avaliação aparece como `skipped`.

```bash
git add tests/test_assistente_avaliacao.py tests/avaliacao_assistente.json API_README.md
git add -f docs/frontend_dashboards.md docs/superpowers/specs/2026-09-25-assistente-consultas-design.md docs/superpowers/plans/2026-09-25-assistente-consultas.md
git commit -m "docs(assistente): avaliação da interpretação, API e rotas do frontend"
```
