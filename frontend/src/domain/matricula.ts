/**
 * Turma e polo saem da matrícula (docs/governanca_dados.md, §4.8).
 *
 * A matrícula da UFPA tem 12 dígitos com estrutura fixa:
 *
 *     2020 1604 0002
 *     │    │    └── sequencial do aluno
 *     │    └─────── polo
 *     └──────────── turma (ano de ingresso)
 *
 * Derivar daqui não é conveniência: a API do FasiTech devolve `polo` nulo em
 * 100% dos registros e não devolve `primeiro_ano_eletivo` campo algum, então
 * a matrícula é a ÚNICA fonte desses dois valores. Como a estrutura é uma
 * convenção institucional (não uma lei da natureza), a regra mora só aqui --
 * nenhum componente deve fatiar matrícula por conta própria.
 */
import { SEM_POLO, SEM_TURMA } from '../data/tipos';

/** Dígitos 5–8 → nome do polo. Validado em 120/120 linhas reais, sem exceção. */
export const POLOS_POR_CODIGO: Readonly<Record<string, string>> = {
  '1604': 'Cametá',
  '8564': 'Limoeiro',
  '8594': 'Oeiras',
};

/** O que a matrícula precisa ser para que a derivação valha: 12 dígitos. */
const PADRAO_MATRICULA = /^\d{12}$/;

/** Aceita o que o contrato da API entrega (number) e o que a rota entrega (string). */
export type Matricula = number | string | null | undefined;

/**
 * Normaliza a matrícula para os 12 dígitos, ou null se não estiver no padrão.
 * Nulo, vazio, com letras, curta ou longa demais: tudo cai em null -- nunca
 * numa turma/polo inventados.
 */
export function digitosDaMatricula(matricula: Matricula): string | null {
  if (matricula === null || matricula === undefined) return null;
  const texto = String(matricula).trim();
  return PADRAO_MATRICULA.test(texto) ? texto : null;
}

/** Turma = os 4 primeiros dígitos (ano de ingresso). Ex.: 202016040011 → "2020". */
export function turmaDaMatricula(matricula: Matricula): string | null {
  return digitosDaMatricula(matricula)?.slice(0, 4) ?? null;
}

/** Código do polo = dígitos 5–8. Ex.: 202016040011 → "1604". */
export function codigoDePolo(matricula: Matricula): string | null {
  return digitosDaMatricula(matricula)?.slice(4, 8) ?? null;
}

/**
 * Nome do polo a partir da matrícula. Código fora da tabela vira
 * `Polo <código>` em vez de null: um polo novo tem que APARECER na tela, não
 * sumir em "sem polo informado" (é exatamente o silêncio que a §4.8 critica).
 */
export function poloDaMatricula(matricula: Matricula): string | null {
  const codigo = codigoDePolo(matricula);
  if (codigo === null) return null;
  return POLOS_POR_CODIGO[codigo] ?? `Polo ${codigo}`;
}

/**
 * Turma a partir do rótulo legado `primeiro_ano_eletivo` ("2024.4" → "2024").
 * Só serve de reserva para matrícula fora do padrão; mantém o eixo de turma
 * homogêneo (sempre o ano), nunca misturando "2024" com "2024.4".
 */
export function turmaDoRotulo(rotulo: string | null | undefined): string | null {
  const ano = String(rotulo ?? '').trim().match(/^(\d{4})/);
  return ano ? ano[1] : null;
}

/** Turma para exibição: deriva, cai no rótulo legado, e só então desiste. */
export function turmaParaExibir(matricula: Matricula, primeiroAnoEletivo?: string | null): string {
  return turmaDaMatricula(matricula) ?? turmaDoRotulo(primeiroAnoEletivo) ?? SEM_TURMA;
}

/** Polo para exibição: deriva, cai no texto livre da fonte, e só então desiste. */
export function poloParaExibir(matricula: Matricula, poloInformado?: string | null): string {
  return poloDaMatricula(matricula) ?? (poloInformado?.trim() || null) ?? SEM_POLO;
}
