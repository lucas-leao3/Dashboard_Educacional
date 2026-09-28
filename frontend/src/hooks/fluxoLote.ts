import { ErroApi } from '../data/api';
import type { ImportacaoOut } from '../data/tipos';

/** O que a orquestração precisa da API — injetável para teste. */
export interface ApiLote {
  importarLote(responsavel: string, arquivo: File): Promise<ImportacaoOut>;
}

export type Resultado<T> = { ok: true; dados: T } | { ok: false; erro: string | null; status: number };

export const TEXTO_CONFIRMAR =
  'A importação cria um lote novo e o fecha ao terminar: depois não é possível editar, enviar mais arquivos nem reprocessar. Confirmar?';

interface Deps {
  api: ApiLote;
  recarregar: () => Promise<void>;
  /** Confirmação da importação. Padrão: window.confirm. */
  confirmar?: () => boolean;
}

/**
 * A ação da tela Dados, sem React: confirma, chama a API, recarrega o
 * DadosProvider se deu certo e devolve um Resultado que a tela só exibe.
 */
export function criarFluxoLote({ api, recarregar, confirmar = () => window.confirm(TEXTO_CONFIRMAR) }: Deps) {
  return {
    importar: async (responsavel: string, arquivo: File): Promise<Resultado<ImportacaoOut>> => {
      if (!confirmar()) return { ok: false, erro: null, status: 0 };
      try {
        const dados = await api.importarLote(responsavel.trim(), arquivo);
        await recarregar();
        return { ok: true, dados };
      } catch (e) {
        if (e instanceof ErroApi) return { ok: false, erro: e.detail, status: e.status };
        return { ok: false, erro: String(e), status: 0 };
      }
    },
  };
}
