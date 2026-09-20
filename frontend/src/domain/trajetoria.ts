import type { DimensaoId } from '../data/tipos';
import { trajetoriaPorDimensao, variacao } from './agregacao';
import type { Aluno } from './agregacao';
import { dimensao } from './dimensoes';

/** Frase curta de subtítulo: "variação +1.20 em CRG" ou aviso de dado insuficiente. */
export function textoVariacao(aluno: Aluno, dimensaoId: DimensaoId): string {
  const d = dimensao(dimensaoId);
  const delta = variacao(trajetoriaPorDimensao(aluno, dimensaoId));
  if (delta === null) return 'menos de 2 períodos com dado';
  const sinal = delta > 0 ? '+' : '';
  const valor = dimensaoId === 'academica' ? delta.toFixed(2) : delta.toFixed(0);
  return `variação ${sinal}${valor} em ${d.escala.rotulo}`;
}
