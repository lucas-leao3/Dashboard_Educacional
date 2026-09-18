# Tela "Dados" (inserção de lote + cobertura) — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma página `/dados` no dashboard onde o pesquisador abre um lote, envia os PDFs (que já rodam os passos 1 e 2), confere a cobertura do lote e o fecha.

**Architecture:** Um endpoint de leitura novo no backend (`GET /lotes/{id}/correspondencia`, reaproveitando `services/fechamento.py`). No frontend, lógica pura em `domain/lote.ts`, cliente de API em `data/api.ts`, orquestração sem React em `hooks/fluxoLote.ts`, componentes finos em `components/lote/`, página `pages/Dados.tsx`. O passo ativo é derivado do estado do lote na API, nunca de estado local.

**Tech Stack:** FastAPI + SQLAlchemy + pytest (backend, `.venv/bin/python -m pytest`); React 19 + react-router 7 + Tailwind 4 + vitest (frontend, `npm test` em `frontend/`). Testes de tela por `renderToString`, sem jsdom.

**Spec:** `docs/superpowers/specs/2026-09-18-tela-dados-lote-design.md`

## Global Constraints

- Nenhuma dependência nova no frontend (sem jsdom, sem testing-library).
- Nenhuma lógica de negócio no frontend que já exista no backend (correspondência vem da API).
- Escrita na API não cai em demonstração: erro é erro, com o `detail` do FastAPI em texto.
- Id de lote: `^[A-Za-z0-9_-]{3,20}$` (o mesmo do backend).
- Arquivos aceitos: `.zip` e `.pdf`, qualquer caixa. Sem `.rar`.
- Sem API (`origem === 'demonstracao'`): a página mostra só o aviso "A inserção de dados exige a API".
- Fechar exige confirmação (injetável) e é definitivo.
- Commits: mensagem em português no estilo do repo (`feat:`, `docs:`, `test:`), terminando com `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Comitar **só os arquivos da tarefa** (há alterações antigas não relacionadas na árvore de trabalho — nunca `git add -A`).
- Todos os comandos abaixo rodam da raiz do repo, salvo indicação.

---

### Task 1: Backend — `GET /lotes/{id}/correspondencia`

**Files:**
- Modify: `backend/app/services/fechamento.py` (função `_escrever_correspondencia_csv`, ~linhas 97–134)
- Modify: `backend/app/schemas/lotes.py`
- Modify: `backend/app/api/lotes.py`
- Test: `tests/test_lotes.py`

**Interfaces:**
- Produces: `fechamento.correspondencia(alunos: list[AlunoOut], excecoes: list[Excecao]) -> list[dict]` com chaves `matricula: int`, `nome: str | None`, `academico: bool`, `socioeconomico: bool`, `faltando: str` (`""`, `"Academico"`, `"SocioEconomico"`, `"Ambos"`), ordenada por matrícula. `fechamento.correspondencia_do_lote(session, lote_id) -> list[dict]`. Rota `GET /lotes/{id}/correspondencia` → `list[CorrespondenciaOut]`.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `tests/test_lotes.py` (o helper `_lote_rodado` já existe nesse arquivo e cria os quatro casos 100/200/300/400):

```python
# ---------------------------------------------------------------------------
# GET /lotes/{id}/correspondencia: a correspondencia.csv como JSON
# ---------------------------------------------------------------------------

async def test_correspondencia_devolve_os_quatro_casos_ordenados(client, lote, db_engine):
    _lote_rodado(db_engine, lote)
    resposta = await client.get(f"/lotes/{lote}/correspondencia")
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert [l["matricula"] for l in corpo] == [100, 200, 300, 400]
    assert corpo[0] == {"matricula": 100, "nome": "Ana", "academico": True, "socioeconomico": True, "faltando": ""}
    assert (corpo[1]["academico"], corpo[1]["socioeconomico"], corpo[1]["faltando"]) == (False, True, "Academico")
    assert (corpo[2]["academico"], corpo[2]["socioeconomico"], corpo[2]["faltando"]) == (True, False, "SocioEconomico")
    assert (corpo[3]["academico"], corpo[3]["socioeconomico"], corpo[3]["faltando"]) == (False, False, "Ambos")


async def test_correspondencia_de_lote_inexistente_da_404(client):
    assert (await client.get("/lotes/L99/correspondencia")).status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_lotes.py -q -k correspondencia`
Expected: 1 failed (`assert 404 == 200`), 1 passed (o 404 já acontece por a rota não existir — passa a passar pelo motivo certo no Step 4).

- [ ] **Step 3: Extrair `correspondencia()` e criar a rota**

Em `backend/app/services/fechamento.py`, substituir a função `_escrever_correspondencia_csv` inteira por:

```python
def correspondencia(alunos: list[AlunoOut], excecoes: list[Excecao]) -> list[dict]:
    """Uma linha por matrícula: tem acadêmico? tem socioeconômico? O que falta?
    Quem está em aluno_vigente tem os dois, salvo exceção que diga o contrário.
    É a fonte tanto do correspondencia.csv quanto de GET /lotes/{id}/correspondencia."""
    info: dict[int, dict] = {}
    for aluno in alunos:
        registro = info.setdefault(aluno.matricula, {"nome": None, "academico": True, "socio": True})
        if aluno.nome:
            registro["nome"] = aluno.nome
    for excecao in excecoes:
        if excecao.matricula is None:
            continue
        registro = info.setdefault(excecao.matricula, {"nome": None, "academico": True, "socio": True})
        if excecao.motivo == "sem_academico":
            registro["academico"] = False
        elif excecao.motivo == "sem_socioeconomico":
            registro["socio"] = False

    linhas = []
    for matricula in sorted(info):
        registro = info[matricula]
        academico_ok, socio_ok = registro["academico"], registro["socio"]
        if academico_ok and socio_ok:
            faltando = ""
        elif not academico_ok and not socio_ok:
            faltando = "Ambos"
        elif not academico_ok:
            faltando = "Academico"
        else:
            faltando = "SocioEconomico"
        linhas.append({
            "matricula": matricula, "nome": registro["nome"],
            "academico": academico_ok, "socioeconomico": socio_ok, "faltando": faltando,
        })
    return linhas


def _escrever_correspondencia_csv(caminho: Path, linhas: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["Matricula", "Nome", "Academico", "SocioEconomico", "Dado_Faltando"])
        for l in linhas:
            escritor.writerow([
                l["matricula"], l["nome"] or "",
                "Sim" if l["academico"] else "Não", "Sim" if l["socioeconomico"] else "Não", l["faltando"],
            ])


def _alunos_e_excecoes(session: Session, lote_id: str) -> tuple[list[AlunoOut], list[Excecao]]:
    excecoes = session.execute(
        select(Excecao).join(Ingestao, Ingestao.id == Excecao.ingestao_id).where(Ingestao.lote_id == lote_id)
    ).scalars().all()
    alunos = [
        AlunoOut.model_validate(linha)
        for linha in session.execute(
            select(aluno_vigente).order_by(aluno_vigente.c.matricula, aluno_vigente.c.periodo)
        ).all()
    ]
    return alunos, list(excecoes)


def correspondencia_do_lote(session: Session, lote_id: str) -> list[dict]:
    alunos, excecoes = _alunos_e_excecoes(session, lote_id)
    return correspondencia(alunos, excecoes)
```

Ainda em `fechamento.py`, dentro de `fechar_lote`, trocar o bloco que monta `excecoes` e `alunos` (as duas consultas `select(Excecao)...` e `AlunoOut.model_validate(...)`) por uma linha, e ajustar a chamada do CSV:

```python
    alunos, excecoes = _alunos_e_excecoes(session, lote.id)
```
```python
    _escrever_correspondencia_csv(processada / "correspondencia.csv", correspondencia(alunos, excecoes))
```

Em `backend/app/schemas/lotes.py`, acrescentar ao fim:

```python
class CorrespondenciaOut(BaseModel):
    matricula: int
    nome: str | None
    academico: bool
    socioeconomico: bool
    faltando: Literal["", "Academico", "SocioEconomico", "Ambos"]
```

Em `backend/app/api/lotes.py`, incluir `CorrespondenciaOut` no import de `app.schemas.lotes` e acrescentar ao fim:

```python
@router.get("/{lote_id}/correspondencia", response_model=list[CorrespondenciaOut])
def listar_correspondencia(lote_id: str, session: Session = Depends(get_session)):
    """GET /lotes/{id}/correspondencia -> uma linha por matrícula: tem acadêmico?
    tem socioeconômico? o que falta? O mesmo conteúdo do correspondencia.csv."""
    if session.get(Lote, lote_id) is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return fechamento.correspondencia_do_lote(session, lote_id)
