import type { CrgSemestre, DimensaoId } from '../data/tipos';
import { trajetoriaPorDimensao, variacao } from './agregacao';
import type { Aluno } from './agregacao';
import { dimensao } from './dimensoes';

/** Frase curta de subtítulo: "variação +1.20 em CRG" ou aviso de dado insuficiente. */
export function textoVariacao(aluno: Aluno, dimensaoId: DimensaoId, crgSemestres: CrgSemestre[] = []): string {
  const d = dimensao(dimensaoId);
  const pontos = trajetoriaPorDimensao(aluno, dimensaoId, crgSemestres);
  const delta = variacao(pontos);
  // A acadêmica anda por semestre letivo; as outras, por período de coleta.
  const unidade = dimensaoId === 'academica' ? 'semestres' : 'períodos';
  if (delta === null) return `menos de 2 ${unidade} com dado`;
  const sinal = delta > 0 ? '+' : '';
  const valor = dimensaoId === 'academica' ? delta.toFixed(2) : delta.toFixed(0);
  return `variação ${sinal}${valor} em ${d.escala.rotulo}`;
}
