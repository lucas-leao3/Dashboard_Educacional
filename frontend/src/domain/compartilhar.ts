import { ErroApi } from '../data/api';
import type { ConsultaEstruturada, RespostaAssistente } from '../data/tipos';
import type { ItemHistorico } from './historico';

/** base64url do JSON em UTF-8: cabe na URL e aguenta acento. */
export function codificarConsulta(consulta: ConsultaEstruturada): string {
  let binario = '';
  new TextEncoder().encode(JSON.stringify(consulta)).forEach((b) => { binario += String.fromCharCode(b); });
  return btoa(binario).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** null para qualquer coisa que não seja uma consulta: link adulterado não quebra a tela. */
export function decodificarConsulta(codigo: string): ConsultaEstruturada | null {
  try {
    const b64 = codigo.replace(/-/g, '+').replace(/_/g, '/');
    const binario = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4));
    const lido: unknown = JSON.parse(new TextDecoder().decode(Uint8Array.from(binario, (c) => c.charCodeAt(0))));
    if (!lido || typeof lido !== 'object' || Array.isArray(lido) || typeof (lido as { tipo?: unknown }).tipo !== 'string') return null;
    return lido as ConsultaEstruturada;
  } catch {
    return null;
  }
}

export const LINK_INVALIDO = 'Link de consulta inválido.';

/**
 * Reexecuta a consulta de um link `?c=`. Link que não decodifica, ou que o
 * backend recusa (422: fora do catálogo), vira uma mensagem só, em vez do
 * erro de validação cru; os demais erros (API fora) passam como vieram.
 */
export async function executarDoLink(
  codigo: string, executar: (consulta: ConsultaEstruturada) => Promise<RespostaAssistente>,
): Promise<RespostaAssistente> {
  const consulta = decodificarConsulta(codigo);
  if (!consulta) throw new ErroApi(422, LINK_INVALIDO);
  try {
    return await executar(consulta);
  } catch (e) {
    if (e instanceof ErroApi && e.status === 422) throw new ErroApi(422, LINK_INVALIDO);
    throw e;
  }
}

/** Dashboard: a própria URL da tela filtrada. Demais formas: /ia-chat?c=, que reexecuta sem LLM. */
export function linkDeCompartilhamento(item: Pick<ItemHistorico, 'consulta' | 'rota'>, origem: string): string {
  return item.rota ? `${origem}${item.rota}` : `${origem}/ia-chat?c=${codificarConsulta(item.consulta)}`;
}
