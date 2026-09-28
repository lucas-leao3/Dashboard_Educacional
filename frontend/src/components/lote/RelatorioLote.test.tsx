import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import type { ReactElement } from 'react';
import type { Lote, Relatorio } from '../../data/tipos';
import RelatorioLote from './RelatorioLote';

const LOTE: Lote = {
  id: '2026-09-L02', executado_em: '2026-09-25T10:00:00Z', fechado_em: '2026-09-25T10:01:00Z', periodos_cobertos: ['2025.2'],
  executado_por: 'Edinaldo', observacao: null, ingestoes: [], excecoes_por_motivo: {},
};
const completo = { campos_avaliados: 13, qtd_campos_sem_resposta: 0, campos_sem_resposta: [], percentual_preenchimento: 100 };
const RELATORIO: Relatorio = {
  lote: LOTE.id,
  resumo: { total: 4, integrados: 2, nao_integrados: 2, por_motivo: { sem_academico: 1, falha_identificacao: 1 }, preenchimento_medio_integrados: 92.3 },
  integrados: [
    { matricula: 202016040011, nome: 'JOAO SILVA', academico: true, socioeconomico: true, status: 'Integrado com sucesso',
      campos_avaliados: 13, qtd_campos_sem_resposta: 2, campos_sem_resposta: ['renda_familiar', 'transporte'], percentual_preenchimento: 84.6 },
    { matricula: 202116040020, nome: 'MARIA SANTOS', academico: true, socioeconomico: true, status: 'Integrado com sucesso', ...completo },
  ],
  nao_integrados: [
    { matricula: 202285640003, nome: null, academico: false, socioeconomico: true, motivo: 'sem_academico',
      motivo_descricao: 'Possui socioeconômico e não possui acadêmico', detalhe: null,
      campos_avaliados: 12, qtd_campos_sem_resposta: 1, campos_sem_resposta: ['renda'], percentual_preenchimento: 91.7 },
    { matricula: null, nome: null, academico: false, socioeconomico: false, motivo: 'falha_identificacao',
      motivo_descricao: 'Falha de identificação', detalhe: 'x.pdf: Histórico sem matrícula',
      campos_avaliados: 0, qtd_campos_sem_resposta: 0, campos_sem_resposta: [], percentual_preenchimento: null },
  ],
};
const render = (el: ReactElement) => renderToString(el).replace(/<!-- -->/g, '');

describe('RelatorioLote', () => {
  test('cabeçalho traz responsável, período extraído e fechamento', () => {
    const html = render(<RelatorioLote lote={LOTE} relatorio={RELATORIO} erro={null} />);
    expect(html).toContain('Relatório do lote 2026-09-L02');
    expect(html).toContain('Responsável: Edinaldo');
    expect(html).toContain('Período: 2025.2');
    expect(html).toContain('Fechado em');
  });

  test('KPIs de integração', () => {
    const html = render(<RelatorioLote lote={LOTE} relatorio={RELATORIO} erro={null} />);
    expect(html).toMatch(/Integrados<\/p><p[^>]*>2</);
    expect(html).toMatch(/Não integrados<\/p><p[^>]*>2</);
    expect(html).toContain('92,3%');
  });

  test('as duas tabelas, com as colunas pedidas e a completude', () => {
    const html = render(<RelatorioLote lote={LOTE} relatorio={RELATORIO} erro={null} />);
    expect(html).toContain('Dados não integrados (2)');
    expect(html).toContain('Dados integrados (2)');
    for (const coluna of ['Matrícula', 'Nome', 'Acadêmico', 'Socioeconômico', 'Motivo', 'Status', 'Sem resposta', 'Campos sem resposta', 'Preenchimento']) {
      expect(html).toContain(`>${coluna}<`);
    }
    expect(html).toContain('Integrado com sucesso');
    expect(html).toContain('renda_familiar, transporte');
    expect(html).toContain('>nenhum<');
    expect(html).toContain('84,6%');
    expect(html).toContain('Possui socioeconômico e não possui acadêmico');
    expect(html).toContain('Falha de identificação');
    expect(html).toContain('x.pdf: Histórico sem matrícula');
  });

  test('não integrados vêm antes dos integrados (é o que pede ação)', () => {
    const html = render(<RelatorioLote lote={LOTE} relatorio={RELATORIO} erro={null} />);
    expect(html.indexOf('Dados não integrados')).toBeLessThan(html.indexOf('Dados integrados'));
  });

  test('carregando e erro', () => {
    expect(render(<RelatorioLote lote={LOTE} relatorio={null} erro={null} />)).toContain('Carregando');
    expect(render(<RelatorioLote lote={LOTE} relatorio={null} erro="HTTP 500" />)).toContain('Não foi possível carregar o relatório');
  });
});
