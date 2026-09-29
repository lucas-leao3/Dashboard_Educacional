import { describe, expect, test } from 'vitest';
import type { ConsultaEstruturada } from '../data/tipos';
import { rotaDoDashboard } from './catalogoDashboards';
import { adicionar, alternarFavorito, carregarHistorico, LIMITE_HISTORICO, ordenarParaExibir, salvarHistorico } from './historico';
import type { ItemHistorico } from './historico';
import { codificarConsulta, decodificarConsulta, linkDeCompartilhamento } from './compartilhar';
import { paraCsv } from './csv';
import { corDaSerie, pivotar } from './graficoDinamico';

const consulta: ConsultaEstruturada = {
  tipo: 'agregado', metrica: 'contagem_alunos', dimensoes: ['polo'],
  filtros: [{ campo: 'polo', op: '=', valor: 'Cametá' }], ordem: null, limite: null, interpretacao: 'Alunos em Cametá',
};
const item = (id: string, favorito = false): ItemHistorico => ({
  id, pergunta: `p${id}`, consulta, forma: 'dinamico', quando: '2026-09-25T00:00:00Z', favorito, rota: null,
});

describe('rotas dos dashboards', () => {
  test('cada id monta a rota com os filtros', () => {
    expect(rotaDoDashboard('polos', {})).toBe('/');
    expect(rotaDoDashboard('polos', { periodo: '2025.(3 e 4)' })).toBe('/?periodo=2025.%283+e+4%29');
    expect(rotaDoDashboard('turmas', { polo: 'Cametá' })).toBe('/polo/Camet%C3%A1');
    expect(rotaDoDashboard('alunos_turma', { polo: 'Oeiras', turma: '2021' })).toBe('/polo/Oeiras/turma/2021');
    expect(rotaDoDashboard('perfil', { matricula: '202016040001' })).toBe('/aluno/202016040001');
    expect(rotaDoDashboard('bidimensional', { dimensao: 'renda' })).toBe('/analises/bidimensional?dimensao=renda');
    expect(rotaDoDashboard('longitudinal', { turma: '2020' })).toBe('/analises/longitudinal?turma=2020');
    expect(rotaDoDashboard('inexistente', {})).toBeNull();
  });
});

describe('histórico', () => {
  test('mais recente primeiro; ao passar do limite sai o não favorito mais antigo', () => {
    let itens: ItemHistorico[] = [item('antigo-favorito', true)];
    for (let i = 0; i < LIMITE_HISTORICO; i++) itens = adicionar(itens, item(String(i)));
    expect(itens).toHaveLength(LIMITE_HISTORICO);
    expect(itens[0].id).toBe(String(LIMITE_HISTORICO - 1));
    expect(itens.some((i) => i.id === 'antigo-favorito')).toBe(true);
    expect(itens.some((i) => i.id === '0')).toBe(false);
  });
  test('favoritos no topo da exibição', () => {
    const itens = alternarFavorito([item('a'), item('b')], 'b');
    expect(ordenarParaExibir(itens).map((i) => i.id)).toEqual(['b', 'a']);
  });
  test('armazenamento corrompido, indisponível ou cheio não quebra', () => {
    expect(carregarHistorico({ getItem: () => '{nao json', setItem: () => {} })).toEqual([]);
    expect(carregarHistorico({ getItem: () => { throw new Error('bloqueado'); }, setItem: () => {} })).toEqual([]);
    expect(() => salvarHistorico([item('a')], { getItem: () => null, setItem: () => { throw new Error('cota'); } })).not.toThrow();
  });
  test('ida e volta pelo armazenamento', () => {
    const memoria = new Map<string, string>();
    const armazenamento = { getItem: (k: string) => memoria.get(k) ?? null, setItem: (k: string, v: string) => { memoria.set(k, v); } };
    salvarHistorico([item('a')], armazenamento);
    expect(carregarHistorico(armazenamento).map((i) => i.id)).toEqual(['a']);
  });
});

describe('compartilhar', () => {
  test('codifica e decodifica com acento', () => {
    expect(decodificarConsulta(codificarConsulta(consulta))).toEqual(consulta);
  });
  test('código adulterado vira null', () => {
    expect(decodificarConsulta('%%%')).toBeNull();
    expect(decodificarConsulta(btoa('[1,2]'))).toBeNull();
  });
  test('dashboard compartilha a rota; o resto compartilha a consulta', () => {
    expect(linkDeCompartilhamento({ ...item('a'), rota: '/polo/Oeiras' }, 'http://x')).toBe('http://x/polo/Oeiras');
    expect(linkDeCompartilhamento(item('a'), 'http://x')).toBe(`http://x/ia-chat?c=${codificarConsulta(consulta)}`);
  });
});

describe('csv', () => {
  test('separador ;, decimal com vírgula, aspas quando precisa e BOM', () => {
    const csv = paraCsv([{ id: 'nome', rotulo: 'Nome' }, { id: 'crg', rotulo: 'CRG' }],
      [{ nome: 'Ana; Maria', crg: 7.5 }, { nome: null, crg: null }]);
    expect(csv).toBe('﻿Nome;CRG\r\n"Ana; Maria";7,5\r\n;');
  });
});

describe('gráfico dinâmico', () => {
  test('pivota por série na ordem dada', () => {
    const dados = [{ polo: 'Cametá', renda: 'B', percentual: 60 }, { polo: 'Cametá', renda: 'A', percentual: 40 },
      { polo: 'Oeiras', renda: 'A', percentual: 100 }];
    expect(pivotar(dados, 'polo', 'renda', 'percentual', ['A', 'B'])).toEqual({
      linhas: [{ polo: 'Cametá', B: 60, A: 40 }, { polo: 'Oeiras', A: 100 }], series: ['A', 'B'],
    });
    expect(pivotar([{ polo: 'Cametá', valor: 2 }], 'polo', null, 'valor', [])).toEqual({
      linhas: [{ polo: 'Cametá', valor: 2 }], series: ['valor'],
    });
  });
  test('ausência é cinza; ordinal segue a rampa; polo mantém a cor fixa', () => {
    expect(corDaSerie('Sem resposta', ['A', 'Sem resposta'], 'renda', true)).toBe('#94a3b8');
    const rampa = ['A', 'B', 'C'].map((s) => corDaSerie(s, ['A', 'B', 'C'], 'renda', true));
    expect(new Set(rampa).size).toBe(3);
    expect(corDaSerie('Cametá', ['Cametá', 'Oeiras'], 'polo', false)).toBe('#2563eb');
  });
});
