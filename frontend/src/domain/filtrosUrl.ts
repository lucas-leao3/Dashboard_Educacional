/**
 * Filtros das telas na query string: o assistente abre uma tela já filtrada
 * (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md) e o link
 * copiado da barra reproduz a mesma visão.
 */

export function lerFiltro(params: URLSearchParams, nome: string, padrao: string): string {
  return params.get(nome) ?? padrao;
}

/** Nova query string com o filtro. O valor padrão sai da URL, para o link ficar limpo. */
export function comFiltro(params: URLSearchParams, nome: string, valor: string, padrao: string): URLSearchParams {
  const nova = new URLSearchParams(params);
  if (valor === padrao) nova.delete(nome);
  else nova.set(nome, valor);
  return nova;
}

/** `?a=b&c=d` a partir de um objeto, sem os vazios; `''` se não sobrar nada. */
export function queryDe(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [nome, valor] of Object.entries(params)) if (valor) q.set(nome, valor);
  const texto = q.toString();
  return texto ? `?${texto}` : '';
}
