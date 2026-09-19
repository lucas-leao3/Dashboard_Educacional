import { describe, expect, test } from 'vitest';
import { ErroApi } from '../data/api';
import type { Lote } from '../data/tipos';
import { criarFluxoLote } from './fluxoLote';
import type { ApiLote } from './fluxoLote';

const LOTE: Lote = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2026.1'],
  executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {},
};
const SAIDA = { lote: '2026-09-L01', gravados: ['a.pdf'], ja_existiam: [], ignorados: [], sincronizar: null, atualizar_crg: null };

function apiFalsa(sobrescrever: Partial<ApiLote> = {}): ApiLote & { chamadas: string[] } {
  const chamadas: string[] = [];
  return {
    chamadas,
    abrirLote: async () => { chamadas.push('abrir'); return LOTE; },
    enviarHistoricos: async () => { chamadas.push('enviar'); return SAIDA; },
    fecharLote: async () => { chamadas.push('fechar'); return { ...LOTE, fechado_em: '2026-09-12T11:00:00Z' }; },
    ...sobrescrever,
  };
}

describe('criarFluxoLote', () => {
  test('caso feliz: cada ação chama recarregar depois de dar certo', async () => {
    const api = apiFalsa();
    let recarregado = 0;
    const fluxo = criarFluxoLote({ api, recarregar: async () => { recarregado++; }, confirmar: () => true });
    expect(await fluxo.abrir({ id: LOTE.id, periodos_cobertos: ['2026.1'], executado_por: null })).toEqual({ ok: true, dados: LOTE });
    expect(await fluxo.enviar(LOTE.id, [new File(['x'], 'a.pdf')])).toEqual({ ok: true, dados: SAIDA });
    expect((await fluxo.fechar(LOTE.id)).ok).toBe(true);
    expect(recarregado).toBe(3);
    expect(api.chamadas).toEqual(['abrir', 'enviar', 'fechar']);
  });

  test('erro da API vira { ok: false, erro: detail, status } e não recarrega', async () => {
    const api = apiFalsa({ enviarHistoricos: async () => { throw new ErroApi(409, 'Passo 2 já foi executado'); } });
    let recarregado = 0;
    const fluxo = criarFluxoLote({ api, recarregar: async () => { recarregado++; } });
    expect(await fluxo.enviar(LOTE.id, [])).toEqual({ ok: false, erro: 'Passo 2 já foi executado', status: 409 });
    expect(recarregado).toBe(0);
  });

  test('fechar sem confirmação não chama a API', async () => {
    const api = apiFalsa();
    const fluxo = criarFluxoLote({ api, recarregar: async () => {}, confirmar: () => false });
    expect(await fluxo.fechar(LOTE.id)).toEqual({ ok: false, erro: null, status: 0 });
    expect(api.chamadas).toEqual([]);
  });
});
