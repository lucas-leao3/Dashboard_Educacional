import { describe, expect, test } from 'vitest';
import { carregarLotes, carregarRegistros } from './api';
import { registro } from '../test/fixtures';

describe('carregarRegistros', () => {
  test('usa a API quando ela responde', async () => {
    const dados = [registro({ matricula: 99 })];
    const fetchFalso = async () => new Response(JSON.stringify(dados), { status: 200 });
    const resultado = await carregarRegistros({ baseUrl: '/api', fetchFn: fetchFalso });
    expect(resultado.origem).toBe('api');
    expect(resultado.registros.map((r) => r.matricula)).toEqual([99]);
  });
  test('cai no dataset de demonstração quando a API falha', async () => {
    const fetchFalso = async () => { throw new Error('rede'); };
    const resultado = await carregarRegistros({ baseUrl: '/api', fetchFn: fetchFalso });
    expect(resultado.origem).toBe('demonstracao');
    expect(resultado.registros.length).toBeGreaterThan(0);
  });
  test('cai no dataset de demonstração em resposta não-2xx', async () => {
    const fetchFalso = async () => new Response('erro', { status: 500 });
    const resultado = await carregarRegistros({ baseUrl: '/api', fetchFn: fetchFalso });
    expect(resultado.origem).toBe('demonstracao');
  });
  test('sem baseUrl vai direto para a demonstração, sem chamar fetch', async () => {
    let chamado = false;
    const fetchFalso = async () => { chamado = true; return new Response('[]'); };
    const resultado = await carregarRegistros({ baseUrl: '', fetchFn: fetchFalso });
    expect(chamado).toBe(false);
    expect(resultado.origem).toBe('demonstracao');
  });
});

describe('carregarLotes', () => {
  test('devolve os lotes quando a API responde', async () => {
    const lotes = [{ id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2026.1'], executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {} }];
    const fetchFalso = async () => new Response(JSON.stringify(lotes), { status: 200 });
    const resultado = await carregarLotes({ baseUrl: '/api', fetchFn: fetchFalso });
    expect(resultado).toEqual(lotes);
  });
  test('devolve [] quando a API falha', async () => {
    const fetchFalso = async () => { throw new Error('rede'); };
    expect(await carregarLotes({ baseUrl: '/api', fetchFn: fetchFalso })).toEqual([]);
  });
  test('devolve [] em resposta não-2xx', async () => {
    const fetchFalso = async () => new Response('erro', { status: 500 });
    expect(await carregarLotes({ baseUrl: '/api', fetchFn: fetchFalso })).toEqual([]);
  });
  test('sem baseUrl devolve [] sem chamar fetch', async () => {
    let chamado = false;
    const fetchFalso = async () => { chamado = true; return new Response('[]'); };
    expect(await carregarLotes({ baseUrl: '', fetchFn: fetchFalso })).toEqual([]);
    expect(chamado).toBe(false);
  });
});

import { ErroApi, abrirLote, carregarCorrespondencia, enviarHistoricos, fecharLote } from './api';

const LOTE = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null,
  periodos_cobertos: ['2026.1'], executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {},
};

describe('escrita na API (abrirLote, enviarHistoricos, fecharLote)', () => {
  test('abrirLote faz POST /lotes com JSON e devolve o lote', async () => {
    let capturado: { url: string; init?: RequestInit } | null = null;
    const fetchFalso = async (url: string | URL | Request, init?: RequestInit) => {
      capturado = { url: String(url), init };
      return new Response(JSON.stringify(LOTE), { status: 201 });
    };
    const lote = await abrirLote({ id: '2026-09-L01', periodos_cobertos: ['2026.1'], executado_por: 'Edi' }, { baseUrl: '/api', fetchFn: fetchFalso });
    expect(lote.id).toBe('2026-09-L01');
    expect(capturado!.url).toBe('/api/lotes');
    expect(capturado!.init?.method).toBe('POST');
    expect(JSON.parse(String(capturado!.init?.body))).toEqual({ id: '2026-09-L01', periodos_cobertos: ['2026.1'], executado_por: 'Edi' });
  });

  test('enviarHistoricos manda multipart com um campo "arquivos" por arquivo e executar=true', async () => {
    let capturado: { url: string; init?: RequestInit } | null = null;
    const fetchFalso = async (url: string | URL | Request, init?: RequestInit) => {
      capturado = { url: String(url), init };
      return new Response(JSON.stringify({ lote: '2026-09-L01', gravados: ['a.pdf'], ja_existiam: [], ignorados: [], sincronizar: null, atualizar_crg: null }), { status: 200 });
    };
    const arquivos = [new File(['x'], 'a.pdf'), new File(['y'], 'b.zip')];
    const saida = await enviarHistoricos('2026-09-L01', arquivos, { baseUrl: '/api', fetchFn: fetchFalso });
    expect(saida.gravados).toEqual(['a.pdf']);
    expect(capturado!.url).toBe('/api/lotes/2026-09-L01/historicos?executar=true');
    const form = capturado!.init?.body as FormData;
    expect(form.getAll('arquivos').map((f) => (f as File).name)).toEqual(['a.pdf', 'b.zip']);
  });

  test('erro HTTP vira ErroApi com o detail do FastAPI', async () => {
    const fetchFalso = async () => new Response(JSON.stringify({ detail: 'Passo 2 já foi executado' }), { status: 409 });
    await expect(fecharLote('2026-09-L01', { baseUrl: '/api', fetchFn: fetchFalso })).rejects.toMatchObject({ status: 409, detail: 'Passo 2 já foi executado' });
  });

  test('fetch rejeitado vira ErroApi "Sem resposta da API"', async () => {
    const fetchFalso = async () => { throw new Error('rede'); };
    const erro = await abrirLote({ id: 'x', periodos_cobertos: [], executado_por: null }, { baseUrl: '/api', fetchFn: fetchFalso }).catch((e) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.status).toBe(0);
    expect(erro.detail).toBe('Sem resposta da API');
  });

  test('sem baseUrl a escrita falha em vez de cair na demonstração', async () => {
    await expect(fecharLote('x', { baseUrl: '' })).rejects.toBeInstanceOf(ErroApi);
  });

  test('carregarCorrespondencia devolve as linhas', async () => {
    const linhas = [{ matricula: 100, nome: 'Ana', academico: true, socioeconomico: true, faltando: '' }];
    const fetchFalso = async () => new Response(JSON.stringify(linhas), { status: 200 });
    expect(await carregarCorrespondencia('2026-09-L01', { baseUrl: '/api', fetchFn: fetchFalso })).toEqual(linhas);
  });
});
