import { describe, expect, test } from 'vitest';
import { SEM_NOME, identificacao, nomeExibido } from './aluno';

describe('nomeExibido', () => {
  test('capitaliza o que o SIGAA manda em caixa alta', () => {
    expect(nomeExibido('NALBERTH DE LEAO CASTRO')).toBe('Nalberth de Leao Castro');
    expect(nomeExibido('JOSIELSON PANTOJA DAMASCENO')).toBe('Josielson Pantoja Damasceno');
  });

  test('partículas em minúscula, menos quando abrem o nome', () => {
    expect(nomeExibido('SIDNEY SANTANA DOS SANTOS LOBATO')).toBe('Sidney Santana dos Santos Lobato');
    expect(nomeExibido('MARIA DA SILVA E SOUZA')).toBe('Maria da Silva e Souza');
    expect(nomeExibido('DOS ANJOS PEREIRA')).toBe('Dos Anjos Pereira');
  });

  test('preserva os separadores dentro da palavra', () => {
    expect(nomeExibido('MARIA-JOSE DA COSTA')).toBe('Maria-Jose da Costa');
    expect(nomeExibido("D'AVILA SANTOS")).toBe("D'Avila Santos");
  });

  test('não se atrapalha com espaços extras', () => {
    expect(nomeExibido('  ANA   PAULA  ')).toBe('Ana Paula');
  });

  test('nome ausente ou vazio devolve null, não string vazia', () => {
    for (const vazio of [null, undefined, '', '   ']) expect(nomeExibido(vazio)).toBeNull();
  });

  test('nome já capitalizado passa intacto', () => {
    expect(nomeExibido('Ana Paula de Souza')).toBe('Ana Paula de Souza');
  });
});

describe('identificacao', () => {
  test('nome seguido da matrícula', () => {
    expect(identificacao('NALBERTH DE LEAO CASTRO', 202016040011)).toBe('Nalberth de Leao Castro · 202016040011');
  });

  test('sem nome, o travessão no lugar dele -- a matrícula nunca some', () => {
    expect(identificacao(null, 202216040022)).toBe(`${SEM_NOME} · 202216040022`);
    expect(identificacao('', 202216040022)).toBe(`${SEM_NOME} · 202216040022`);
  });

  test('aceita a matrícula como string (vem assim da rota)', () => {
    expect(identificacao(null, '202216040022')).toBe(`${SEM_NOME} · 202216040022`);
  });

  test('o marcador de ausência é o mesmo usado no resto do painel', () => {
    expect(SEM_NOME).toBe('—');
  });
});
