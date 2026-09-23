/**
 * Agregações das telas de Análises (Bidimensional, Distribuição,
 * Longitudinal). Ficam aqui, fora dos componentes, por dois motivos: dá para
 * testar sem montar React, e as três telas param de carregar números fixos.
 *
 * Regras que atravessam as três, herdadas do resto do dashboard:
 * - o `n` de cada recorte é sempre visível, e abaixo de `N_MINIMO` sai o
 *   aviso de amostra pequena;
 * - quem não respondeu vira categoria própria em vez de sumir calado;
 * - ausência de nota é `null`, nunca `0` -- zero é uma nota, e desenhar zero
 *   onde não há apuração inventa uma queda (governança §4.6).
 */
import type { CrgSemestre, Registro } from '../data/tipos';
import { N_MINIMO } from './agregacao';
import type { Aluno } from './agregacao';
import { identificacao } from './aluno';

/** Rótulo de quem não respondeu o campo do eixo. */
export const NAO_INFORMADO = 'não informado';

/* ------------------------------------------------------------------ */
/* Eixo X do gráfico bidimensional                                      */
/* ------------------------------------------------------------------ */

export interface EixoCategoria {
  id: string;
  rotulo: string;
  /** Categoria do aluno neste eixo; null = não respondeu. */
  de: (aluno: Aluno) => string | null;
}

/** Campo do registro vigente, tratando string vazia como não respondido. */
function doVigente(campo: keyof Registro): (aluno: Aluno) => string | null {
  return (aluno) => {
    const v = aluno.vigente[campo];
    return v === null || v === undefined || v === '' ? null : String(v);
  };
}

/**
 * Só campos que a base realmente traz. Polo e turma entram porque agora são
 * derivados da matrícula (§4.8) e existem para 100% dos alunos.
 */
export const EIXOS_X: readonly EixoCategoria[] = [
  { id: 'cor_etnia', rotulo: 'Cor/Etnia', de: doVigente('cor_etnia') },
  { id: 'genero', rotulo: 'Gênero', de: doVigente('genero') },
  { id: 'renda', rotulo: 'Renda', de: doVigente('renda') },
  { id: 'trabalho', rotulo: 'Trabalho', de: doVigente('trabalho') },
  { id: 'polo', rotulo: 'Polo', de: (a) => a.polo },
  { id: 'turma', rotulo: 'Turma', de: (a) => a.turma },
];

export function eixo(id: string): EixoCategoria {
  return EIXOS_X.find((e) => e.id === id) ?? EIXOS_X[0];
}

export interface BarraCategoria {
  categoria: string;
  /** Média de CRG; null se ninguém da categoria tem nota. */
  valor: number | null;
  /** Alunos na categoria (respondendo ou não ao CRG). */
  n: number;
  /** Quantos deles têm nota -- é a base real da média. */
  nComNota: number;
  /**
   * Amostra pequena. Mede `nComNota`, não `n`: quem sustenta a média são os
   * alunos COM nota. Uma categoria com 22 alunos e 9 notas tem a média
   * apoiada em 9 -- avisar com base no 22 daria confiança que não existe.
   */
  nBaixo: boolean;
}

function media(valores: number[]): number | null {
  return valores.length ? valores.reduce((s, v) => s + v, 0) / valores.length : null;
}

/**
 * Média de CRG por categoria do eixo. Ordena da maior média para a menor,
 * com as categorias sem nota no fim -- elas não são "as piores", são as
 * desconhecidas, e misturá-las no meio do ranking sugeriria valor zero.
 */
export function mediaCrgPorCategoria(alunos: Aluno[], eixoX: EixoCategoria): BarraCategoria[] {
  const grupos = new Map<string, Aluno[]>();
  for (const aluno of alunos) {
    const chave = eixoX.de(aluno) ?? NAO_INFORMADO;
    grupos.set(chave, [...(grupos.get(chave) ?? []), aluno]);
  }
  return [...grupos]
    .map(([categoria, lista]) => {
      const notas = lista.map((a) => a.vigente.CRG).filter((v): v is number => v !== null);
      return {
        categoria,
        valor: media(notas),
        n: lista.length,
        nComNota: notas.length,
        nBaixo: notas.length < N_MINIMO,
      };
    })
    .sort((a, b) => {
      if (a.valor === null && b.valor === null) return a.categoria.localeCompare(b.categoria);
      if (a.valor === null) return 1;
      if (b.valor === null) return -1;
      return b.valor - a.valor;
    });
}

/* ------------------------------------------------------------------ */
/* Histograma de CRG                                                    */
/* ------------------------------------------------------------------ */

