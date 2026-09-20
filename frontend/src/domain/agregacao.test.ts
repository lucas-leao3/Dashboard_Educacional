import { describe, expect, test } from 'vitest';
import { registro } from '../test/fixtures';
import {
  ordenarPeriodos, consolidarAlunos, agregarPorPolo, agregarPorTurma,
  trajetoriaPorDimensao, INDICADORES, N_MINIMO,
} from './agregacao';
import { SEM_TURMA } from '../data/tipos';

describe('ordenarPeriodos', () => {
  test('ordena cronologicamente os rótulos do FasiTech', () => {
    expect(ordenarPeriodos(['2025.(3 e 4)', '2024.(3 e 4)', '2024.(1 e 2)'])).toEqual([
      '2024.(1 e 2)', '2024.(3 e 4)', '2025.(3 e 4)',
    ]);
  });
  test('remove duplicados', () => {
    expect(ordenarPeriodos(['2024.(1 e 2)', '2024.(1 e 2)'])).toEqual(['2024.(1 e 2)']);
  });
});

describe('consolidarAlunos', () => {
  const base = [
    registro({ id: 1, matricula: 10, periodo: '2024.(1 e 2)', CRG: 5, polo: 'Cameta', primeiro_ano_eletivo: '2024.4' }),
    registro({ id: 2, matricula: 10, periodo: '2025.(3 e 4)', CRG: 8, polo: 'Cameta', primeiro_ano_eletivo: '2024.4' }),
    registro({ id: 3, matricula: 20, periodo: '2024.(3 e 4)', CRG: 4, polo: 'Oeiras' }),
  ];
  test('um aluno por matrícula, com o registro mais recente como vigente', () => {
    const alunos = consolidarAlunos(base);
    expect(alunos).toHaveLength(2);
    const a10 = alunos.find((a) => a.matricula === 10)!;
    expect(a10.vigente.CRG).toBe(8);
    expect(a10.registros.map((r) => r.periodo)).toEqual(['2024.(1 e 2)', '2025.(3 e 4)']);
  });
  test('turma vem do primeiro ano letivo; sem ele usa o rótulo padrão', () => {
    const alunos = consolidarAlunos(base);
    expect(alunos.find((a) => a.matricula === 10)!.turma).toBe('2024.4');
    expect(alunos.find((a) => a.matricula === 20)!.turma).toBe(SEM_TURMA);
  });
  test('sinalização e fatores são derivados do vigente', () => {
    const a20 = consolidarAlunos(base).find((a) => a.matricula === 20)!;
    expect(a20.sinalizacao).toBe('critico');
    expect(a20.fatores).toContain('CRG abaixo de 5');
  });
  test('filtrar por período mantém só quem respondeu naquele período', () => {
    const alunos = consolidarAlunos(base, '2025.(3 e 4)');
    expect(alunos.map((a) => a.matricula)).toEqual([10]);
    expect(alunos[0].vigente.periodo).toBe('2025.(3 e 4)');
  });
});

