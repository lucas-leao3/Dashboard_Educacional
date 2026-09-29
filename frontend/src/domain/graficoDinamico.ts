import type { Celula } from '../data/tipos';
import { COR_SINALIZACAO, corDaEntidade, PALETA_CATEGORICA, RAMPA_TURMA } from '../theme/cores';

export interface Pivotado {
  linhas: Record<string, Celula>[];
  series: string[];
}

/**
 * Formato longo (uma linha por eixo × série, como vem da API) -> uma linha por
 * categoria do eixo, com uma chave por série, que é o que o Recharts desenha.
 * Sem série, a chave do valor é `valor`.
 */
export function pivotar(dados: Record<string, Celula>[], eixo: string, serie: string | null, campo: string, ordemSeries: string[]): Pivotado {
  if (!serie) return { linhas: dados.map((d) => ({ [eixo]: d[eixo], valor: d[campo] })), series: ['valor'] };
  const porEixo = new Map<string, Record<string, Celula>>();
  for (const d of dados) {
    const chave = String(d[eixo]);
    const linha = porEixo.get(chave) ?? { [eixo]: d[eixo] };
    linha[String(d[serie])] = d[campo];
    porEixo.set(chave, linha);
  }
  return { linhas: [...porEixo.values()], series: ordemSeries };
}

/** "Sem resposta", "Sem polo informado", "Sem turma informada": não coletado, nunca um valor. */
export function ehAusente(valor: string): boolean {
  return valor.startsWith('Sem ');
}

/** Cor de uma série: ausência em cinza; polo com a cor fixa dele; ordinal na rampa de um hue só; nominal na paleta categórica. */
export function corDaSerie(nome: string, series: string[], dimensao: string | null, ordinal: boolean): string {
  if (ehAusente(nome)) return COR_SINALIZACAO.sem_dado.hex;
  const presentes = series.filter((s) => !ehAusente(s));
  if (dimensao === 'polo') return corDaEntidade(nome, presentes);
  const i = presentes.indexOf(nome);
  if (ordinal) {
    const passo = presentes.length <= 1 ? RAMPA_TURMA.length - 1 : Math.round((i / (presentes.length - 1)) * (RAMPA_TURMA.length - 1));
    return RAMPA_TURMA[passo];
  }
  return PALETA_CATEGORICA[i] ?? '#64748b';
}
