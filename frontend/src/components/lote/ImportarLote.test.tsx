import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import type { ComponentProps } from 'react';
import type { ImportacaoOut } from '../../data/tipos';
import ImportarLote from './ImportarLote';

const nada = () => {};
const render = (extra: Partial<ComponentProps<typeof ImportarLote>> = {}) =>
  renderToString(<ImportarLote ocupado={false} erro={null} resultado={null} onImportar={nada} {...extra} />).replace(/<!-- -->/g, '');

const RESULTADO: ImportacaoOut = {
  id: '2026-09-L02', executado_em: '2026-09-25T10:00:00Z', fechado_em: '2026-09-25T10:01:00Z', periodos_cobertos: ['2025.2'],
  executado_por: 'Edinaldo', observacao: null, ingestoes: [], excecoes_por_motivo: {},
  arquivos: { gravados: ['a.pdf', 'b.pdf'], ja_existiam: [], ignorados: ['leiame.txt'] }, sincronizar: {}, atualizar_crg: {},
  arquivos_gerados: [], resumo: { total: 3, integrados: 2, nao_integrados: 1, por_motivo: { sem_academico: 1 }, preenchimento_medio_integrados: 80 },
};

describe('ImportarLote', () => {
  test('pede só o responsável e um .zip -- nada de período nem id', () => {
    const html = render();
    expect(html).toContain('Responsável pela importação');
    expect(html).toContain('accept=".zip"');
    expect(html.match(/<input/g)).toHaveLength(2);
    expect(html).not.toContain('Períodos');
    expect(html).not.toContain('Id do lote');
    expect(html).not.toContain('multiple');
  });
  test('botão começa desabilitado (falta responsável e arquivo)', () => {
    expect(render()).toMatch(/<button type="submit" disabled=""/);
  });
  test('avisa que o lote é fechado ao terminar', () => {
    expect(render()).toContain('não pode ser editado, receber arquivos nem ser reprocessado');
  });
  test('erro da API aparece e diz que nada foi gravado', () => {
    const html = render({ erro: 'Erro ao consultar o FasiTech' });
    expect(html).toContain('Erro ao consultar o FasiTech');
    expect(html).toContain('nada foi gravado');
  });
  test('resultado mostra o lote, o período extraído e a integração', () => {
    const html = render({ resultado: RESULTADO });
    expect(html).toContain('Lote 2026-09-L02 importado e fechado');
    expect(html).toContain('Período (extraído dos históricos): 2025.2');
    expect(html).toContain('2 histórico(s) gravado(s), 1 ignorado(s): leiame.txt');
    expect(html).toContain('2 aluno(s) integrado(s), 1 não integrado(s)');
  });
});
