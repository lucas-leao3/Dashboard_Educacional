import type { Celula } from '../data/tipos';

/**
 * CSV que o Excel em pt-BR abre certo: `;`, decimal com vírgula, BOM UTF-8.
 * Inteiro longo (matrícula) sai como `="..."`: como número, o Excel o mostraria
 * em notação científica e perderia dígitos. Texto que começa como fórmula
 * (`=`, `+`, `-`, `@`) ganha `'` na frente, para não ser executado ao abrir.
 */
export function paraCsv(colunas: { id: string; rotulo: string }[], linhas: Record<string, Celula>[]): string {
  const celula = (v: Celula | undefined) => {
    if (typeof v === 'number' && Number.isInteger(v) && Math.abs(v) >= 1e8) return `="${v}"`;
    let texto = v === null || v === undefined ? '' : typeof v === 'number' ? String(v).replace('.', ',') : v;
    if (typeof v === 'string' && /^[=+\-@\t\r]/.test(texto)) texto = `'${texto}`;
    return /[";\r\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
  };
  const cabecalho = colunas.map((c) => celula(c.rotulo)).join(';');
  const corpo = linhas.map((l) => colunas.map((c) => celula(l[c.id])).join(';'));
  return '﻿' + [cabecalho, ...corpo].join('\r\n');
}
