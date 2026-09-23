import { describe, expect, test } from 'vitest';
import type { CrgSemestre } from '../data/tipos';
import { consolidarAlunos } from './agregacao';
import { registro } from '../test/fixtures';
import {
  EIXOS_X, NAO_INFORMADO, eixo, histogramaCrg, mediaCrgPorCategoria,
  ordenarSemestres, serieLongitudinal,
} from './analises';

const alunos = consolidarAlunos([
  registro({ id: 1, matricula: 202016040001, CRG: 8, cor_etnia: 'Pardo', genero: 'Feminino' }),
  registro({ id: 2, matricula: 202016040002, CRG: 6, cor_etnia: 'Pardo', genero: 'Masculino' }),
  registro({ id: 3, matricula: 202185940003, CRG: 4, cor_etnia: 'Branco', genero: 'Feminino' }),
  registro({ id: 4, matricula: 202185940004, CRG: null, cor_etnia: 'Branco', genero: 'Feminino' }),
  registro({ id: 5, matricula: 202285640005, CRG: 10, cor_etnia: null, genero: 'Masculino' }),
]);

describe('mediaCrgPorCategoria', () => {
  test('média por categoria, com o n de cada barra', () => {
    const barras = mediaCrgPorCategoria(alunos, eixo('cor_etnia'));
    const pardo = barras.find((b) => b.categoria === 'Pardo')!;
    expect(pardo.valor).toBe(7);
    expect(pardo.n).toBe(2);
  });

  test('quem não respondeu vira categoria própria, não some', () => {
    const barras = mediaCrgPorCategoria(alunos, eixo('cor_etnia'));
    expect(barras.map((b) => b.categoria)).toContain(NAO_INFORMADO);
    expect(barras.find((b) => b.categoria === NAO_INFORMADO)!.valor).toBe(10);
  });

  test('aluno sem CRG conta no n mas não na média', () => {
    const branco = mediaCrgPorCategoria(alunos, eixo('cor_etnia')).find((b) => b.categoria === 'Branco')!;
    expect(branco.n).toBe(2);
    expect(branco.nComNota).toBe(1);
    expect(branco.valor).toBe(4);
  });

  test('categoria sem nenhuma nota devolve valor null, não zero', () => {
    const so = consolidarAlunos([registro({ matricula: 202016040009, CRG: null, cor_etnia: 'Preto' })]);
    const [barra] = mediaCrgPorCategoria(so, eixo('cor_etnia'));
    expect(barra.valor).toBeNull();
    expect(barra.n).toBe(1);
  });

  test('n baixo mede quem TEM NOTA, não o total da categoria', () => {
    // 20 alunos na categoria, mas só 3 com nota: a média se apoia em 3.
    const muitos = consolidarAlunos([
      ...Array.from({ length: 17 }, (_, i) =>
        registro({ id: 100 + i, matricula: 202016040100 + i, CRG: null, renda: 'A' })),
      ...Array.from({ length: 3 }, (_, i) =>
        registro({ id: 200 + i, matricula: 202016040200 + i, CRG: 8, renda: 'A' })),
    ]);
    const [barra] = mediaCrgPorCategoria(muitos, eixo('renda'));
    expect(barra.n).toBe(20);
    expect(barra.nComNota).toBe(3);
    expect(barra.nBaixo).toBe(true);
  });

  test('amostra suficiente de notas não é marcada', () => {
    const muitos = consolidarAlunos(
      Array.from({ length: 16 }, (_, i) =>
        registro({ id: 300 + i, matricula: 202016040300 + i, CRG: 7, renda: 'A' })),
    );
    expect(mediaCrgPorCategoria(muitos, eixo('renda'))[0].nBaixo).toBe(false);
  });

  test('ordena da maior média para a menor, com os sem nota no fim', () => {
    const so = consolidarAlunos([
      registro({ id: 1, matricula: 202016040001, CRG: 5, renda: 'A' }),
      registro({ id: 2, matricula: 202016040002, CRG: 9, renda: 'B' }),
      registro({ id: 3, matricula: 202016040003, CRG: null, renda: 'C' }),
    ]);
    expect(mediaCrgPorCategoria(so, eixo('renda')).map((b) => b.categoria)).toEqual(['B', 'A', 'C']);
  });

  test('polo e turma são eixos, e saem da matrícula', () => {
    const porPolo = mediaCrgPorCategoria(alunos, eixo('polo'));
    expect(porPolo.map((b) => b.categoria).sort()).toEqual(['Cametá', 'Limoeiro', 'Oeiras']);
    expect(mediaCrgPorCategoria(alunos, eixo('turma')).map((b) => b.categoria).sort()).toEqual(['2020', '2021', '2022']);
  });

  test('todo eixo declarado sabe extrair sua categoria', () => {
    for (const e of EIXOS_X) expect(() => mediaCrgPorCategoria(alunos, e)).not.toThrow();
  });
});

