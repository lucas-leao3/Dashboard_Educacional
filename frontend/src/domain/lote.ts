/** Regras puras da tela Dados (importação e relatórios). */

/** O mesmo teto do backend (app.services.importacao.TAMANHO_MAXIMO_RESPONSAVEL). */
export const TAMANHO_MAXIMO_RESPONSAVEL = 100;

export function ehZip(nome: string): boolean {
  return nome.toLowerCase().endsWith('.zip');
}

/**
 * O que falta para poder importar, ou null se está pronto. A importação só
 * pede o responsável e o .zip; o resto (id, período) o backend infere.
 */
export function pendenciaDaImportacao(responsavel: string, arquivo: { name: string } | null): string | null {
  const nome = responsavel.trim();
  if (!nome) return 'Informe o nome do responsável.';
  if (nome.length > TAMANHO_MAXIMO_RESPONSAVEL) return `O nome passa de ${TAMANHO_MAXIMO_RESPONSAVEL} caracteres.`;
  if (!arquivo) return 'Escolha o arquivo .zip com os históricos.';
  if (!ehZip(arquivo.name)) return 'O arquivo precisa ser um .zip com os históricos em PDF.';
  return null;
}

/** "renda, trabalho" ou "nenhum" -- como o relatório mostra a lista. */
export function textoCamposSemResposta(campos: string[]): string {
  return campos.length ? campos.join(', ') : 'nenhum';
}

export function textoPercentual(valor: number | null): string {
  return valor === null ? '—' : `${valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`;
}
