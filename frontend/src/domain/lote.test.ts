import { describe, expect, test } from 'vitest';
import { ehZip, pendenciaDaImportacao, textoCamposSemResposta, textoPercentual } from './lote';

describe('pendenciaDaImportacao', () => {
  const zip = { name: 'historicos.zip' };
  test('pronto com responsável e .zip', () => expect(pendenciaDaImportacao('Edinaldo', zip)).toBeNull());
  test('sem responsável (ou só espaços)', () => {
    expect(pendenciaDaImportacao('', zip)).toContain('responsável');
    expect(pendenciaDaImportacao('   ', zip)).toContain('responsável');
  });
  test('nome longo demais', () => expect(pendenciaDaImportacao('a'.repeat(101), zip)).toContain('100'));
  test('sem arquivo', () => expect(pendenciaDaImportacao('Edinaldo', null)).toContain('.zip'));
  test('arquivo que não é .zip', () => expect(pendenciaDaImportacao('Edinaldo', { name: 'a.pdf' })).toContain('.zip'));
});

describe('ehZip', () => {
  test('qualquer caixa', () => {
    expect(ehZip('H.ZIP')).toBe(true);
    expect(ehZip('h.zip.pdf')).toBe(false);
  });
});

describe('textos do relatório', () => {
  test('campos sem resposta', () => {
    expect(textoCamposSemResposta([])).toBe('nenhum');
    expect(textoCamposSemResposta(['renda_familiar', 'transporte'])).toBe('renda_familiar, transporte');
  });
  test('percentual', () => {
    expect(textoPercentual(null)).toBe('—');
    expect(textoPercentual(100)).toBe('100%');
    expect(textoPercentual(23.1)).toBe('23,1%');
  });
});
