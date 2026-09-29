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
