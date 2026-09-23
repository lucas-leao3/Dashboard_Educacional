import { describe, expect, test } from 'vitest';
import { consolidarAlunos } from './agregacao';
import { textoVariacao } from './trajetoria';
import { registro } from '../test/fixtures';

describe('textoVariacao', () => {
  const [aluno] = consolidarAlunos([
    registro({ id: 1, matricula: 1, periodo: '2024.(1 e 2)', CRG: 5, saude_mental: 'Ruim' }),
    registro({ id: 2, matricula: 1, periodo: '2025.(3 e 4)', CRG: 5, saude_mental: 'Muito boa' }),
  ]);

  test('CRG com duas casas e sinal, medido entre semestres letivos', () => {
    const semestres = [
      { matricula: 1, semestre: '2024.1', crg: 5 },
      { matricula: 1, semestre: '2024.2', crg: 6.2 },
    ];
    expect(textoVariacao(aluno, 'academica', semestres)).toBe('variação +1.20 em CRG');
  });

  test('sem histórico acadêmico, avisa em semestres -- não finge variação zero', () => {
    expect(textoVariacao(aluno, 'academica')).toBe('menos de 2 semestres com dado');
  });

  test('um semestre só também não dá variação', () => {
    const um = [{ matricula: 1, semestre: '2024.1', crg: 5 }];
    expect(textoVariacao(aluno, 'academica', um)).toBe('menos de 2 semestres com dado');
  });

  test('as outras dimensões continuam medidas por período de coleta', () => {
    // A escala é de ALERTA: 'Ruim' -> 'Muito boa' faz o índice cair.
    expect(textoVariacao(aluno, 'saude_mental')).toBe('variação -2 em Índice de alerta');
  });
});
