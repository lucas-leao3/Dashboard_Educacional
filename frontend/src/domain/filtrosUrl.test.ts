import { describe, expect, test } from 'vitest';
import { comFiltro, lerFiltro, queryDe } from './filtrosUrl';

describe('filtros na URL', () => {
  test('ausente = padrão', () => {
    expect(lerFiltro(new URLSearchParams(''), 'polo', 'Todos')).toBe('Todos');
    expect(lerFiltro(new URLSearchParams('polo=Oeiras'), 'polo', 'Todos')).toBe('Oeiras');
  });
  test('valor padrão sai da URL e os outros filtros ficam', () => {
    const p = comFiltro(new URLSearchParams('polo=Oeiras&dimensao=renda'), 'polo', 'Todos', 'Todos');
    expect(p.toString()).toBe('dimensao=renda');
    expect(comFiltro(p, 'polo', 'Cametá', 'Todos').get('polo')).toBe('Cametá');
  });
  test('queryDe ignora vazios e codifica acento', () => {
    expect(queryDe({ polo: 'Cametá', periodo: undefined, turma: '' })).toBe('?polo=Camet%C3%A1');
    expect(queryDe({})).toBe('');
  });
});
