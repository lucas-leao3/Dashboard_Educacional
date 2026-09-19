import { ErroApi } from '../data/api';
import type { NovoLote } from '../data/api';
import type { HistoricosOut, Lote } from '../data/tipos';

/** O que a orquestração precisa da API — injetável para teste. */
export interface ApiLote {
  abrirLote(dados: NovoLote): Promise<Lote>;
  enviarHistoricos(id: string, arquivos: File[]): Promise<HistoricosOut>;
  fecharLote(id: string): Promise<Lote>;
}

export type Resultado<T> = { ok: true; dados: T } | { ok: false; erro: string | null; status: number };

export const TEXTO_FECHAR = 'Fechar é definitivo: o lote não se reabre nem recebe mais PDFs. Confirmar?';

interface Deps {
  api: ApiLote;
  recarregar: () => Promise<void>;
  /** Confirmação do fechar. Padrão: window.confirm. */
  confirmar?: () => boolean;
}

/**
 * As três ações da tela Dados, sem React: cada uma chama a API, recarrega o
 * DadosProvider se deu certo e devolve um Resultado que a tela só exibe.
 * A máquina de estados avança pelo recarregar, nunca por estado local.
 */
export function criarFluxoLote({ api, recarregar, confirmar = () => window.confirm(TEXTO_FECHAR) }: Deps) {
  async function executar<T>(acao: () => Promise<T>): Promise<Resultado<T>> {
    try {
      const dados = await acao();
      await recarregar();
      return { ok: true, dados };
    } catch (e) {
      if (e instanceof ErroApi) return { ok: false, erro: e.detail, status: e.status };
      return { ok: false, erro: String(e), status: 0 };
    }
  }
  return {
    abrir: (dados: NovoLote) => executar(() => api.abrirLote(dados)),
    enviar: (id: string, arquivos: File[]) => executar(() => api.enviarHistoricos(id, arquivos)),
    fechar: async (id: string): Promise<Resultado<Lote>> =>
      confirmar() ? executar(() => api.fecharLote(id)) : { ok: false, erro: null, status: 0 },
  };
}
