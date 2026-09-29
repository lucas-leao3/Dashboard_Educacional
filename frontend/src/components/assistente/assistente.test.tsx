import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import type { ReactElement } from 'react';
import type { RespostaAssistente } from '../../data/tipos';
import Explicacao from './Explicacao';
import RespostaView from './RespostaView';
import Historico from './Historico';

const html = (el: ReactElement) => renderToString(el).replace(/<!-- -->/g, '');
const explicacao = {
  consulta_interpretada: 'Contagem de alunos por Polo', filtros_aplicados: [{ rotulo: 'Turma', valor: '2020' }],
  fontes: ['aluno_integrado'], forma: 'tabela' as const,
};
function resposta(parcial: Partial<RespostaAssistente>): RespostaAssistente {
  return { id: 'r1', pergunta: 'Pergunta?', consulta: null, forma: 'texto', explicacao, dashboard: null,
    dinamico: null, tabela: null, texto: null, nao_entendi: null, ...parcial };
}
const nada = () => {};

describe('respostas do assistente', () => {
  test('explicação mostra o que entendeu, filtros, fonte e forma', () => {
    const h = html(<Explicacao explicacao={explicacao} />);
    for (const t of ['Consulta interpretada', 'Contagem de alunos por Polo', 'Turma: 2020', 'aluno_integrado', 'Tabela']) expect(h).toContain(t);
    expect(html(<Explicacao explicacao={{ ...explicacao, filtros_aplicados: [] }} />)).toContain('Nenhum');
  });
  test('tabela pagina de 25 em 25, mostra o total e exporta', () => {
    const linhas = Array.from({ length: 30 }, (_, i) => ({ matricula: 202016040000 + i, crg: 7.5 }));
    const h = html(<RespostaView resposta={resposta({ forma: 'tabela', tabela: { colunas: [{ id: 'matricula', rotulo: 'Matrícula' }, { id: 'crg', rotulo: 'CRG' }], linhas, total: 30 } })} onSugestao={nada} />);
    expect(h).toContain('30 registro(s)');
    expect(h).toContain('Página 1 de 2');
    expect(h).toContain('Exportar CSV');
    expect(h.match(/<tr/g)).toHaveLength(26);
    expect(h).toContain('202016040000'); // matrícula sem separador de milhar
    expect(h).toContain('7,5');
  });
  test('texto', () => {
    expect(html(<RespostaView resposta={resposta({ texto: { mensagem: '2 aluno(s) integrado(s).', valor: 2, n: 2 } })} onSugestao={nada} />))
      .toContain('2 aluno(s) integrado(s).');
  });
  test('não entendi traz o motivo e as sugestões', () => {
    const h = html(<RespostaView resposta={resposta({ forma: 'nao_entendi', nao_entendi: { motivo: 'Não há dado de evasão.', sugestoes: ['Quantos alunos existem por polo?'] } })} onSugestao={nada} />);
    expect(h).toContain('Não há dado de evasão.');
    expect(h).toContain('Quantos alunos existem por polo?');
  });
  test('dinâmico mostra título e o n de cada grupo', () => {
    const grafico = { tipo: 'barras' as const, titulo: 'Contagem de alunos por Polo', eixo: 'polo', serie: null, series: [],
      serie_ordinal: false, rotulo_valor: 'Alunos', dados: [{ polo: 'Cametá', valor: 2, n: 2 }, { polo: 'Oeiras', valor: 1, n: 1 }] };
    const h = html(<RespostaView resposta={resposta({ forma: 'dinamico', dinamico: { kpis: [], graficos: [grafico] } })} onSugestao={nada} />);
    expect(h).toContain('Contagem de alunos por Polo');
    expect(h).toContain('Cametá n=2');
    expect(h).toContain('Oeiras n=1');
  });
  test('histórico lista favoritos primeiro, com as quatro ações', () => {
    const consulta = { tipo: 'agregado' as const, metrica: 'x', dimensoes: [], filtros: [], ordem: null, limite: null, interpretacao: '' };
    const itens = [
      { id: 'a', pergunta: 'Primeira', consulta, forma: 'texto' as const, quando: '', favorito: false, rota: null },
      { id: 'b', pergunta: 'Favorita', consulta, forma: 'texto' as const, quando: '', favorito: true, rota: null },
    ];
    const h = html(<Historico itens={itens} onRepetir={nada} onEditar={nada} onFavoritar={nada} onCompartilhar={nada} />);
    expect(h.indexOf('Favorita')).toBeLessThan(h.indexOf('Primeira'));
    for (const acao of ['Repetir', 'Editar', 'Desfavoritar', 'Compartilhar']) expect(h).toContain(acao);
  });
});
