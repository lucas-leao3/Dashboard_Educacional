import { describe, expect, test } from 'vitest';
import { ErroApi } from '../data/api';
import type { ImportacaoOut } from '../data/tipos';
import { criarFluxoLote } from './fluxoLote';
import type { ApiLote } from './fluxoLote';

const SAIDA: ImportacaoOut = {
  id: '2026-09-L02', executado_em: '2026-09-25T10:00:00Z', fechado_em: '2026-09-25T10:01:00Z', periodos_cobertos: ['2025.2'],
  executado_por: 'Edinaldo', observacao: null, ingestoes: [], excecoes_por_motivo: {},
  arquivos: { gravados: ['a.pdf'], ja_existiam: [], ignorados: [] }, sincronizar: {}, atualizar_crg: {}, arquivos_gerados: [],
  resumo: { total: 1, integrados: 1, nao_integrados: 0, por_motivo: {}, preenchimento_medio_integrados: 100 },
};
const ZIP = new File(['PK'], 'historicos.zip');

function apiFalsa(importarLote: ApiLote['importarLote'] = async () => SAIDA) {
  const chamadas: [string, string][] = [];
  const api: ApiLote = { importarLote: async (r, a) => { chamadas.push([r, a.name]); return importarLote(r, a); } };
  return { api, chamadas };
}

describe('criarFluxoLote', () => {
  test('caso feliz: importa com o responsável sem espaços e recarrega', async () => {
    const { api, chamadas } = apiFalsa();
    let recarregado = 0;
    const fluxo = criarFluxoLote({ api, recarregar: async () => { recarregado++; }, confirmar: () => true });
    expect(await fluxo.importar('  Edinaldo ', ZIP)).toEqual({ ok: true, dados: SAIDA });
    expect(chamadas).toEqual([['Edinaldo', 'historicos.zip']]);
    expect(recarregado).toBe(1);
  });

  test('erro da API vira { ok: false, erro: detail, status } e não recarrega', async () => {
    const { api } = apiFalsa(async () => { throw new ErroApi(502, 'FasiTech fora do ar'); });
    let recarregado = 0;
    const fluxo = criarFluxoLote({ api, recarregar: async () => { recarregado++; }, confirmar: () => true });
    expect(await fluxo.importar('Edi', ZIP)).toEqual({ ok: false, erro: 'FasiTech fora do ar', status: 502 });
    expect(recarregado).toBe(0);
  });

  test('sem confirmação não chama a API', async () => {
    const { api, chamadas } = apiFalsa();
    const fluxo = criarFluxoLote({ api, recarregar: async () => {}, confirmar: () => false });
    expect(await fluxo.importar('Edi', ZIP)).toEqual({ ok: false, erro: null, status: 0 });
    expect(chamadas).toEqual([]);
  });
});