export interface FaixaHistograma {
  faixa: string;
  inicio: number;
  frequencia: number;
}

/**
 * Dez faixas inteiras de 0 a 10, todas sempre presentes (faixa vazia é
 * informação: mostra onde NÃO há ninguém). O limite inferior pertence à
 * faixa; o 10 entra na última, senão sumiria do gráfico.
 */
export function histogramaCrg(alunos: Aluno[]): FaixaHistograma[] {
  const faixas: FaixaHistograma[] = Array.from({ length: 10 }, (_, i) => ({
    faixa: `${i}–${i + 1}`,
    inicio: i,
    frequencia: 0,
  }));
  for (const aluno of alunos) {
    const crg = aluno.vigente.CRG;
    if (crg === null || crg < 0 || crg > 10) continue;
    faixas[Math.min(9, Math.floor(crg))].frequencia++;
  }
  return faixas;
}

/* ------------------------------------------------------------------ */
/* Série longitudinal por semestre letivo                               */
/* ------------------------------------------------------------------ */

/** '2024.1' -> 4048. Ordena cronologicamente, não alfabeticamente. */
function chaveSemestre(semestre: string): number {
  const m = semestre.match(/^(\d{4})\.(\d)/);
  return m ? Number(m[1]) * 2 + Number(m[2]) : Number.POSITIVE_INFINITY;
}

export function ordenarSemestres(semestres: Iterable<string>): string[] {
  return [...new Set(semestres)].sort((a, b) => chaveSemestre(a) - chaveSemestre(b));
}

export interface OpcoesSerie {
  polo?: string;
  turmas?: string[];
  /** Uma matrícula transforma o gráfico em trajetória individual. */
  matricula?: number;
}

/** Uma linha do gráfico: o semestre mais uma coluna por série. */
export type PontoLongitudinal = { semestre: string } & Record<string, number | null | string>;

export interface SerieLongitudinal {
  semestres: string[];
  series: string[];
  dados: PontoLongitudinal[];
}

/**
 * CRG médio por semestre letivo, uma série por turma (ou uma só, quando se
 * escolhe um aluno). O eixo sai dos semestres que os alunos selecionados
 * realmente têm.
 *
 * Semestre em que a série não tem NENHUMA nota apurada vale `null`, e o
 * gráfico desenha lacuna. É o caso real de 2025.2 e 2026.1, que têm 56 alunos
 * e zero notas: desenhar 0 ali faria toda linha despencar no fim.
 */
export function serieLongitudinal(
  alunos: Aluno[],
  crgSemestres: CrgSemestre[],
  opcoes: OpcoesSerie = {},
): SerieLongitudinal {
  let selecionados = alunos;
  if (opcoes.polo) selecionados = selecionados.filter((a) => a.polo === opcoes.polo);
  if (opcoes.turmas?.length) selecionados = selecionados.filter((a) => opcoes.turmas!.includes(a.turma));
  if (opcoes.matricula !== undefined) selecionados = selecionados.filter((a) => a.matricula === opcoes.matricula);

  const nomeDaSerie = (aluno: Aluno) =>
    opcoes.matricula !== undefined
      ? identificacao(aluno.vigente.nome, aluno.matricula)
      : `Turma ${aluno.turma}`;

  const porMatricula = new Map(selecionados.map((a) => [a.matricula, a]));
  const relevantes = crgSemestres.filter((c) => porMatricula.has(c.matricula));
  const semestres = ordenarSemestres(relevantes.map((c) => c.semestre));

  const notas = new Map<string, number[]>();
  const comAlgumaNota = new Set<string>();
  for (const ponto of relevantes) {
    if (ponto.crg === null) continue;
    const serie = nomeDaSerie(porMatricula.get(ponto.matricula)!);
    comAlgumaNota.add(serie);
    const chave = `${ponto.semestre}|${serie}`;
    notas.set(chave, [...(notas.get(chave) ?? []), ponto.crg]);
  }

  // Só entram séries com ao menos uma NOTA APURADA -- ter linha em
  // crg_semestre não basta. A turma 2025 tem 23 alunos com semestres
  // registrados e nenhuma nota ainda: incluí-la daria uma entrada de legenda
  // com a linha inteiramente vazia, que não informa nada e ainda gasta um
  // passo da rampa de cor.
  const series = [...comAlgumaNota].sort();

  const dados = semestres.map((semestre) => {
    const linha: PontoLongitudinal = { semestre };
    for (const serie of series) linha[serie] = media(notas.get(`${semestre}|${serie}`) ?? []);
    return linha;
  });

  return { semestres, series, dados };
}
