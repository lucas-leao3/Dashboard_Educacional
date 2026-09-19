import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import type { ComponentProps } from 'react';
import type { Lote } from '../../data/tipos';
import InserirLote from './InserirLote';

const base: Lote = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2026.1'],
  executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {},
};
const ingestao = (passo: number) => ({ id: passo, passo, arquivo_sha256: null, executado_em: '2026-09-12T10:00:00Z', registros_lidos: 1, registros_aceitos: 1, registros_rejeitados: 0 });
const nada = () => {};
const render = (lote: Lote | null, extra: Partial<ComponentProps<typeof InserirLote>> = {}) =>
  renderToString(<InserirLote lote={lote} lotes={[]} ocupado={false} erro={null} resultadoEnvio={null} onAbrir={nada} onEnviar={nada} onFechar={nada} {...extra} />).replace(/<!-- -->/g, '');

describe('InserirLote', () => {
  test('sem lote: passo 1 com id sugerido e campo de períodos', () => {
    const html = render(null);
    expect(html).toContain('Abrir lote');
    expect(html).toMatch(/value="\d{4}-\d{2}-L01"/);
    expect(html).toContain('Períodos cobertos');
  });
  test('lote sem ingestões: passo 2 com input de arquivos aceitando .zip e .pdf', () => {
    const html = render(base);
    expect(html).toContain('Enviar e rodar');
    expect(html).toContain('type="file"');
    expect(html).toContain('accept=".zip,.pdf"');
  });
  test('lote com passos 1 e 2: passo 3 com botão Fechar lote', () => {
    const html = render({ ...base, ingestoes: [ingestao(1), ingestao(2)] });
    expect(html).toContain('Fechar lote');
    expect(html).not.toContain('type="file"');
  });
  test('lote fechado: selo "Fechado em" e nenhum botão de ação', () => {
    const html = render({ ...base, ingestoes: [ingestao(1), ingestao(2)], fechado_em: '2026-09-12T11:00:00Z' });
    expect(html).toContain('Fechado em');
    expect(html).not.toContain('Fechar lote');
    expect(html).not.toContain('type="file"');
  });
  test('erro aparece no passo atual', () => {
    expect(render(base, { erro: 'Passo 2 já foi executado' })).toContain('Passo 2 já foi executado');
  });
  test('resultado do envio mostra gravados e ignorados', () => {
    const html = render({ ...base, ingestoes: [ingestao(1), ingestao(2)] }, {
      resultadoEnvio: { lote: base.id, gravados: ['a.pdf', 'b.pdf'], ja_existiam: [], ignorados: ['leiame.txt'], sincronizar: { importados: 5 }, atualizar_crg: 'ja_executado' },
    });
    expect(html).toContain('2 gravado');
    expect(html).toContain('leiame.txt');
    expect(html).toContain('importados');
  });
});
