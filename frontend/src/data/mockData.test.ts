import { describe, expect, test } from 'vitest';
import { gerarRegistros, registrosDemonstracao } from './mockData';
import { agregarPorPolo, consolidarAlunos } from '../domain/agregacao';
import { SEM_POLO } from './tipos';

describe('dataset de demonstração', () => {
  test('não repete (matrícula, período)', () => {
    const chaves = registrosDemonstracao.map((r) => `${r.matricula}|${r.periodo}`);
    expect(new Set(chaves).size).toBe(chaves.length);
  });
  test('tem 75 alunos em 3 polos, com registros suficientes para as telas', () => {
    const alunos = consolidarAlunos(registrosDemonstracao);
    expect(alunos).toHaveLength(75);
    expect(agregarPorPolo(alunos).map((p) => p.polo)).toEqual(['Cametá', 'Oeiras', 'Limoeiro']);
    expect(registrosDemonstracao.length).toBeGreaterThanOrEqual(110);
  });
  test('as matrículas têm os 12 dígitos reais e turma/polo saem delas', () => {
    expect(registrosDemonstracao.every((r) => /^\d{12}$/.test(String(r.matricula)))).toBe(true);
    // A demonstração espelha a API: os dois campos chegam nulos da fonte.
    expect(registrosDemonstracao.every((r) => r.polo === null && r.primeiro_ano_eletivo === null)).toBe(true);
    const alunos = consolidarAlunos(registrosDemonstracao);
    expect(alunos.every((a) => /^\d{4}$/.test(a.turma))).toBe(true);
    expect(alunos.every((a) => a.polo !== SEM_POLO)).toBe(true);
  });
  test('é determinístico para a mesma semente', () => {
    expect(gerarRegistros(7)).toEqual(gerarRegistros(7));
    expect(gerarRegistros(7)).not.toEqual(gerarRegistros(8));
  });
});
