import { describe, expect, test } from 'vitest';
import { consolidarAlunos } from './agregacao';
import { textoVariacao } from './trajetoria';
import { registro } from '../test/fixtures';

describe('textoVariacao', () => {
  test('CRG com duas casas e sinal', () => {
    const [a] = consolidarAlunos([
      registro({ id: 1, matricula: 1, periodo: '2024.(1 e 2)', CRG: 5 }),
      registro({ id: 2, matricula: 1, periodo: '2025.(3 e 4)', CRG: 6.2 }),
    ]);
    expect(textoVariacao(a, 'academica')).toBe('variação +1.20 em CRG');
  });
  test('avisa quando há menos de dois períodos com dado', () => {
    const [a] = consolidarAlunos([registro({ id: 1, matricula: 1, CRG: 5 })]);
    expect(textoVariacao(a, 'academica')).toBe('menos de 2 períodos com dado');
  });
});