```

- [ ] **Step 4: Rodar toda a suíte do backend**

Run: `.venv/bin/python -m pytest -q`
Expected: 90 passed (88 anteriores + 2). Os testes de `fechar` que leem `correspondencia.csv` continuam passando — a saída do CSV não mudou.

- [ ] **Step 5: Documentar a rota e comitar**

Em `API_README.md`, logo depois da seção `### 11. POST /lotes/{id}/fechar` (antes de `## Fluxo de um lote`), acrescentar:

```markdown
### 12. `GET /lotes/{id}/correspondencia`
O `correspondencia.csv` como JSON: uma linha por matrícula, ordenada. É o que a tela **Dados** do dashboard mostra na "Cobertura do lote".

```json
[{"matricula": 202016040001, "nome": "Ana", "academico": true, "socioeconomico": false, "faltando": "SocioEconomico"}]
```
`faltando` ∈ `""`, `"Academico"`, `"SocioEconomico"`, `"Ambos"`. `404` se o lote não existe.
```

Na tabela de visão geral do mesmo arquivo, trocar a contagem de testes para 90 (linhas "88 testes automatizados…" e "**88 passed**").

```bash
git add backend/app/services/fechamento.py backend/app/schemas/lotes.py backend/app/api/lotes.py tests/test_lotes.py API_README.md
git commit -m "feat: GET /lotes/{id}/correspondencia reaproveitando o fechamento

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Frontend — tipos e cliente de API de escrita

**Files:**
- Modify: `frontend/src/data/tipos.ts` (interface `Lote`, ~linha 50)
- Modify: `frontend/src/data/api.ts`
- Test: `frontend/src/data/api.test.ts`

**Interfaces:**
- Produces (em `tipos.ts`): `Lote.fechado_em: string | null`; `HistoricosOut`; `Correspondencia`.
- Produces (em `api.ts`): `class ErroApi extends Error { status: number; detail: string }`; `interface NovoLote { id: string; periodos_cobertos: string[]; executado_por: string | null }`; `abrirLote(dados: NovoLote, opcoes?): Promise<Lote>`; `enviarHistoricos(id: string, arquivos: File[], opcoes?): Promise<HistoricosOut>`; `fecharLote(id: string, opcoes?): Promise<Lote>`; `carregarLote(id: string, opcoes?): Promise<Lote>`; `carregarCorrespondencia(id: string, opcoes?): Promise<Correspondencia[]>`. `opcoes` é o mesmo `{ baseUrl?, fetchFn? }` das funções existentes.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `frontend/src/data/api.test.ts`:

```ts
import { ErroApi, abrirLote, carregarCorrespondencia, enviarHistoricos, fecharLote } from './api';

const LOTE = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null,
  periodos_cobertos: ['2026.1'], executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {},
};

