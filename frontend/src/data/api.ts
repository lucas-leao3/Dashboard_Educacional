import { crgSemestresDemonstracao, registrosDemonstracao } from './mockData';
import type { Correspondencia, CrgSemestre, HistoricosOut, Lote, Registro } from './tipos';

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
 * Busca GET {baseUrl}/alunos (o vigente de cada matrícula×período). Se a API
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

export interface NovoLote {
  id: string;
  periodos_cobertos: string[];
  executado_por: string | null;
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

export function abrirLote(dados: NovoLote, opcoes: Opcoes = {}): Promise<Lote> {
  return chamar('/lotes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados) }, opcoes) as Promise<Lote>;
}

export function enviarHistoricos(id: string, arquivos: File[], opcoes: Opcoes = {}): Promise<HistoricosOut> {
  const form = new FormData();
  for (const arquivo of arquivos) form.append('arquivos', arquivo, arquivo.name);
  return chamar(`/lotes/${encodeURIComponent(id)}/historicos?executar=true`, { method: 'POST', body: form }, opcoes) as Promise<HistoricosOut>;
}

export function fecharLote(id: string, opcoes: Opcoes = {}): Promise<Lote> {
  return chamar(`/lotes/${encodeURIComponent(id)}/fechar`, { method: 'POST' }, opcoes) as Promise<Lote>;
}

export function carregarLote(id: string, opcoes: Opcoes = {}): Promise<Lote> {
  return chamar(`/lotes/${encodeURIComponent(id)}`, {}, opcoes) as Promise<Lote>;
}

export function carregarCorrespondencia(id: string, opcoes: Opcoes = {}): Promise<Correspondencia[]> {
  return chamar(`/lotes/${encodeURIComponent(id)}/correspondencia`, {}, opcoes) as Promise<Correspondencia[]>;
}
