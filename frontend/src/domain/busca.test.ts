import { describe, expect, test } from 'vitest';
import { consolidarAlunos } from './agregacao';
import { buscarAlunos } from './busca';
import { registro } from '../test/fixtures';

const alunos = consolidarAlunos([
  registro({ id: 1, matricula: 202016040011, nome: 'NALBERTH DE LEAO CASTRO' }),
  registro({ id: 2, matricula: 202016040028, nome: 'SIDNEY SANTANA DOS SANTOS LOBATO' }),
  registro({ id: 3, matricula: 202116040002, nome: 'JOSIELSON PANTOJA DAMASCENO' }),
  registro({ id: 4, matricula: 202216040022, nome: null }),
  registro({ id: 5, matricula: 202385940007, nome: 'MARIA JOSÉ DA SILVA' }),
  registro({ id: 6, matricula: 202485640009, nome: 'ANA SANTANA' }),
]);

const matriculas = (termo: string) => buscarAlunos(alunos, termo).map((a) => a.matricula);

describe('buscarAlunos', () => {
  test('acha por trecho do nome, não só por igualdade', () => {
    expect(matriculas('santana')).toEqual([202016040028, 202485640009]);
    expect(matriculas('pantoja')).toEqual([202116040002]);
  });

  test('ignora a caixa -- o nome é gravado em CAIXA ALTA', () => {
    expect(matriculas('Nalberth')).toEqual([202016040011]);
    expect(matriculas('NALBERTH')).toEqual([202016040011]);
  });

  test('ignora acento: o que a tela mostra encontra o que o banco guarda', () => {
    expect(matriculas('jose')).toEqual([202385940007]);
    expect(matriculas('JOSÉ')).toEqual([202385940007]);
  });

  test('acha o texto que a tela mostra, colado da identificação', () => {
    expect(matriculas('Nalberth de Leao Castro')).toEqual([202016040011]);
  });

  test('acha por trecho da matrícula', () => {
    expect(matriculas('202016040011')).toEqual([202016040011]);
    expect(matriculas('040028')).toEqual([202016040028]);
  });

  test('matrícula exata vem na frente de qualquer casamento parcial', () => {
    const [primeiro] = buscarAlunos(alunos, '202016040028');
    expect(primeiro.matricula).toBe(202016040028);
  });

  test('quem começa com o termo vem antes de quem só o contém', () => {
    expect(matriculas('ana')).toEqual([202485640009, 202016040028]);
  });

  test('aluno sem nome ainda é achável pela matrícula', () => {
    expect(matriculas('202216040022')).toEqual([202216040022]);
  });

  test('termo vazio ou só espaço não devolve nada -- não lista a base inteira', () => {
    for (const vazio of ['', '   ']) expect(buscarAlunos(alunos, vazio)).toEqual([]);
  });

  test('termo sem correspondência devolve lista vazia', () => {
    expect(buscarAlunos(alunos, 'zzzz')).toEqual([]);
  });

  test('respeita o limite, para a lista não cobrir a tela', () => {
    expect(buscarAlunos(alunos, '20', 3)).toHaveLength(3);
  });
});

describe('o que o usuário copia da tela encontra o aluno', () => {
  test('nome capitalizado da tela casa com o CAIXA ALTA do banco', () => {
    // Era o defeito: a tela mostra "Sidney Santana dos Santos Lobato" e a
    // busca comparava com "SIDNEY SANTANA DOS SANTOS LOBATO", por igualdade.
    expect(buscarAlunos(alunos, 'Sidney Santana dos Santos Lobato').map((a) => a.matricula))
      .toEqual([202016040028]);
  });

  test('um sobrenome comum lista todos, em vez de escolher um calado', () => {
    expect(buscarAlunos(alunos, 'santana')).toHaveLength(2);
  });
});

