import { describe, expect, test } from 'vitest';
import { SEM_POLO, SEM_TURMA } from '../data/tipos';
import { consolidarAlunos } from './agregacao';
import { registro } from '../test/fixtures';
import {
  codigoDePolo, digitosDaMatricula, poloDaMatricula, poloParaExibir,
  turmaDaMatricula, turmaDoRotulo, turmaParaExibir,
} from './matricula';

describe('turmaDaMatricula', () => {
  test('os 4 primeiros dígitos são o ano de ingresso', () => {
    expect(turmaDaMatricula(202016040011)).toBe('2020');
    expect(turmaDaMatricula(202316040045)).toBe('2023');
  });

  test('cobre todos os anos de ingresso presentes na base real', () => {
    const casos: [number, string][] = [
      [202016040002, '2020'], [202116040018, '2021'], [202216040007, '2022'],
      [202316040045, '2023'], [202416040031, '2024'], [202516040040, '2025'],
      [202616040012, '2026'],
    ];
    for (const [matricula, turma] of casos) expect(turmaDaMatricula(matricula)).toBe(turma);
  });

  test('aceita matrícula como string (vem assim da rota)', () => {
    expect(turmaDaMatricula('202016040011')).toBe('2020');
    expect(turmaDaMatricula(' 202016040011 ')).toBe('2020');
  });

  test('matrícula nula, vazia ou inválida não vira turma', () => {
    for (const ruim of [null, undefined, '', '   ', 0, 1, 20201604, '2020160400112', 'abcdefghijkl', '20201604001x', NaN]) {
      expect(turmaDaMatricula(ruim as never)).toBeNull();
    }
  });
});

describe('poloDaMatricula', () => {
  test('dígitos 5–8 mapeiam para o nome do polo (§4.8)', () => {
    expect(poloDaMatricula(202016040011)).toBe('Cametá');
    expect(poloDaMatricula(202285640003)).toBe('Limoeiro');
    expect(poloDaMatricula(202485940009)).toBe('Oeiras');
  });

  test('código fora da tabela aparece na tela em vez de sumir', () => {
    expect(poloDaMatricula(202099990001)).toBe('Polo 9999');
  });

  test('matrícula inválida não vira polo', () => {
    expect(poloDaMatricula(null)).toBeNull();
    expect(poloDaMatricula(123)).toBeNull();
  });

  test('codigoDePolo devolve os dígitos crus', () => {
    expect(codigoDePolo(202016040011)).toBe('1604');
    expect(codigoDePolo('x')).toBeNull();
  });
});

describe('digitosDaMatricula', () => {
  test('só passa o que tem exatamente 12 dígitos', () => {
    expect(digitosDaMatricula(202016040011)).toBe('202016040011');
    expect(digitosDaMatricula(20201604001)).toBeNull();
    expect(digitosDaMatricula(2020160400111)).toBeNull();
  });
});

describe('turmaDoRotulo', () => {
  test('extrai o ano do rótulo legado', () => {
    expect(turmaDoRotulo('2024.4')).toBe('2024');
    expect(turmaDoRotulo('2024')).toBe('2024');
  });
  test('rótulo ausente ou sem ano não vira turma', () => {
    for (const ruim of [null, undefined, '', 'sem informação']) expect(turmaDoRotulo(ruim)).toBeNull();
  });
});

describe('integração com o que o banco devolve', () => {
  test('o valor derivado pelo banco tem precedência sobre a derivação local', () => {
    const [aluno] = consolidarAlunos([
      registro({ matricula: 202016040011, turma: '2020', polo_cod: '1604', polo_nome: 'Cametá' }),
    ]);
    expect(aluno.turma).toBe('2020');
    expect(aluno.polo).toBe('Cametá');
  });

  test('sem API (demonstração), a derivação local cobre o mesmo valor', () => {
    const [aluno] = consolidarAlunos([registro({ matricula: 202016040011 })]);
    expect(aluno.turma).toBe('2020');
    expect(aluno.polo).toBe('Cametá');
  });

  test('polo que o banco ainda não conhece aparece pelo código, não some', () => {
    const [aluno] = consolidarAlunos([
      registro({ matricula: 202099990001, turma: '2020', polo_cod: '9999', polo_nome: null }),
    ]);
    expect(aluno.polo).toBe('Polo 9999');
  });
});

describe('valores para exibição', () => {
  test('a matrícula tem precedência sobre o dado informado', () => {
    expect(turmaParaExibir(202016040011, '2024.4')).toBe('2020');
    expect(poloParaExibir(202016040011, 'Oeiras')).toBe('Cametá');
  });

  test('matrícula inválida cai no dado informado', () => {
    expect(turmaParaExibir(1, '2024.4')).toBe('2024');
    expect(poloParaExibir(1, 'Cameta')).toBe('Cameta');
  });

  test('sem matrícula e sem dado informado, rótulo explícito de ausência', () => {
    expect(turmaParaExibir(null, null)).toBe(SEM_TURMA);
    expect(poloParaExibir(null, null)).toBe(SEM_POLO);
    expect(poloParaExibir(null, '   ')).toBe(SEM_POLO);
  });
});
