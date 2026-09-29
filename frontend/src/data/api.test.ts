import { describe, expect, test } from 'vitest';
import { carregarLotes, carregarRegistros, executarConsulta, perguntarAssistente } from './api';
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

import { ErroApi, carregarRelatorio, importarLote } from './api';

const IMPORTACAO = {
  id: '2026-09-L02', executado_em: '2026-09-25T10:00:00Z', fechado_em: '2026-09-25T10:01:00Z',
  periodos_cobertos: ['2025.2'], executado_por: 'Edinaldo', observacao: null, ingestoes: [], excecoes_por_motivo: {},
  arquivos: { gravados: ['a.pdf'], ja_existiam: [], ignorados: [] }, sincronizar: {}, atualizar_crg: {},
  arquivos_gerados: [], resumo: { total: 1, integrados: 1, nao_integrados: 0, por_motivo: {}, preenchimento_medio_integrados: 100 },
};

describe('escrita na API (importarLote)', () => {
  test('importarLote manda multipart só com responsavel e arquivo', async () => {
    let capturado: { url: string; init?: RequestInit } | null = null;
    const fetchFalso = async (url: string | URL | Request, init?: RequestInit) => {
      capturado = { url: String(url), init };
      return new Response(JSON.stringify(IMPORTACAO), { status: 201 });
    };
    const saida = await importarLote('Edinaldo', new File(['PK'], 'historicos.zip'), { baseUrl: '/api', fetchFn: fetchFalso });
    expect(saida.id).toBe('2026-09-L02');
    expect(capturado!.url).toBe('/api/lotes/importar');
    expect(capturado!.init?.method).toBe('POST');
    const form = capturado!.init?.body as FormData;
    expect([...form.keys()].sort()).toEqual(['arquivo', 'responsavel']);
    expect(form.get('responsavel')).toBe('Edinaldo');
    expect((form.get('arquivo') as File).name).toBe('historicos.zip');
  });

  test('erro HTTP vira ErroApi com o detail do FastAPI', async () => {
    const fetchFalso = async () => new Response(JSON.stringify({ detail: 'Erro ao consultar o FasiTech' }), { status: 502 });
    await expect(importarLote('Edi', new File(['x'], 'h.zip'), { baseUrl: '/api', fetchFn: fetchFalso }))
      .rejects.toMatchObject({ status: 502, detail: 'Erro ao consultar o FasiTech' });
  });

  test('detail em lista (422 do FastAPI) vira texto', async () => {
    const fetchFalso = async () => new Response(JSON.stringify({ detail: [{ loc: ['body', 'responsavel'], msg: 'Field required' }] }), { status: 422 });
    const erro = await importarLote('', new File(['x'], 'h.zip'), { baseUrl: '/api', fetchFn: fetchFalso }).catch((e) => e);
    expect(erro.status).toBe(422);
    expect(erro.detail).toContain('responsavel');
  });

  test('fetch rejeitado vira ErroApi "Sem resposta da API"', async () => {
    const fetchFalso = async () => { throw new Error('rede'); };
    const erro = await importarLote('Edi', new File(['x'], 'h.zip'), { baseUrl: '/api', fetchFn: fetchFalso }).catch((e) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.status).toBe(0);
    expect(erro.detail).toBe('Sem resposta da API');
  });

  test('sem baseUrl a escrita falha em vez de cair na demonstração', async () => {
    await expect(importarLote('Edi', new File(['x'], 'h.zip'), { baseUrl: '' })).rejects.toBeInstanceOf(ErroApi);
  });

  test('carregarRelatorio lê GET /lotes/{id}/relatorio', async () => {
    const relatorio = { lote: '2026-09-L02', resumo: IMPORTACAO.resumo, integrados: [], nao_integrados: [] };
    let url = '';
    const fetchFalso = async (u: string | URL | Request) => { url = String(u); return new Response(JSON.stringify(relatorio), { status: 200 }); };
    expect(await carregarRelatorio('2026-09-L02', { baseUrl: '/api', fetchFn: fetchFalso })).toEqual(relatorio);
    expect(url).toBe('/api/lotes/2026-09-L02/relatorio');
  });
});

describe('assistente', () => {
  test('pergunta por POST em JSON', async () => {
    // Objeto, e não `let`: o TS estreitaria um `let x = null` atribuído dentro do callback para `never`.
    const visto: { url?: string; init?: RequestInit } = {};
    const fetchFalso = async (url: RequestInfo | URL, init?: RequestInit) => {
      visto.url = String(url);
      visto.init = init;
      return new Response(JSON.stringify({ id: 'r1' }), { status: 200 });
    };
    const resposta = await perguntarAssistente('Quantos alunos?', { baseUrl: '/api', fetchFn: fetchFalso as typeof fetch });
    expect(resposta.id).toBe('r1');
    expect(visto.url).toBe('/api/assistente/perguntar');
    expect(visto.init?.method).toBe('POST');
    expect(JSON.parse(String(visto.init?.body))).toEqual({ pergunta: 'Quantos alunos?' });
  });
  test('503 vira ErroApi com o detail', async () => {
    const fetchFalso = async () => new Response(JSON.stringify({ detail: 'Groq respondeu HTTP 429.' }), { status: 503 });
    await expect(executarConsulta({} as never, { baseUrl: '/api', fetchFn: fetchFalso })).rejects.toMatchObject({
      status: 503, detail: 'Groq respondeu HTTP 429.',
    });
  });
});
