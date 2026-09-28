import { crgSemestresDemonstracao, registrosDemonstracao } from './mockData';
import type { CrgSemestre, ImportacaoOut, Lote, Registro, Relatorio } from './tipos';

export type Origem = 'api' | 'demonstracao';

export interface ResultadoCarga {
  registros: Registro[];
  origem: Origem;
}

interface Opcoes {
  /** Base da API (VITE_API_URL). Vazia = ir direto para a demonstração. */
  baseUrl?: string;
  fetchFn?: typeof fetch;
}

/**
 * Busca GET {baseUrl}/alunos (o vigente de cada matrícula×período, só dos
 * alunos integrados -- acadêmico + socioeconômico). Se a API
 * não estiver configurada ou falhar, devolve o dataset de demonstração e
 * marca a origem, para a UI avisar que não são dados reais.
 */
export async function carregarRegistros(opcoes: Opcoes = {}): Promise<ResultadoCarga> {
  const baseUrl = (opcoes.baseUrl ?? import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
  const fetchFn = opcoes.fetchFn ?? fetch;
  if (!baseUrl) return { registros: registrosDemonstracao, origem: 'demonstracao' };
  try {
    const resposta = await fetchFn(`${baseUrl}/alunos`, { headers: { Accept: 'application/json' } });
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    const registros = (await resposta.json()) as Registro[];
    return { registros, origem: 'api' };
  } catch {
    return { registros: registrosDemonstracao, origem: 'demonstracao' };
  }
}

/**
 * Busca GET {baseUrl}/crg-semestres (a trajetória acadêmica por semestre).
 * Mesma política de `carregarRegistros`: sem API ou em erro, cai na
 * demonstração -- senão os gráficos de evolução ficariam vazios sem aviso.
 */
export async function carregarCrgSemestres(opcoes: Opcoes = {}): Promise<CrgSemestre[]> {
  const baseUrl = (opcoes.baseUrl ?? import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
  const fetchFn = opcoes.fetchFn ?? fetch;
  if (!baseUrl) return crgSemestresDemonstracao;
  try {
    const resposta = await fetchFn(`${baseUrl}/crg-semestres`, { headers: { Accept: 'application/json' } });
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    return (await resposta.json()) as CrgSemestre[];
  } catch {
    return crgSemestresDemonstracao;
  }
}

/**
 * Busca GET {baseUrl}/lotes (governança por lote, selo no AppShell). Sem
 * baseUrl ou em erro, devolve [] -- o selo simplesmente não aparece.
 */
export async function carregarLotes(opcoes: Opcoes = {}): Promise<Lote[]> {
  const baseUrl = (opcoes.baseUrl ?? import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
  const fetchFn = opcoes.fetchFn ?? fetch;
  if (!baseUrl) return [];
  try {
    const resposta = await fetchFn(`${baseUrl}/lotes`, { headers: { Accept: 'application/json' } });
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    return (await resposta.json()) as Lote[];
  } catch {
    return [];
  }
}

/** Erro de uma chamada de escrita: `detail` é o texto que o FastAPI mandou. */
export class ErroApi extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ErroApi';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Chamada que NÃO cai em demonstração: escrever sem API é erro. Erro HTTP vira
 * ErroApi com o `detail` do corpo; fetch rejeitado vira "Sem resposta da API".
 */
async function chamar(caminho: string, init: RequestInit, opcoes: Opcoes): Promise<unknown> {
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
  return (await resposta.json()) as unknown;
}

/**
 * POST /lotes/importar: o responsável e o .zip dos históricos -- a única
 * entrada de dados. A API cria o lote, extrai o período dos históricos,
 * processa e fecha; se algo falhar, não grava nada.
 */
export function importarLote(responsavel: string, arquivo: File, opcoes: Opcoes = {}): Promise<ImportacaoOut> {
  const form = new FormData();
  form.append('responsavel', responsavel);
  form.append('arquivo', arquivo, arquivo.name);
  return chamar('/lotes/importar', { method: 'POST', body: form }, opcoes) as Promise<ImportacaoOut>;
}

export function carregarRelatorio(id: string, opcoes: Opcoes = {}): Promise<Relatorio> {
  return chamar(`/lotes/${encodeURIComponent(id)}/relatorio`, {}, opcoes) as Promise<Relatorio>;
}
