import type { ConsultaEstruturada, FormaResposta } from '../data/tipos';

/** Uma pergunta feita neste navegador. Não há login: o histórico é local. */
export interface ItemHistorico {
  id: string;
  pergunta: string;
  consulta: ConsultaEstruturada;
  forma: FormaResposta;
  quando: string;
  favorito: boolean;
  /** Rota do dashboard, quando a resposta foi abrir um. */
  rota: string | null;
}

export interface Armazenamento {
  getItem(chave: string): string | null;
  setItem(chave: string, valor: string): void;
}

export const CHAVE_HISTORICO = 'assistente.historico';
export const LIMITE_HISTORICO = 100;

/** localStorage, se o navegador deixar: em janela privada ou com dados de site bloqueados, até ler a propriedade lança. */
function armazenamentoPadrao(): Armazenamento | undefined {
  try {
    return globalThis.localStorage ?? undefined;
  } catch {
    return undefined;
  }
}

export function carregarHistorico(armazenamento: Armazenamento | undefined = armazenamentoPadrao()): ItemHistorico[] {
  try {
    const bruto = armazenamento?.getItem(CHAVE_HISTORICO);
    const lido: unknown = bruto ? JSON.parse(bruto) : [];
    return Array.isArray(lido) ? (lido as ItemHistorico[]) : [];
  } catch {
    return [];
  }
}

export function salvarHistorico(itens: ItemHistorico[], armazenamento: Armazenamento | undefined = armazenamentoPadrao()): void {
  try {
    armazenamento?.setItem(CHAVE_HISTORICO, JSON.stringify(itens));
  } catch {
    /* cota cheia ou armazenamento bloqueado: o histórico só não persiste */
  }
}

/** Novo no topo. Passando do limite, sai o não favorito mais antigo. */
export function adicionar(itens: ItemHistorico[], novo: ItemHistorico): ItemHistorico[] {
  const lista = [novo, ...itens];
  if (lista.length <= LIMITE_HISTORICO) return lista;
  const descartar = lista.map((i) => i.favorito).lastIndexOf(false);
  return descartar === -1 ? lista : lista.filter((_, i) => i !== descartar);
}

export function alternarFavorito(itens: ItemHistorico[], id: string): ItemHistorico[] {
  return itens.map((i) => (i.id === id ? { ...i, favorito: !i.favorito } : i));
}

export function ordenarParaExibir(itens: ItemHistorico[]): ItemHistorico[] {
  return [...itens.filter((i) => i.favorito), ...itens.filter((i) => !i.favorito)];
}
