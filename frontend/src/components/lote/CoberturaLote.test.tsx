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
