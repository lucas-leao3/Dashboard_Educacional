import { describe, expect, test } from 'vitest';
import { classificarDimensao, classificarAluno, fatoresDoRegistro } from './classificacao';
import { registro } from '../test/fixtures';

describe('dimensão acadêmica (CRG)', () => {
  test('sem CRG é sem dado', () => {
    expect(classificarDimensao('academica', registro())).toBe('sem_dado');
  });
  test('CRG abaixo de 5 é crítico', () => {
    expect(classificarDimensao('academica', registro({ CRG: 4.9 }))).toBe('critico');
  });
  test('CRG entre 5 e 7 é atenção', () => {
    expect(classificarDimensao('academica', registro({ CRG: 6.5 }))).toBe('atencao');
  });
  test('CRG a partir de 7 é sem alerta', () => {
    expect(classificarDimensao('academica', registro({ CRG: 7 }))).toBe('ok');
  });
});

describe('dimensão socioeconômica', () => {
  test('todos os campos vazios é sem dado', () => {
    expect(classificarDimensao('socioeconomica', registro())).toBe('sem_dado');
  });
  test('renda até 1 SM sem assistência e trabalho informal é crítico', () => {
    const r = registro({ renda: 'Até 1 salário mínimo', assistencia_estudantil: 'Não', trabalho: 'Sim, trabalho informal' });
    expect(classificarDimensao('socioeconomica', r)).toBe('critico');
  });
  test('renda até 1 SM sem assistência, mas sem trabalho precário, é atenção', () => {
    const r = registro({ renda: 'Até 1 salário mínimo', assistencia_estudantil: 'Não', trabalho: 'Não' });
    expect(classificarDimensao('socioeconomica', r)).toBe('atencao');
  });
  test('só renda até 1 SM com assistência é atenção', () => {
    const r = registro({ renda: 'Até 1 salário mínimo', assistencia_estudantil: 'Sim', trabalho: 'Não' });
    expect(classificarDimensao('socioeconomica', r)).toBe('atencao');
  });
  test('renda de 3 a 5 SM, sem trabalho, moradia própria é sem alerta', () => {
    const r = registro({ renda: '3 a 5 salários mínimos', trabalho: 'Não', tipo_moradia: 'Própria' });
    expect(classificarDimensao('socioeconomica', r)).toBe('ok');
  });
});

describe('dimensão saúde mental', () => {
  test('sem resposta é sem dado', () => {
    expect(classificarDimensao('saude_mental', registro())).toBe('sem_dado');
  });
  test('"Prefiro não responder" é sem dado', () => {
    expect(classificarDimensao('saude_mental', registro({ saude_mental: 'Prefiro não responder' }))).toBe('sem_dado');
  });
  test('muito ruim é crítico', () => {
    expect(classificarDimensao('saude_mental', registro({ saude_mental: 'Muito ruim' }))).toBe('critico');
  });
  test('ruim com estresse frequente é crítico', () => {
    const r = registro({ saude_mental: 'Ruim', estresse: 'Sim, frequentemente' });
    expect(classificarDimensao('saude_mental', r)).toBe('critico');
  });
  test('regular é atenção', () => {
    expect(classificarDimensao('saude_mental', registro({ saude_mental: 'Regular', estresse: 'Não' }))).toBe('atencao');
  });
  test('boa sem estresse é sem alerta', () => {
    expect(classificarDimensao('saude_mental', registro({ saude_mental: 'Boa', estresse: 'Não' }))).toBe('ok');
  });
});

describe('dimensão infraestrutura', () => {
  test('sem respostas é sem dado', () => {
    expect(classificarDimensao('infraestrutura', registro())).toBe('sem_dado');
  });
  test('sem internet é crítico', () => {
    expect(classificarDimensao('infraestrutura', registro({ acesso_internet: 'Não', computador_proprio: 'Sim' }))).toBe('critico');
  });
  test('sem computador próprio com internet é atenção', () => {
    expect(classificarDimensao('infraestrutura', registro({ acesso_internet: 'Sim', computador_proprio: 'Não' }))).toBe('atencao');
  });
  test('internet e computador próprio é sem alerta', () => {
    expect(classificarDimensao('infraestrutura', registro({ acesso_internet: 'Sim', computador_proprio: 'Sim' }))).toBe('ok');
  });
});

describe('sinalização consolidada do aluno (resultado das 4 dimensões)', () => {
  test('qualquer dimensão crítica torna o aluno crítico', () => {
    const r = registro({ CRG: 4, acesso_internet: 'Sim', computador_proprio: 'Sim', saude_mental: 'Boa' });
    expect(classificarAluno(r)).toBe('critico');
  });
  test('atenção prevalece sobre sem alerta e sem dado', () => {
    const r = registro({ CRG: 6 });
    expect(classificarAluno(r)).toBe('atencao');
  });
  test('tudo sem dado é sem dado', () => {
    expect(classificarAluno(registro())).toBe('sem_dado');
  });
  test('todas as dimensões ok é sem alerta', () => {
    const r = registro({
      CRG: 8, renda: '3 a 5 salários mínimos', trabalho: 'Não', tipo_moradia: 'Própria',
      saude_mental: 'Boa', estresse: 'Não', acesso_internet: 'Sim', computador_proprio: 'Sim',
    });
    expect(classificarAluno(r)).toBe('ok');
  });
});

describe('fatores explicativos', () => {
  test('lista os fatores que puxaram a sinalização', () => {
    const r = registro({ renda: 'Até 1 salário mínimo', trabalho: 'Sim, trabalho informal', saude_mental: 'Ruim', computador_proprio: 'Não' });
    expect(fatoresDoRegistro(r)).toEqual([
      'Renda até 1 SM', 'Trabalho informal', 'Saúde mental: ruim', 'Sem computador próprio',
    ]);
  });
  test('registro sem alertas não tem fatores', () => {
    const r = registro({ CRG: 8, renda: '3 a 5 salários mínimos', trabalho: 'Não', saude_mental: 'Boa', acesso_internet: 'Sim', computador_proprio: 'Sim' });
    expect(fatoresDoRegistro(r)).toEqual([]);
  });
});