describe('escrita na API (abrirLote, enviarHistoricos, fecharLote)', () => {
  test('abrirLote faz POST /lotes com JSON e devolve o lote', async () => {
    let capturado: { url: string; init?: RequestInit } | null = null;
    const fetchFalso = async (url: string | URL | Request, init?: RequestInit) => {
      capturado = { url: String(url), init };
      return new Response(JSON.stringify(LOTE), { status: 201 });
    };
    const lote = await abrirLote({ id: '2026-09-L01', periodos_cobertos: ['2026.1'], executado_por: 'Edi' }, { baseUrl: '/api', fetchFn: fetchFalso });
    expect(lote.id).toBe('2026-09-L01');
    expect(capturado!.url).toBe('/api/lotes');
    expect(capturado!.init?.method).toBe('POST');
    expect(JSON.parse(String(capturado!.init?.body))).toEqual({ id: '2026-09-L01', periodos_cobertos: ['2026.1'], executado_por: 'Edi' });
  });

  test('enviarHistoricos manda multipart com um campo "arquivos" por arquivo e executar=true', async () => {
    let capturado: { url: string; init?: RequestInit } | null = null;
    const fetchFalso = async (url: string | URL | Request, init?: RequestInit) => {
      capturado = { url: String(url), init };
      return new Response(JSON.stringify({ lote: '2026-09-L01', gravados: ['a.pdf'], ja_existiam: [], ignorados: [], sincronizar: null, atualizar_crg: null }), { status: 200 });
    };
    const arquivos = [new File(['x'], 'a.pdf'), new File(['y'], 'b.zip')];
    const saida = await enviarHistoricos('2026-09-L01', arquivos, { baseUrl: '/api', fetchFn: fetchFalso });
    expect(saida.gravados).toEqual(['a.pdf']);
    expect(capturado!.url).toBe('/api/lotes/2026-09-L01/historicos?executar=true');
    const form = capturado!.init?.body as FormData;
    expect(form.getAll('arquivos').map((f) => (f as File).name)).toEqual(['a.pdf', 'b.zip']);
  });

  test('erro HTTP vira ErroApi com o detail do FastAPI', async () => {
    const fetchFalso = async () => new Response(JSON.stringify({ detail: 'Passo 2 já foi executado' }), { status: 409 });
    await expect(fecharLote('2026-09-L01', { baseUrl: '/api', fetchFn: fetchFalso })).rejects.toMatchObject({ status: 409, detail: 'Passo 2 já foi executado' });
  });

  test('fetch rejeitado vira ErroApi "Sem resposta da API"', async () => {
    const fetchFalso = async () => { throw new Error('rede'); };
    const erro = await abrirLote({ id: 'x', periodos_cobertos: [], executado_por: null }, { baseUrl: '/api', fetchFn: fetchFalso }).catch((e) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.status).toBe(0);
    expect(erro.detail).toBe('Sem resposta da API');
  });

  test('sem baseUrl a escrita falha em vez de cair na demonstração', async () => {
    await expect(fecharLote('x', { baseUrl: '' })).rejects.toBeInstanceOf(ErroApi);
  });

  test('carregarCorrespondencia devolve as linhas', async () => {
    const linhas = [{ matricula: 100, nome: 'Ana', academico: true, socioeconomico: true, faltando: '' }];
    const fetchFalso = async () => new Response(JSON.stringify(linhas), { status: 200 });
    expect(await carregarCorrespondencia('2026-09-L01', { baseUrl: '/api', fetchFn: fetchFalso })).toEqual(linhas);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/data/api.test.ts`
Expected: falha de import (`ErroApi`, `abrirLote`… não exportados).

- [ ] **Step 3: Implementar tipos e cliente**

Em `frontend/src/data/tipos.ts`, na interface `Lote`, acrescentar depois de `executado_em: string;`:

```ts
  /** Preenchido por POST /lotes/{id}/fechar. Fechado não se reabre. */
  fechado_em: string | null;
```

E ao fim do arquivo:

```ts
/** Espelha `HistoricosOut` (backend/app/schemas/lotes.py). */
export interface HistoricosOut {
  lote: string;
  gravados: string[];
  ja_existiam: string[];
  ignorados: string[];
  /** Contadores do passo, "ja_executado" se já tinha rodado, null se não se pediu ?executar. */
  sincronizar: Record<string, unknown> | 'ja_executado' | null;
  atualizar_crg: Record<string, unknown> | 'ja_executado' | null;
}

/** Espelha `CorrespondenciaOut`: uma linha por matrícula. */
export interface Correspondencia {
  matricula: number;
  nome: string | null;
  academico: boolean;
  socioeconomico: boolean;
  faltando: '' | 'Academico' | 'SocioEconomico' | 'Ambos';
}
```

Em `frontend/src/data/api.ts`, trocar o import de tipos por `import type { Correspondencia, HistoricosOut, Lote, Registro } from './tipos';` e acrescentar ao fim:

```ts
/** Erro de uma chamada de escrita: `detail` é o texto que o FastAPI mandou. */
export class ErroApi extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = 'ErroApi';
  }
}

export interface NovoLote {
  id: string;
  periodos_cobertos: string[];
  executado_por: string | null;
}

/**
 * Chamada que NÃO cai em demonstração: escrever sem API é erro. Erro HTTP vira
 * ErroApi com o `detail` do corpo; fetch rejeitado vira "Sem resposta da API".
 */
async function chamar<T>(caminho: string, init: RequestInit, opcoes: Opcoes): Promise<T> {
  const baseUrl = (opcoes.baseUrl ?? import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
  const fetchFn = opcoes.fetchFn ?? fetch;
  if (!baseUrl) throw new ErroApi(0, 'API não configurada');
  let resposta: Response;
  try {
    resposta = await fetchFn(`${baseUrl}${caminho}`, { ...init, headers: { Accept: 'application/json', ...(init.headers ?? {}) } });
  } catch {
    throw new ErroApi(0, 'Sem resposta da API');
  }
  if (!resposta.ok) {
    let detail = `HTTP ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (typeof corpo?.detail === 'string') detail = corpo.detail;
      else if (corpo?.detail) detail = JSON.stringify(corpo.detail);
    } catch { /* corpo não-JSON: fica o status */ }
    throw new ErroApi(resposta.status, detail);
  }
  return (await resposta.json()) as T;
}

export function abrirLote(dados: NovoLote, opcoes: Opcoes = {}): Promise<Lote> {
  return chamar<Lote>('/lotes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados) }, opcoes);
}

export function enviarHistoricos(id: string, arquivos: File[], opcoes: Opcoes = {}): Promise<HistoricosOut> {
  const form = new FormData();
  for (const arquivo of arquivos) form.append('arquivos', arquivo, arquivo.name);
  return chamar<HistoricosOut>(`/lotes/${encodeURIComponent(id)}/historicos?executar=true`, { method: 'POST', body: form }, opcoes);
}

export function fecharLote(id: string, opcoes: Opcoes = {}): Promise<Lote> {
  return chamar<Lote>(`/lotes/${encodeURIComponent(id)}/fechar`, { method: 'POST' }, opcoes);
}

export function carregarLote(id: string, opcoes: Opcoes = {}): Promise<Lote> {
  return chamar<Lote>(`/lotes/${encodeURIComponent(id)}`, {}, opcoes);
}

export function carregarCorrespondencia(id: string, opcoes: Opcoes = {}): Promise<Correspondencia[]> {
  return chamar<Correspondencia[]>(`/lotes/${encodeURIComponent(id)}/correspondencia`, {}, opcoes);
}
```

- [ ] **Step 4: Rodar os testes e o typecheck**

Run: `cd frontend && npx vitest run src/data/api.test.ts && npx tsc -b`
Expected: todos os testes de `api.test.ts` passam; `tsc` sem erros. Se o `tsc` reclamar de `fechado_em` faltando no objeto de teste de `carregarLotes` já existente, acrescentar `fechado_em: null` a esse literal.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/data/tipos.ts frontend/src/data/api.ts frontend/src/data/api.test.ts
git commit -m "feat(frontend): cliente de API para abrir, enviar e fechar lote

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Frontend — lógica pura do lote (`domain/lote.ts`)

**Files:**
- Create: `frontend/src/domain/lote.ts`
- Test: `frontend/src/domain/lote.test.ts`

**Interfaces:**
- Produces: `type Passo = 1 | 2 | 3 | null`; `passoAtual(lote: Lote | null): Passo`; `PADRAO_ID: RegExp`; `validarIdLote(id: string): boolean`; `sugerirIdLote(hoje: Date, lotes: Lote[]): string`; `filtrarArquivosAceitos<T extends { name: string }>(arquivos: T[]): { aceitos: T[]; rejeitados: T[] }`; `resumirCobertura(linhas: Correspondencia[]): { total: number; completos: number; faltaAcademico: number; faltaSocio: number; faltaAmbos: number }`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `frontend/src/domain/lote.test.ts`:

```ts
import { describe, expect, test } from 'vitest';
import type { Lote } from '../data/tipos';
import { filtrarArquivosAceitos, passoAtual, resumirCobertura, sugerirIdLote, validarIdLote } from './lote';

function lote(parcial: Partial<Lote> = {}): Lote {
  return {
    id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2026.1'],
    executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {}, ...parcial,
  };
}
const ingestao = (passo: number) => ({ id: passo, passo, arquivo_sha256: null, executado_em: '2026-09-12T10:00:00Z', registros_lidos: 0, registros_aceitos: 0, registros_rejeitados: 0 });

describe('passoAtual', () => {
  test('sem lote -> 1 (abrir)', () => expect(passoAtual(null)).toBe(1));
  test('lote sem ingestões -> 2 (enviar e rodar)', () => expect(passoAtual(lote())).toBe(2));
  test('só passo 1 feito -> ainda 2', () => expect(passoAtual(lote({ ingestoes: [ingestao(1)] }))).toBe(2));
  test('passos 1 e 2 feitos, aberto -> 3 (fechar)', () => expect(passoAtual(lote({ ingestoes: [ingestao(1), ingestao(2)] }))).toBe(3));
  test('fechado -> null', () => expect(passoAtual(lote({ ingestoes: [ingestao(1), ingestao(2)], fechado_em: '2026-09-12T11:00:00Z' }))).toBeNull());
});

describe('validarIdLote', () => {
  test('aceita o padrão AAAA-MM-Lnn', () => expect(validarIdLote('2026-09-L01')).toBe(true));
  test('recusa barra, espaço, curto e longo', () => {
    for (const id of ['../x', 'com espaco', 'ab', 'a'.repeat(21)]) expect(validarIdLote(id)).toBe(false);
  });
});

describe('sugerirIdLote', () => {
  const hoje = new Date(2026, 8, 18); // setembro
  test('sem lotes no mês -> L01', () => expect(sugerirIdLote(hoje, [])).toBe('2026-09-L01'));
  test('com L01 e L02 no mês -> L03', () => {
    expect(sugerirIdLote(hoje, [lote({ id: '2026-09-L01' }), lote({ id: '2026-09-L02' })])).toBe('2026-09-L03');
  });
  test('lote de outro mês não conta', () => expect(sugerirIdLote(hoje, [lote({ id: '2026-08-L07' })])).toBe('2026-09-L01'));
});

describe('filtrarArquivosAceitos', () => {
  test('aceita .zip e .pdf em qualquer caixa e rejeita o resto pelo nome', () => {
    const r = filtrarArquivosAceitos([{ name: 'a.pdf' }, { name: 'B.PDF' }, { name: 'h.zip' }, { name: 'x.rar' }, { name: 'nota.txt' }]);
    expect(r.aceitos.map((a) => a.name)).toEqual(['a.pdf', 'B.PDF', 'h.zip']);
    expect(r.rejeitados.map((a) => a.name)).toEqual(['x.rar', 'nota.txt']);
  });
});

describe('resumirCobertura', () => {
  test('conta os quatro casos', () => {
    const resumo = resumirCobertura([
      { matricula: 100, nome: 'Ana', academico: true, socioeconomico: true, faltando: '' },
      { matricula: 200, nome: null, academico: false, socioeconomico: true, faltando: 'Academico' },
      { matricula: 300, nome: null, academico: true, socioeconomico: false, faltando: 'SocioEconomico' },
      { matricula: 400, nome: null, academico: false, socioeconomico: false, faltando: 'Ambos' },
    ]);
    expect(resumo).toEqual({ total: 4, completos: 1, faltaAcademico: 1, faltaSocio: 1, faltaAmbos: 1 });
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/domain/lote.test.ts`
Expected: falha de import (`./lote` não existe).

- [ ] **Step 3: Implementar**

Criar `frontend/src/domain/lote.ts`:

```ts
import type { Correspondencia, Lote } from '../data/tipos';

/** Passo da inserção. Derivado só do que a API devolve (spec, "Máquina de estados"). */
export type Passo = 1 | 2 | 3 | null;

export function passoAtual(lote: Lote | null): Passo {
  if (!lote) return 1;
  if (lote.fechado_em) return null;
  const passos = new Set(lote.ingestoes.map((i) => i.passo));
  return passos.has(1) && passos.has(2) ? 3 : 2;
}

/** O mesmo padrão de backend/app/schemas/lotes.py (LoteCreate.id). */
export const PADRAO_ID = /^[A-Za-z0-9_-]{3,20}$/;

export function validarIdLote(id: string): boolean {
  return PADRAO_ID.test(id);
}

/** AAAA-MM-Lnn com o mês de `hoje`; nn = maior sequência já usada no mês + 1. */
export function sugerirIdLote(hoje: Date, lotes: Lote[]): string {
  const prefixo = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-L`;
  const maior = lotes
    .map((l) => l.id)
    .filter((id) => id.startsWith(prefixo))
    .map((id) => Number(id.slice(prefixo.length)))
    .filter((n) => Number.isInteger(n))
    .reduce((m, n) => Math.max(m, n), 0);
  return `${prefixo}${String(maior + 1).padStart(2, '0')}`;
}

const EXTENSOES = ['.pdf', '.zip'];

/** Separa pelo nome o que o backend aceita (.pdf/.zip, qualquer caixa) do que não. */
export function filtrarArquivosAceitos<T extends { name: string }>(arquivos: T[]): { aceitos: T[]; rejeitados: T[] } {
  const aceitos: T[] = [];
  const rejeitados: T[] = [];
  for (const a of arquivos) {
    (EXTENSOES.some((ext) => a.name.toLowerCase().endsWith(ext)) ? aceitos : rejeitados).push(a);
  }
  return { aceitos, rejeitados };
}

export interface ResumoCobertura {
  total: number;
  completos: number;
  faltaAcademico: number;
  faltaSocio: number;
  faltaAmbos: number;
}

export function resumirCobertura(linhas: Correspondencia[]): ResumoCobertura {
  const resumo: ResumoCobertura = { total: linhas.length, completos: 0, faltaAcademico: 0, faltaSocio: 0, faltaAmbos: 0 };
  for (const l of linhas) {
    if (l.faltando === '') resumo.completos++;
    else if (l.faltando === 'Academico') resumo.faltaAcademico++;
    else if (l.faltando === 'SocioEconomico') resumo.faltaSocio++;
    else resumo.faltaAmbos++;
  }
  return resumo;
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/domain/lote.test.ts`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/domain/lote.ts frontend/src/domain/lote.test.ts
git commit -m "feat(frontend): máquina de estados do lote e regras puras da tela Dados

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Frontend — `DadosProvider` com `lotes` e `recarregar`

**Files:**
- Modify: `frontend/src/hooks/DadosProvider.tsx`
- Modify: `frontend/src/pages/paginas.test.tsx` (o literal `dados: Dados`, ~linha 14)

**Interfaces:**
- Produces: `Dados.lotes: Lote[]` (todos, na ordem da API); `Dados.recarregar: () => Promise<void>`. `Dados.lote` (o vigente) continua existindo.

- [ ] **Step 1: Atualizar o contexto falso dos testes de página (vai falhar no typecheck)**

Em `frontend/src/pages/paginas.test.tsx`, no literal `const dados: Dados = {...}`, acrescentar `lotes: [], recarregar: async () => {},` depois de `lote: null,`.

Run: `cd frontend && npx tsc -b`
Expected: erro — `lotes`/`recarregar` não existem em `Dados`.

- [ ] **Step 2: Implementar**

Em `frontend/src/hooks/DadosProvider.tsx`:

Na interface `Dados`, depois de `lote: Lote | null;`:

```ts
  /** Todos os lotes, na ordem da API (executado_em). Para o seletor da tela Dados. */
  lotes: Lote[];
  /** Refaz as duas cargas. Chamado depois de abrir/enviar/fechar um lote. */
  recarregar: () => Promise<void>;
```

Substituir o `useEffect` e os `useState` de `lote` pelo bloco abaixo (mantendo `registros`, `origem`, `carregando`, `periodo` como estão):

```ts
  const [lotes, setLotes] = useState<Lote[]>([]);

  const recarregar = useCallback(async () => {
    const [r, ls] = await Promise.all([carregarRegistros(), carregarLotes()]);
    setRegistros(r.registros);
    setOrigem(r.origem);
    setLotes(ls);
    setCarregando(false);
  }, []);

  useEffect(() => {
    let ativo = true;
    Promise.all([carregarRegistros(), carregarLotes()]).then(([r, ls]) => {
      if (!ativo) return;
      setRegistros(r.registros);
      setOrigem(r.origem);
      setLotes(ls);
      setCarregando(false);
    });
    return () => { ativo = false; };
  }, []);

  const lote = useMemo(() => loteVigente(lotes), [lotes]);
```

Importar `useCallback` de `react`. No `useMemo` final que monta `valor`, acrescentar `lotes, recarregar` ao objeto e ao array de dependências.

- [ ] **Step 3: Typecheck e suíte inteira**

Run: `cd frontend && npx tsc -b && npx vitest run`
Expected: sem erros de tipo; 62 + os novos de Tasks 2–3 passando.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/DadosProvider.tsx frontend/src/pages/paginas.test.tsx
git commit -m "feat(frontend): DadosProvider expõe todos os lotes e recarregar()

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Frontend — orquestração `criarFluxoLote`

**Files:**
- Create: `frontend/src/hooks/fluxoLote.ts`
- Test: `frontend/src/hooks/fluxoLote.test.ts`

**Interfaces:**
- Consumes: `ErroApi`, `NovoLote` (Task 2); tipos `Lote`, `HistoricosOut`.
- Produces: `interface ApiLote { abrirLote(d: NovoLote): Promise<Lote>; enviarHistoricos(id: string, arquivos: File[]): Promise<HistoricosOut>; fecharLote(id: string): Promise<Lote> }`; `type Resultado<T> = { ok: true; dados: T } | { ok: false; erro: string | null; status: number }`; `TEXTO_FECHAR: string`; `criarFluxoLote({ api, recarregar, confirmar? }): { abrir(d: NovoLote): Promise<Resultado<Lote>>; enviar(id: string, arquivos: File[]): Promise<Resultado<HistoricosOut>>; fechar(id: string): Promise<Resultado<Lote>> }`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `frontend/src/hooks/fluxoLote.test.ts`:

```ts
import { describe, expect, test } from 'vitest';
import { ErroApi } from '../data/api';
import type { Lote } from '../data/tipos';
import { criarFluxoLote } from './fluxoLote';
import type { ApiLote } from './fluxoLote';

const LOTE: Lote = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2026.1'],
  executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {},
};
const SAIDA = { lote: '2026-09-L01', gravados: ['a.pdf'], ja_existiam: [], ignorados: [], sincronizar: null, atualizar_crg: null };

function apiFalsa(sobrescrever: Partial<ApiLote> = {}): ApiLote & { chamadas: string[] } {
  const chamadas: string[] = [];
  return {
    chamadas,
    abrirLote: async () => { chamadas.push('abrir'); return LOTE; },
    enviarHistoricos: async () => { chamadas.push('enviar'); return SAIDA; },
    fecharLote: async () => { chamadas.push('fechar'); return { ...LOTE, fechado_em: '2026-09-12T11:00:00Z' }; },
    ...sobrescrever,
  };
}

describe('criarFluxoLote', () => {
  test('caso feliz: cada ação chama recarregar depois de dar certo', async () => {
    const api = apiFalsa();
    let recarregado = 0;
    const fluxo = criarFluxoLote({ api, recarregar: async () => { recarregado++; }, confirmar: () => true });
    expect(await fluxo.abrir({ id: LOTE.id, periodos_cobertos: ['2026.1'], executado_por: null })).toEqual({ ok: true, dados: LOTE });
    expect(await fluxo.enviar(LOTE.id, [new File(['x'], 'a.pdf')])).toEqual({ ok: true, dados: SAIDA });
    expect((await fluxo.fechar(LOTE.id)).ok).toBe(true);
    expect(recarregado).toBe(3);
    expect(api.chamadas).toEqual(['abrir', 'enviar', 'fechar']);
  });

  test('erro da API vira { ok: false, erro: detail, status } e não recarrega', async () => {
    const api = apiFalsa({ enviarHistoricos: async () => { throw new ErroApi(409, 'Passo 2 já foi executado'); } });
    let recarregado = 0;
    const fluxo = criarFluxoLote({ api, recarregar: async () => { recarregado++; } });
    expect(await fluxo.enviar(LOTE.id, [])).toEqual({ ok: false, erro: 'Passo 2 já foi executado', status: 409 });
    expect(recarregado).toBe(0);
  });

  test('fechar sem confirmação não chama a API', async () => {
    const api = apiFalsa();
    const fluxo = criarFluxoLote({ api, recarregar: async () => {}, confirmar: () => false });
    expect(await fluxo.fechar(LOTE.id)).toEqual({ ok: false, erro: null, status: 0 });
    expect(api.chamadas).toEqual([]);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/hooks/fluxoLote.test.ts`
Expected: falha de import (`./fluxoLote` não existe).

- [ ] **Step 3: Implementar**

Criar `frontend/src/hooks/fluxoLote.ts`:

```ts
import { ErroApi } from '../data/api';
import type { NovoLote } from '../data/api';
import type { HistoricosOut, Lote } from '../data/tipos';

/** O que a orquestração precisa da API — injetável para teste. */
export interface ApiLote {
  abrirLote(dados: NovoLote): Promise<Lote>;
  enviarHistoricos(id: string, arquivos: File[]): Promise<HistoricosOut>;
  fecharLote(id: string): Promise<Lote>;
}

export type Resultado<T> = { ok: true; dados: T } | { ok: false; erro: string | null; status: number };

export const TEXTO_FECHAR = 'Fechar é definitivo: o lote não se reabre nem recebe mais PDFs. Confirmar?';

interface Deps {
  api: ApiLote;
  recarregar: () => Promise<void>;
  /** Confirmação do fechar. Padrão: window.confirm. */
  confirmar?: () => boolean;
}

/**
 * As três ações da tela Dados, sem React: cada uma chama a API, recarrega o
 * DadosProvider se deu certo e devolve um Resultado que a tela só exibe.
 * A máquina de estados avança pelo recarregar, nunca por estado local.
 */
export function criarFluxoLote({ api, recarregar, confirmar = () => window.confirm(TEXTO_FECHAR) }: Deps) {
  async function executar<T>(acao: () => Promise<T>): Promise<Resultado<T>> {
    try {
      const dados = await acao();
      await recarregar();
      return { ok: true, dados };
    } catch (e) {
      if (e instanceof ErroApi) return { ok: false, erro: e.detail, status: e.status };
      return { ok: false, erro: String(e), status: 0 };
    }
  }
  return {
    abrir: (dados: NovoLote) => executar(() => api.abrirLote(dados)),
    enviar: (id: string, arquivos: File[]) => executar(() => api.enviarHistoricos(id, arquivos)),
    fechar: async (id: string): Promise<Resultado<Lote>> =>
      confirmar() ? executar(() => api.fecharLote(id)) : { ok: false, erro: null, status: 0 },
  };
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/hooks/fluxoLote.test.ts`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/fluxoLote.ts frontend/src/hooks/fluxoLote.test.ts
git commit -m "feat(frontend): orquestração abrir/enviar/fechar do lote sem React

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Frontend — `CoberturaLote`

**Files:**
- Create: `frontend/src/components/lote/CoberturaLote.tsx`
- Test: `frontend/src/components/lote/CoberturaLote.test.tsx`

**Interfaces:**
- Consumes: `resumirCobertura` (Task 3); `KpiCard` (`components/ui/KpiCard.tsx`, props `label`, `value`, `hint?`, `tone?`); tipos `Lote`, `Correspondencia`.
- Produces: `<CoberturaLote lote={Lote} linhas={Correspondencia[] | null} erro={string | null} />`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `frontend/src/components/lote/CoberturaLote.test.tsx`:

```tsx
import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import type { ReactElement } from 'react';
import type { Correspondencia, Lote } from '../../data/tipos';
import CoberturaLote from './CoberturaLote';

const LOTE: Lote = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2025.2', '2026.1'],
  executado_por: 'Edinaldo', observacao: null,
  ingestoes: [
    { id: 1, passo: 1, arquivo_sha256: 'abc', executado_em: '2026-09-12T10:00:00Z', registros_lidos: 103, registros_aceitos: 103, registros_rejeitados: 0 },
    { id: 2, passo: 2, arquivo_sha256: null, executado_em: '2026-09-12T10:05:00Z', registros_lidos: 56, registros_aceitos: 56, registros_rejeitados: 0 },
  ],
  excecoes_por_motivo: { sem_academico: 47 },
};
const LINHAS: Correspondencia[] = [
  { matricula: 100, nome: 'Ana', academico: true, socioeconomico: true, faltando: '' },
  { matricula: 200, nome: 'Beto', academico: false, socioeconomico: true, faltando: 'Academico' },
  { matricula: 300, nome: null, academico: true, socioeconomico: false, faltando: 'SocioEconomico' },
  { matricula: 400, nome: null, academico: false, socioeconomico: false, faltando: 'Ambos' },
];
const render = (el: ReactElement) => renderToString(el).replace(/<!-- -->/g, '');

describe('CoberturaLote', () => {
  test('mostra os KPIs, as exceções por motivo e uma linha por matrícula', () => {
    const html = render(<CoberturaLote lote={LOTE} linhas={LINHAS} erro={null} />);
    expect(html).toContain('Alunos no lote');
    expect(html).toMatch(/Completos[^]*?>1</);
    expect(html).toContain('sem_academico');
    expect(html).toContain('47');
    for (const m of ['100', '200', '300', '400']) expect(html).toContain(m);
    expect(html).toContain('Ana');
    expect(html).toContain('Ambos');
  });
  test('sem linhas ainda mostra "carregando"; com erro mostra a mensagem', () => {
    expect(render(<CoberturaLote lote={LOTE} linhas={null} erro={null} />)).toContain('Carregando');
    expect(render(<CoberturaLote lote={LOTE} linhas={null} erro="HTTP 500" />)).toContain('Não foi possível carregar a correspondência');
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/components/lote/CoberturaLote.test.tsx`
Expected: falha de import.

- [ ] **Step 3: Implementar**

Criar `frontend/src/components/lote/CoberturaLote.tsx`:

```tsx
import KpiCard from '../ui/KpiCard';
import { resumirCobertura } from '../../domain/lote';
import type { Correspondencia, Lote } from '../../data/tipos';

interface Props {
  lote: Lote;
  /** null = ainda carregando. */
  linhas: Correspondencia[] | null;
  erro: string | null;
}

const ROTULO_FALTANDO: Record<Correspondencia['faltando'], string> = {
  '': '—', Academico: 'Acadêmico', SocioEconomico: 'Socioeconômico', Ambos: 'Ambos',
};

/** "Cobertura do lote": o corte transversal (governança §4.7) na tela. */
export default function CoberturaLote({ lote, linhas, erro }: Props) {
  const resumo = linhas ? resumirCobertura(linhas) : null;
  const excecoes = Object.entries(lote.excecoes_por_motivo);

  return (
    <section className="space-y-4" aria-labelledby="cobertura-titulo">
      <h2 id="cobertura-titulo" className="text-base font-bold text-slate-800">Cobertura do lote {lote.id}</h2>

      {resumo && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <KpiCard label="Alunos no lote" value={resumo.total} />
          <KpiCard label="Completos" value={resumo.completos} hint="acadêmico + socioeconômico" />
          <KpiCard label="Falta acadêmico" value={resumo.faltaAcademico} tone={resumo.faltaAcademico ? 'atencao' : undefined} hint="sem histórico em PDF" />
          <KpiCard label="Falta socioeconômico" value={resumo.faltaSocio} tone={resumo.faltaSocio ? 'atencao' : undefined} hint="sem resposta no FasiTech" />
          <KpiCard label="Falta ambos" value={resumo.faltaAmbos} tone={resumo.faltaAmbos ? 'critico' : undefined} />
        </div>
      )}

      <div className="rounded-2xl bg-white border border-slate-200/80 p-5 text-sm">
        <h3 className="font-semibold text-slate-700 mb-2">Ingestões e exceções</h3>
        <ul className="text-slate-600 space-y-1">
          {lote.ingestoes.map((i) => (
            <li key={i.id}>Passo {i.passo}: {i.registros_lidos} lidos, {i.registros_aceitos} aceitos, {i.registros_rejeitados} rejeitados</li>
          ))}
          {excecoes.length === 0 && <li>Nenhuma exceção.</li>}
          {excecoes.map(([motivo, n]) => <li key={motivo}><code>{motivo}</code>: {n}</li>)}
        </ul>
      </div>

      <div className="rounded-2xl bg-white border border-slate-200/80 overflow-x-auto">
        {erro && <p className="p-5 text-sm text-red-700">Não foi possível carregar a correspondência: {erro}</p>}
        {!erro && !linhas && <p className="p-5 text-sm text-slate-500">Carregando…</p>}
        {linhas && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500 bg-slate-50">
              <tr><th className="px-4 py-2">Matrícula</th><th className="px-4 py-2">Nome</th><th className="px-4 py-2">Acadêmico</th><th className="px-4 py-2">Socioeconômico</th><th className="px-4 py-2">Faltando</th></tr>
            </thead>
            <tbody>
              {linhas.map((l) => (
                <tr key={l.matricula} className="border-t border-slate-100">
                  <td className="px-4 py-2 font-mono">{l.matricula}</td>
                  <td className="px-4 py-2">{l.nome ?? <span className="text-slate-400">—</span>}</td>
                  <td className="px-4 py-2">{l.academico ? 'Sim' : 'Não'}</td>
                  <td className="px-4 py-2">{l.socioeconomico ? 'Sim' : 'Não'}</td>
                  <td className="px-4 py-2">{ROTULO_FALTANDO[l.faltando]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/components/lote/CoberturaLote.test.tsx`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/lote/CoberturaLote.tsx frontend/src/components/lote/CoberturaLote.test.tsx
git commit -m "feat(frontend): componente CoberturaLote (KPIs, exceções e correspondência)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Frontend — `InserirLote` e os três passos

**Files:**
- Create: `frontend/src/components/lote/InserirLote.tsx`
- Create: `frontend/src/components/lote/PassoAbrir.tsx`
- Create: `frontend/src/components/lote/PassoEnviar.tsx`
- Create: `frontend/src/components/lote/PassoFechar.tsx`
- Test: `frontend/src/components/lote/InserirLote.test.tsx`

**Interfaces:**
- Consumes: `passoAtual`, `validarIdLote`, `filtrarArquivosAceitos`, `sugerirIdLote` (Task 3); `NovoLote` (Task 2); `HistoricosOut`, `Lote`.
- Produces: `<InserirLote lote={Lote | null} lotes={Lote[]} ocupado={boolean} erro={string | null} resultadoEnvio={HistoricosOut | null} onAbrir={(d: NovoLote) => void} onEnviar={(arquivos: File[]) => void} onFechar={() => void} />`. Componentes puros: todo estado de negócio vem por props; só estado de formulário é local.

- [ ] **Step 1: Escrever os testes que falham**

Criar `frontend/src/components/lote/InserirLote.test.tsx`:

```tsx
import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import type { ComponentProps } from 'react';
import type { Lote } from '../../data/tipos';
import InserirLote from './InserirLote';

const base: Lote = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2026.1'],
  executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {},
};
const ingestao = (passo: number) => ({ id: passo, passo, arquivo_sha256: null, executado_em: '2026-09-12T10:00:00Z', registros_lidos: 1, registros_aceitos: 1, registros_rejeitados: 0 });
const nada = () => {};
const render = (lote: Lote | null, extra: Partial<ComponentProps<typeof InserirLote>> = {}) =>
  renderToString(<InserirLote lote={lote} lotes={[]} ocupado={false} erro={null} resultadoEnvio={null} onAbrir={nada} onEnviar={nada} onFechar={nada} {...extra} />).replace(/<!-- -->/g, '');

describe('InserirLote', () => {
  test('sem lote: passo 1 com id sugerido e campo de períodos', () => {
    const html = render(null);
    expect(html).toContain('Abrir lote');
    expect(html).toMatch(/value="\d{4}-\d{2}-L01"/);
    expect(html).toContain('Períodos cobertos');
  });
  test('lote sem ingestões: passo 2 com input de arquivos aceitando .zip e .pdf', () => {
    const html = render(base);
    expect(html).toContain('Enviar e rodar');
    expect(html).toContain('type="file"');
    expect(html).toContain('accept=".zip,.pdf"');
  });
  test('lote com passos 1 e 2: passo 3 com botão Fechar lote', () => {
    const html = render({ ...base, ingestoes: [ingestao(1), ingestao(2)] });
    expect(html).toContain('Fechar lote');
    expect(html).not.toContain('type="file"');
  });
  test('lote fechado: selo "Fechado em" e nenhum botão de ação', () => {
    const html = render({ ...base, ingestoes: [ingestao(1), ingestao(2)], fechado_em: '2026-09-12T11:00:00Z' });
    expect(html).toContain('Fechado em');
    expect(html).not.toContain('Fechar lote');
    expect(html).not.toContain('type="file"');
  });
  test('erro aparece no passo atual', () => {
    expect(render(base, { erro: 'Passo 2 já foi executado' })).toContain('Passo 2 já foi executado');
  });
  test('resultado do envio mostra gravados e ignorados', () => {
    const html = render({ ...base, ingestoes: [ingestao(1), ingestao(2)] }, {
      resultadoEnvio: { lote: base.id, gravados: ['a.pdf', 'b.pdf'], ja_existiam: [], ignorados: ['leiame.txt'], sincronizar: { importados: 5 }, atualizar_crg: 'ja_executado' },
    });
    expect(html).toContain('2 gravado');
    expect(html).toContain('leiame.txt');
    expect(html).toContain('importados');
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/components/lote/InserirLote.test.tsx`
Expected: falha de import.

- [ ] **Step 3: Implementar os três passos**

Criar `frontend/src/components/lote/PassoAbrir.tsx`:

```tsx
import { useState } from 'react';
import type { FormEvent } from 'react';
import type { NovoLote } from '../../data/api';
import type { Lote } from '../../data/tipos';
import { sugerirIdLote, validarIdLote } from '../../domain/lote';

interface Props {
  lotes: Lote[];
  ocupado: boolean;
  onAbrir: (dados: NovoLote) => void;
}

const INPUT = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500';

export default function PassoAbrir({ lotes, ocupado, onAbrir }: Props) {
  const [id, setId] = useState(() => sugerirIdLote(new Date(), lotes));
  const [periodos, setPeriodos] = useState('');
  const [por, setPor] = useState('');
  const idValido = validarIdLote(id);
  const lista = periodos.split(/[,\s]+/).map((p) => p.trim()).filter(Boolean);

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (!idValido || lista.length === 0) return;
    onAbrir({ id, periodos_cobertos: lista, executado_por: por.trim() || null });
  }

  return (
    <form onSubmit={enviar} className="space-y-3">
      <label className="block text-sm">
        <span className="font-medium text-slate-700">Id do lote</span>
        <input className={INPUT} value={id} onChange={(e) => setId(e.target.value)} aria-invalid={!idValido} />
        {!idValido && <span className="text-xs text-red-700">Só letras, dígitos, "-" e "_", de 3 a 20 caracteres.</span>}
      </label>
      <label className="block text-sm">
        <span className="font-medium text-slate-700">Períodos cobertos</span>
        <input className={INPUT} value={periodos} onChange={(e) => setPeriodos(e.target.value)} placeholder="2025.2 2026.1" />
        <span className="text-xs text-slate-500">Separe por espaço ou vírgula.</span>
      </label>
      <label className="block text-sm">
        <span className="font-medium text-slate-700">Executado por</span>
        <input className={INPUT} value={por} onChange={(e) => setPor(e.target.value)} />
      </label>
      <button type="submit" disabled={ocupado || !idValido || lista.length === 0} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
        Abrir lote
      </button>
    </form>
  );
}
```

Criar `frontend/src/components/lote/PassoEnviar.tsx`:

```tsx
import { useState } from 'react';
import type { ChangeEvent } from 'react';
import type { HistoricosOut } from '../../data/tipos';
import { filtrarArquivosAceitos } from '../../domain/lote';

interface Props {
  ocupado: boolean;
  onEnviar: (arquivos: File[]) => void;
}

export default function PassoEnviar({ ocupado, onEnviar }: Props) {
  const [aceitos, setAceitos] = useState<File[]>([]);
  const [rejeitados, setRejeitados] = useState<File[]>([]);

  function escolher(e: ChangeEvent<HTMLInputElement>) {
    const r = filtrarArquivosAceitos(Array.from(e.target.files ?? []));
    setAceitos(r.aceitos);
    setRejeitados(r.rejeitados);
  }

  return (
    <div className="space-y-3 text-sm">
      <label className="block">
        <span className="font-medium text-slate-700">Históricos do SIGAA (um .zip ou vários .pdf)</span>
        <input type="file" multiple accept=".zip,.pdf" onChange={escolher} disabled={ocupado} className="mt-1 block w-full text-sm" />
      </label>
      {aceitos.length > 0 && <p className="text-slate-600">{aceitos.length} arquivo(s) selecionado(s).</p>}
      {rejeitados.length > 0 && (
        <p className="text-amber-700">Ignorados (só .zip ou .pdf): {rejeitados.map((f) => f.name).join(', ')}</p>
      )}
      <button type="button" onClick={() => onEnviar(aceitos)} disabled={ocupado || aceitos.length === 0} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
        {ocupado ? 'Enviando e rodando…' : 'Enviar e rodar'}
      </button>
    </div>
  );
}

/** Resumo do último envio: o que gravou, o que ignorou, e os contadores dos passos. */
export function ResultadoEnvio({ resultado }: { resultado: HistoricosOut }) {
  const passo = (nome: string, valor: HistoricosOut['sincronizar']) => {
    if (valor === null) return null;
    const texto = valor === 'ja_executado' ? 'já executado' : Object.entries(valor).filter(([k]) => k !== 'lote' && k !== 'ingestao_id').map(([k, v]) => `${k}=${v}`).join(', ');
    return <li><span className="font-medium">{nome}:</span> {texto}</li>;
  };
  return (
    <ul className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-900 space-y-1">
      <li>{resultado.gravados.length} gravado(s), {resultado.ja_existiam.length} já existia(m), {resultado.ignorados.length} ignorado(s){resultado.ignorados.length > 0 && `: ${resultado.ignorados.join(', ')}`}</li>
      {passo('Passo 1 (sincronizar)', resultado.sincronizar)}
      {passo('Passo 2 (atualizar CRG)', resultado.atualizar_crg)}
    </ul>
  );
}
```

Criar `frontend/src/components/lote/PassoFechar.tsx`:

```tsx
import type { Lote } from '../../data/tipos';

interface Props {
  lote: Lote;
  ocupado: boolean;
  onFechar: () => void;
}

export default function PassoFechar({ lote, ocupado, onFechar }: Props) {
  const total = Object.values(lote.excecoes_por_motivo).reduce((s, n) => s + n, 0);
  return (
    <div className="space-y-3 text-sm">
      <p className="text-slate-600">
        Passos 1 e 2 executados, {total} exceção(ões). Confira a cobertura abaixo e o dashboard antes de fechar.
        <strong> Fechar é definitivo:</strong> o lote não se reabre nem recebe mais PDFs.
      </p>
      <button type="button" onClick={onFechar} disabled={ocupado} className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
        {ocupado ? 'Fechando…' : 'Fechar lote'}
      </button>
    </div>
  );
}
```

Criar `frontend/src/components/lote/InserirLote.tsx`:

```tsx
import type { NovoLote } from '../../data/api';
import type { HistoricosOut, Lote } from '../../data/tipos';
import { passoAtual } from '../../domain/lote';
import PassoAbrir from './PassoAbrir';
import PassoEnviar, { ResultadoEnvio } from './PassoEnviar';
import PassoFechar from './PassoFechar';

interface Props {
  lote: Lote | null;
  lotes: Lote[];
  ocupado: boolean;
  erro: string | null;
  resultadoEnvio: HistoricosOut | null;
  onAbrir: (dados: NovoLote) => void;
  onEnviar: (arquivos: File[]) => void;
  onFechar: () => void;
}

const PASSOS = [
  { n: 1, rotulo: 'Abrir' },
  { n: 2, rotulo: 'Enviar PDFs e rodar' },
  { n: 3, rotulo: 'Conferir e fechar' },
] as const;

function formatarData(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('pt-BR');
}

/** Stepper de 3 passos; o passo ativo vem só do estado do lote na API. */
export default function InserirLote({ lote, lotes, ocupado, erro, resultadoEnvio, onAbrir, onEnviar, onFechar }: Props) {
  const atual = passoAtual(lote);

  return (
    <section className="rounded-2xl bg-white border border-slate-200/80 p-5 space-y-4" aria-labelledby="inserir-titulo">
      <h2 id="inserir-titulo" className="text-base font-bold text-slate-800">Inserir lote</h2>

      <ol className="flex flex-wrap gap-2 text-xs">
        {PASSOS.map((p) => {
          const estado = atual === null || p.n < atual ? 'feito' : p.n === atual ? 'atual' : 'pendente';
          const cor = estado === 'feito' ? 'bg-emerald-100 text-emerald-800' : estado === 'atual' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-500';
          return <li key={p.n} className={`rounded-full px-3 py-1 font-semibold ${cor}`} aria-current={estado === 'atual' ? 'step' : undefined}>{p.n}. {p.rotulo}</li>;
        })}
      </ol>

      {erro && <p role="alert" className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">{erro}</p>}

      {atual === 1 && <PassoAbrir lotes={lotes} ocupado={ocupado} onAbrir={onAbrir} />}
      {atual === 2 && <PassoEnviar ocupado={ocupado} onEnviar={onEnviar} />}
      {atual === 3 && lote && <PassoFechar lote={lote} ocupado={ocupado} onFechar={onFechar} />}
      {atual === null && lote?.fechado_em && (
        <p className="text-sm text-slate-600">Fechado em {formatarData(lote.fechado_em)}. Para inserir mais dados, abra um lote novo.</p>
      )}

      {resultadoEnvio && <ResultadoEnvio resultado={resultadoEnvio} />}
    </section>
  );
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/components/lote/InserirLote.test.tsx && npx tsc -b`
Expected: 6 passed; `tsc` sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/lote/InserirLote.tsx frontend/src/components/lote/PassoAbrir.tsx frontend/src/components/lote/PassoEnviar.tsx frontend/src/components/lote/PassoFechar.tsx frontend/src/components/lote/InserirLote.test.tsx
git commit -m "feat(frontend): stepper InserirLote com os passos abrir, enviar e fechar

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Frontend — página `Dados`, rota e item de menu

**Files:**
- Create: `frontend/src/pages/Dados.tsx`
- Modify: `frontend/src/main.tsx` (rotas, ~linha 33)
- Modify: `frontend/src/components/Sidebar.tsx` (grupo Navegação, ~linha 66)
- Test: `frontend/src/pages/paginas.test.tsx`

**Interfaces:**
- Consumes: tudo das Tasks 2–7; `useDados()` com `origem`, `carregando`, `lotes`, `recarregar`; `AppShell` com `titulo`, `subtitulo`, `migalhas`, `semFiltros`.

- [ ] **Step 1: Escrever os testes que falham**

Em `frontend/src/pages/paginas.test.tsx`: importar `Dados from './Dados'`, acrescentar `<Route path="/dados" element={<Dados />} />` dentro do `<Routes>` de `renderComContexto`, e acrescentar ao fim do arquivo:

```tsx
const loteAberto = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2026.1'],
  executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {},
};
const ingestao = (passo: number) => ({ id: passo, passo, arquivo_sha256: null, executado_em: '2026-09-12T10:00:00Z', registros_lidos: 1, registros_aceitos: 1, registros_rejeitados: 0 });

describe('tela Dados', () => {
  test('sem API mostra o aviso e nenhum formulário', () => {
    const html = render('/dados');
    expect(html).toContain('A inserção de dados exige a API');
    expect(html).not.toContain('type="file"');
    expect(html).not.toContain('Abrir lote');
  });
  test('com API e nenhum lote começa no passo 1', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [] }, '/dados');
    expect(html).toContain('Abrir lote');
  });
  test('com API e um lote aberto sem ingestões, seleciona esse lote e mostra o passo 2', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [loteAberto], lote: loteAberto }, '/dados');
    expect(html).toContain('type="file"');
    expect(html).toContain('Cobertura do lote 2026-09-L01');
  });
  test('lote com passos 1 e 2 mostra o botão Fechar lote', () => {
    const rodado = { ...loteAberto, ingestoes: [ingestao(1), ingestao(2)] };
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [rodado], lote: rodado }, '/dados');
    expect(html).toContain('Fechar lote');
  });
  test('lote fechado mostra "Fechado em" e não mostra ação', () => {
    const fechado = { ...loteAberto, ingestoes: [ingestao(1), ingestao(2)], fechado_em: '2026-09-12T11:00:00Z' };
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [fechado], lote: fechado }, '/dados');
    expect(html).toContain('Fechado em');
    expect(html).not.toContain('Fechar lote');
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/pages/paginas.test.tsx`
Expected: falha de import (`./Dados` não existe).

- [ ] **Step 3: Implementar a página, a rota e o menu**

Criar `frontend/src/pages/Dados.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'react';
import AppShell from '../components/layout/AppShell';
import CoberturaLote from '../components/lote/CoberturaLote';
import InserirLote from '../components/lote/InserirLote';
import * as api from '../data/api';
import type { NovoLote } from '../data/api';
import type { Correspondencia, HistoricosOut } from '../data/tipos';
import { criarFluxoLote } from '../hooks/fluxoLote';
import { useDados } from '../hooks/useDados';

const NOVO = '__novo__';

/** Tela Dados: inserir um lote (abrir → enviar e rodar → fechar) e ver a cobertura. */
export default function Dados() {
  const { origem, carregando, lotes, recarregar } = useDados();
  // null = ainda não escolheu: cai no lote mais recente, ou em "novo" se não há nenhum.
  const [escolhido, setEscolhido] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultadoEnvio, setResultadoEnvio] = useState<HistoricosOut | null>(null);
  const [linhas, setLinhas] = useState<Correspondencia[] | null>(null);
  const [erroCobertura, setErroCobertura] = useState<string | null>(null);
  const [versao, setVersao] = useState(0); // incrementa após enviar/fechar para recarregar a cobertura

  const selecionadoId = escolhido ?? (lotes.length > 0 ? lotes[lotes.length - 1].id : NOVO);
  const lote = useMemo(() => lotes.find((l) => l.id === selecionadoId) ?? null, [lotes, selecionadoId]);

  const fluxo = useMemo(() => criarFluxoLote({ api, recarregar }), [recarregar]);

  useEffect(() => {
    if (!lote) { setLinhas(null); setErroCobertura(null); return; }
    let ativo = true;
    setLinhas(null);
    api.carregarCorrespondencia(lote.id)
      .then((ls) => { if (ativo) { setLinhas(ls); setErroCobertura(null); } })
      .catch((e) => { if (ativo) setErroCobertura(e instanceof api.ErroApi ? e.detail : String(e)); });
    return () => { ativo = false; };
  }, [lote?.id, lote?.fechado_em, versao]);

  async function rodar<T>(acao: () => Promise<{ ok: true; dados: T } | { ok: false; erro: string | null; status: number }>, depois?: (dados: T) => void) {
    setOcupado(true);
    setErro(null);
    const r = await acao();
    setOcupado(false);
    if (r.ok) depois?.(r.dados);
    else if (r.erro !== null) setErro(r.status === 502 || r.status === 503 ? `${r.erro} — os PDFs ficaram gravados; reenvie os mesmos arquivos para retomar.` : r.erro);
  }

  const onAbrir = (d: NovoLote) => rodar(() => fluxo.abrir(d), (novo) => { setEscolhido(novo.id); setResultadoEnvio(null); });
  const onEnviar = (arquivos: File[]) => rodar(() => fluxo.enviar(selecionadoId, arquivos), (saida) => { setResultadoEnvio(saida); setVersao((v) => v + 1); });
  const onFechar = () => rodar(() => fluxo.fechar(selecionadoId), () => setVersao((v) => v + 1));

  return (
    <AppShell titulo="Dados" subtitulo="Insira um lote de dados e confira a cobertura do que entrou." migalhas={[{ rotulo: 'Dados' }]} semFiltros>
      {origem === 'demonstracao' && !carregando ? (
        <p className="rounded-2xl bg-amber-50 border border-amber-200 p-5 text-sm text-amber-900">
          A inserção de dados exige a API. Suba o backend (<code>docker compose up -d</code>) e recarregue a página.
        </p>
      ) : (
        <div className="space-y-6">
          <label className="block text-sm max-w-xs">
            <span className="font-medium text-slate-700">Lote</span>
            <select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={selecionadoId} disabled={ocupado} onChange={(e) => { setEscolhido(e.target.value); setErro(null); setResultadoEnvio(null); }}>
              <option value={NOVO}>Novo lote</option>
              {lotes.map((l) => <option key={l.id} value={l.id}>{l.id}{l.fechado_em ? ' (fechado)' : ''}</option>)}
            </select>
          </label>

          <InserirLote lote={lote} lotes={lotes} ocupado={ocupado} erro={erro} resultadoEnvio={resultadoEnvio} onAbrir={onAbrir} onEnviar={onEnviar} onFechar={onFechar} />

          {lote && <CoberturaLote lote={lote} linhas={linhas} erro={erroCobertura} />}
        </div>
      )}
    </AppShell>
  );
}
```

Em `frontend/src/main.tsx`: importar `Dados from './pages/Dados'` e acrescentar, logo depois da rota `/aluno/:matricula`:

```tsx
          {/* Inserção de lote + cobertura (docs/superpowers/specs/2026-09-18-tela-dados-lote-design.md) */}
          <Route path="/dados" element={<Dados />} />
```

Em `frontend/src/components/Sidebar.tsx`: acrescentar o ícone junto aos outros:

```tsx
const IconUpload = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
);
```

e no grupo `Navegação`, depois do item `Polos`:

```tsx
      { label: 'Dados', to: '/dados', icon: <IconUpload /> },
```

- [ ] **Step 4: Rodar tudo**

Run: `cd frontend && npx tsc -b && npx vitest run && npm run lint`
Expected: sem erros de tipo; todos os testes passando (62 anteriores + Tasks 2–8); lint limpo.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Dados.tsx frontend/src/main.tsx frontend/src/components/Sidebar.tsx frontend/src/pages/paginas.test.tsx
git commit -m "feat(frontend): tela Dados com inserção de lote e cobertura

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Documentação e verificação manual

**Files:**
- Modify: `docs/frontend_dashboards.md` (tabela "Rotas")
- Modify: `docs/primeiro_lote.md`
- Modify: `docs/operacao_lote.md` (seção "Pelo Swagger")

- [ ] **Step 1: Documentar a rota e o caminho pela tela**

Em `docs/frontend_dashboards.md`, na tabela de rotas, acrescentar depois da linha de `/aluno/:matricula`:

```markdown
| `/dados` | Inserção de lote (abrir → enviar PDFs e rodar → conferir e fechar) + cobertura do lote (correspondência por matrícula) | spec `2026-09-18-tela-dados-lote-design.md` |
```

E na seção "Dados", acrescentar um item:

```markdown
- A tela `/dados` é a única que **escreve** na API (`POST /lotes`, `POST /lotes/{id}/historicos?executar=true`,
  `POST /lotes/{id}/fechar`) e lê `GET /lotes/{id}/correspondencia`. Sem API ela mostra só um aviso.
  Depois de cada ação, `recarregar()` do `DadosProvider` atualiza o dashboard inteiro.
```

Em `docs/primeiro_lote.md`, antes de `## Os três passos`, acrescentar:

```markdown
## Pela tela do dashboard (mais simples)

Abra `http://localhost:8080/dados`. Os mesmos três passos, em botões:
**Abrir lote** (id sugerido, períodos `2025.2 2026.1`, seu nome) → **Enviar e rodar**
(selecione o `historicos_L01.zip`) → confira a cobertura que aparece embaixo →
**Fechar lote**. O que segue é o mesmo fluxo pelo Swagger.
```

Em `docs/operacao_lote.md`, no início da seção `## Pelo Swagger (sem terminal)`, acrescentar uma linha:

```markdown
A tela **Dados** do dashboard (`http://localhost:8080/dados`) faz estas mesmas três chamadas por botões — é o caminho recomendado para quem não quer abrir o Swagger.
```

- [ ] **Step 2: Roteiro manual (Docker no ar, FasiTech configurado)**

Só executável com `backend/.env` preenchido. Registrar o resultado no PR/commit; se não for possível rodar, dizer explicitamente.

1. `docker compose up -d --build`; abrir `http://localhost:8080/dados`.
2. Sem lotes: passo 1 mostra id sugerido `AAAA-MM-L01`. Preencher períodos `2025.2 2026.1` e nome; **Abrir lote** → o seletor passa a mostrar o lote e o passo 2 aparece.
3. Selecionar `backend/app/data/historicos_L01.zip` (ou os 56 PDFs); **Enviar e rodar** → resultado com `56 gravado(s)`, passo 1 `importados=103`, passo 2 `pdfs_lidos=56, sem_academico=47`; a cobertura embaixo mostra 103 alunos, 56 completos, 47 falta acadêmico; o selo do lote aparece no cabeçalho; a página Polos mostra os dados reais.
4. Clicar **Enviar e rodar** de novo com o mesmo zip → `409` "Passo 2 já foi executado" na faixa de erro (a tela já está no passo 3, então isso só ocorre se forçado; pular se o input não estiver mais visível).
5. **Fechar lote** → `confirm` → selo "Fechado em"; `data/raw/lotes/<id>/lote.md` e `data/processed/<id>/correspondencia.csv` existem; o seletor mostra "(fechado)".
6. Selecionar "Novo lote" → passo 1 sugere `L02`.

- [ ] **Step 3: Commit**

```bash
git add docs/frontend_dashboards.md docs/primeiro_lote.md docs/operacao_lote.md
git commit -m "docs: tela Dados nos guias do frontend e do primeiro lote

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
