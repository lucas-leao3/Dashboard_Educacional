import type { ConsultaEstruturada } from '../data/tipos';
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

/** Dashboard: a própria URL da tela filtrada. Demais formas: /ia-chat?c=, que reexecuta sem LLM. */
export function linkDeCompartilhamento(item: Pick<ItemHistorico, 'consulta' | 'rota'>, origem: string): string {
  return item.rota ? `${origem}${item.rota}` : `${origem}/ia-chat?c=${codificarConsulta(item.consulta)}`;
}
