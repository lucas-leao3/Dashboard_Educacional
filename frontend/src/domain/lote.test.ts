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
