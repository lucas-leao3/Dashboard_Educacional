import type { Sinalizacao } from '../data/tipos';

/**
 * Cores de estado (reservadas: nunca usadas como série). Validadas com o
 * validador de paleta em modo claro; o âmbar fica abaixo de 3:1 sobre branco,
 * por isso toda sinalização é sempre acompanhada de texto (nunca só cor).
 */
export const COR_SINALIZACAO: Record<Sinalizacao, { hex: string; texto: string; fundo: string }> = {
  ok: { hex: '#15803d', texto: 'text-green-700', fundo: 'bg-green-50' },
  atencao: { hex: '#f59e0b', texto: 'text-amber-700', fundo: 'bg-amber-50' },
  critico: { hex: '#dc2626', texto: 'text-red-700', fundo: 'bg-red-50' },
  sem_dado: { hex: '#94a3b8', texto: 'text-slate-500', fundo: 'bg-slate-100' },
};

/** Paleta categórica (identidade), em ordem fixa. Validada: CVD ΔE ≥ 8. */
const PALETA_CATEGORICA = ['#2563eb', '#c2410c', '#7c3aed', '#0d9488'] as const;

/**
 * A cor segue a entidade, não a posição no ranking: o mesmo polo tem sempre
 * a mesma cor, independentemente do filtro. A ordem é alfabética estável.
 */
export function corDaEntidade(nome: string, todas: readonly string[]): string {
  const ordenadas = [...todas].sort((a, b) => a.localeCompare(b));
  const i = ordenadas.indexOf(nome);
  return i >= 0 && i < PALETA_CATEGORICA.length ? PALETA_CATEGORICA[i] : '#64748b';
}

export const COR_PRIMARIA = '#2563eb';