describe('agregarPorPolo', () => {
  const base = [
    registro({ id: 1, matricula: 1, polo: 'Cameta', CRG: 6, renda: 'Até 1 salário mínimo', trabalho: 'Não', acesso_internet: 'Sim' }),
    registro({ id: 2, matricula: 1, polo: 'Cameta', periodo: '2025.(3 e 4)', CRG: 8, renda: 'Até 1 salário mínimo', trabalho: 'Sim, trabalho informal', acesso_internet: 'Sim' }),
    registro({ id: 3, matricula: 2, polo: 'Cameta', CRG: null, renda: '1 a 3 salários mínimos', trabalho: 'Não', acesso_internet: 'Não' }),
    registro({ id: 4, matricula: 3, polo: 'Oeiras', CRG: 9, renda: '1 a 3 salários mínimos', trabalho: 'Não', acesso_internet: 'Sim' }),
  ];
  test('conta alunos únicos e registros', () => {
    const cameta = agregarPorPolo(consolidarAlunos(base)).find((p) => p.polo === 'Cameta')!;
    expect(cameta.alunos).toBe(2);
    expect(cameta.registros).toBe(3);
  });
  test('CRG médio ignora quem não tem nota', () => {
    const cameta = agregarPorPolo(consolidarAlunos(base)).find((p) => p.polo === 'Cameta')!;
    expect(cameta.indicadores.crg_medio).toBe(8);
  });
  test('percentuais usam o registro vigente de cada aluno', () => {
    const cameta = agregarPorPolo(consolidarAlunos(base)).find((p) => p.polo === 'Cameta')!;
    expect(cameta.indicadores.pct_renda_ate_1sm).toBe(50);
    expect(cameta.indicadores.pct_trabalho_informal).toBe(50);
    expect(cameta.indicadores.pct_sem_internet).toBe(50);
  });
  test('sinaliza n baixo abaixo do mínimo', () => {
    const polos = agregarPorPolo(consolidarAlunos(base));
    expect(polos.every((p) => p.nBaixo === p.alunos < N_MINIMO)).toBe(true);
  });
  test('ordena por alunos, decrescente', () => {
    expect(agregarPorPolo(consolidarAlunos(base)).map((p) => p.polo)).toEqual(['Cameta', 'Oeiras']);
  });
  test('todo indicador tem rótulo e formatação', () => {
    for (const ind of INDICADORES) {
      expect(ind.rotulo).toBeTruthy();
      expect(typeof ind.formatar(1)).toBe('string');
    }
  });
});

describe('agregarPorTurma', () => {
  const base = [
    registro({ id: 1, matricula: 1, polo: 'Cameta', primeiro_ano_eletivo: '2024.4', CRG: 8 }),
    registro({ id: 2, matricula: 2, polo: 'Cameta', primeiro_ano_eletivo: '2024.4', CRG: 4 }),
    registro({ id: 3, matricula: 3, polo: 'Cameta', primeiro_ano_eletivo: '2025.4', CRG: null }),
    registro({ id: 4, matricula: 4, polo: 'Oeiras', primeiro_ano_eletivo: '2024.4', CRG: 9 }),
  ];
  test('só turmas do polo, com contagem de alunos e CRG médio', () => {
    const turmas = agregarPorTurma(consolidarAlunos(base), 'Cameta');
    expect(turmas.map((t) => t.turma)).toEqual(['2024.4', '2025.4']);
    expect(turmas[0].alunos).toBe(2);
    expect(turmas[0].indicadores.crg_medio).toBe(6);
    expect(turmas[1].indicadores.crg_medio).toBeNull();
  });
  test('conta sinalizações da turma', () => {
    const [t2024] = agregarPorTurma(consolidarAlunos(base), 'Cameta');
    expect(t2024.porSinalizacao.critico).toBe(1);
    expect(t2024.porSinalizacao.ok).toBe(1);
  });
});

describe('trajetoriaPorDimensao', () => {
  const [aluno] = consolidarAlunos([
    registro({ id: 1, matricula: 1, periodo: '2024.(1 e 2)', CRG: 5, saude_mental: 'Ruim', estresse: 'Não' }),
    registro({ id: 2, matricula: 1, periodo: '2024.(3 e 4)', CRG: 7, saude_mental: 'Regular', estresse: 'Não' }),
    registro({ id: 3, matricula: 1, periodo: '2025.(3 e 4)', CRG: null, saude_mental: 'Boa', estresse: 'Não' }),
  ]);
  test('acadêmica é a série de CRG por período (null preservado)', () => {
    expect(trajetoriaPorDimensao(aluno, 'academica')).toEqual([
      { periodo: '2024.(1 e 2)', valor: 5 }, { periodo: '2024.(3 e 4)', valor: 7 }, { periodo: '2025.(3 e 4)', valor: null },
    ]);
  });
  test('saúde mental é o índice da dimensão por período', () => {
    expect(trajetoriaPorDimensao(aluno, 'saude_mental').map((p) => p.valor)).toEqual([2, 1, 0]);
  });
});