describe('histogramaCrg', () => {
  test('dez faixas inteiras, sempre todas presentes', () => {
    const faixas = histogramaCrg(alunos);
    expect(faixas).toHaveLength(10);
    expect(faixas.map((f) => f.faixa)).toEqual(['0–1', '1–2', '2–3', '3–4', '4–5', '5–6', '6–7', '7–8', '8–9', '9–10']);
  });

  test('conta cada aluno na sua faixa e ignora quem não tem nota', () => {
    const faixas = histogramaCrg(alunos);          // notas: 8, 6, 4, null, 10
    const por = Object.fromEntries(faixas.map((f) => [f.faixa, f.frequencia]));
    expect(por['4–5']).toBe(1);
    expect(por['6–7']).toBe(1);
    expect(por['8–9']).toBe(1);                    // o limite inferior pertence à faixa
    expect(por['9–10']).toBe(1);                   // o 10
    expect(por['7–8']).toBe(0);
    expect(faixas.reduce((s, f) => s + f.frequencia, 0)).toBe(4);   // o CRG null fica de fora
  });

  test('CRG 10 entra na última faixa, não fora dela', () => {
    const faixas = histogramaCrg(consolidarAlunos([registro({ matricula: 202016040001, CRG: 10 })]));
    expect(faixas.find((f) => f.faixa === '9–10')!.frequencia).toBe(1);
  });

  test('base sem nenhuma nota devolve as faixas zeradas, não vazio', () => {
    const faixas = histogramaCrg(consolidarAlunos([registro({ matricula: 202016040001, CRG: null })]));
    expect(faixas).toHaveLength(10);
    expect(faixas.every((f) => f.frequencia === 0)).toBe(true);
  });
});

describe('ordenarSemestres', () => {
  test('ordem cronológica, não alfabética', () => {
    expect(ordenarSemestres(['2024.2', '2023.1', '2024.1', '2023.2'])).toEqual(['2023.1', '2023.2', '2024.1', '2024.2']);
  });
});

describe('serieLongitudinal', () => {
  const semestres: CrgSemestre[] = [
    { matricula: 202016040001, semestre: '2023.1', crg: 6 },
    { matricula: 202016040001, semestre: '2023.2', crg: 8 },
    { matricula: 202016040002, semestre: '2023.1', crg: 4 },
    { matricula: 202016040002, semestre: '2023.2', crg: null },
    { matricula: 202185940003, semestre: '2023.2', crg: 10 },
  ];

  test('uma série por turma, média dos alunos da turma em cada semestre', () => {
    const { series, dados } = serieLongitudinal(alunos, semestres);
    expect(series).toEqual(['Turma 2020', 'Turma 2021']);
    expect(dados.find((d) => d.semestre === '2023.1')!['Turma 2020']).toBe(5);
  });

  test('semestre não apurado vira null (lacuna), nunca zero', () => {
    const { dados } = serieLongitudinal(alunos, semestres);
    // Em 2023.2 a turma 2020 só tem o aluno 1 com nota (o 2 está não apurado).
    expect(dados.find((d) => d.semestre === '2023.2')!['Turma 2020']).toBe(8);
    // A turma 2021 não existe em 2023.1: lacuna, e não 0.
    expect(dados.find((d) => d.semestre === '2023.1')!['Turma 2021']).toBeNull();
  });

  test('série sem NENHUMA nota apurada fica fora: legenda não ganha linha vazia', () => {
    // Caso real: a turma 2025 tem semestres registrados e zero notas.
    const { series } = serieLongitudinal(alunos, [
      { matricula: 202016040001, semestre: '2024.1', crg: 7 },
      { matricula: 202185940003, semestre: '2024.1', crg: null },
      { matricula: 202185940004, semestre: '2024.2', crg: null },
    ]);
    expect(series).toEqual(['Turma 2020']);
  });

  test('semestre sem nota numa série que tem notas noutro semestre vira lacuna', () => {
    const { dados } = serieLongitudinal(alunos, [
      { matricula: 202016040002, semestre: '2024.1', crg: null },
      { matricula: 202016040002, semestre: '2024.2', crg: 6 },
    ]);
    expect(dados.find((d) => d.semestre === '2024.1')!['Turma 2020']).toBeNull();
    expect(dados.find((d) => d.semestre === '2024.2')!['Turma 2020']).toBe(6);
  });

  test('os semestres saem em ordem cronológica', () => {
    const { dados } = serieLongitudinal(alunos, semestres);
    expect(dados.map((d) => d.semestre)).toEqual(['2023.1', '2023.2']);
  });

  test('filtrar por turma reduz as séries sem mexer no eixo', () => {
    const { series } = serieLongitudinal(alunos, semestres, { turmas: ['2020'] });
    expect(series).toEqual(['Turma 2020']);
  });

  test('filtrar por aluno vira uma série só, identificada por nome e matrícula', () => {
    const { series, dados } = serieLongitudinal(alunos, semestres, { matricula: 202016040001 });
    expect(series).toEqual(['— · 202016040001']);          // fixture sem nome
    expect(dados.find((d) => d.semestre === '2023.2')!['— · 202016040001']).toBe(8);
  });

  test('a série do aluno usa o nome quando existe', () => {
    const comNome = consolidarAlunos([
      registro({ id: 1, matricula: 202016040001, nome: 'NALBERTH DE LEAO CASTRO', CRG: 8 }),
    ]);
    const { series } = serieLongitudinal(comNome, semestres, { matricula: 202016040001 });
    expect(series).toEqual(['Nalberth de Leao Castro · 202016040001']);
  });

  test('sem nenhum semestre devolve vazio em vez de quebrar', () => {
    const { series, dados } = serieLongitudinal(alunos, []);
    expect(series).toEqual([]);
    expect(dados).toEqual([]);
  });
});
