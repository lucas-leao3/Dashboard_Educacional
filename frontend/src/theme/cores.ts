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
export const PALETA_CATEGORICA = ['#2563eb', '#c2410c', '#7c3aed', '#0d9488'] as const;

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

/**
 * Rampa ORDINAL para turma. Turma é ano de ingresso: trocar a ordem mudaria o
 * sentido, então ela não é categórica -- pede um hue só com claridade
 * monótona, para o leitor ver a ordem na própria cor. A paleta categórica
 * acima serve a polo, que é nominal (e tem 4 slots; turma chega a 7).
 *
 * Gerada em OKLCH (hue 258, C 0.12, L 0.67 -> 0.30) e validada com o
 * validador da skill de dataviz (`validate_palette.js --ordinal`): claridade
 * monótona PASS, todos os saltos ΔL >= 0.06 PASS, ponta clara 2.93:1 contra a
 * superfície PASS, hue spread 2° PASS.
 */
export const RAMPA_TURMA = ['#6596de', '#5383ca', '#4270b6', '#305ea2', '#1f4c8e', '#0b3b7b', '#002968'] as const;

/**
 * Cor da turma pela posição CRONOLÓGICA dela, não pelo ranking do gráfico:
 * a mesma turma mantém a cor quando um filtro muda o conjunto.
 *
 * A rampa foi validada para 7 passos, que é o que a base tem (2020–2026). Com
 * mais turmas que isso os passos ficam abaixo do ΔL mínimo e duas turmas
 * vizinhas passam a ter tons parecidos -- aí o gráfico deve virar pequenos
 * múltiplos, não ganhar mais cores.
 */
export function corDaTurma(turma: string, todas: readonly string[]): string {
  const ordenadas = [...new Set(todas)].sort();
  const i = ordenadas.indexOf(turma);
  if (i < 0) return '#64748b';
  if (ordenadas.length === 1) return RAMPA_TURMA[RAMPA_TURMA.length - 1];
  const passo = Math.round((i / (ordenadas.length - 1)) * (RAMPA_TURMA.length - 1));
  return RAMPA_TURMA[passo];
}
