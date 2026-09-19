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
