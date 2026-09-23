import type { CrgSemestre, DimensaoId, Registro, Sinalizacao } from '../data/tipos';
import { classificarAluno, classificarDimensao, fatoresDoRegistro, pontuarDimensao } from './classificacao';
import { poloParaExibir, turmaParaExibir } from './matricula';

/** Abaixo disto o comparativo mostra o aviso "n baixo" (provisório). */
export const N_MINIMO = 15;

/**
 * Rótulo do FasiTech "2024.(3 e 4)" -> chave numérica 2024.3.
 * Tolera também "2024.1" e "2024" puros.
 */
function chaveDoPeriodo(periodo: string): number {
  const m = periodo.match(/^(\d{4})\D*(\d)?/);
  if (!m) return Number.POSITIVE_INFINITY;
  return Number(m[1]) + (m[2] ? Number(m[2]) / 10 : 0);
}

export function ordenarPeriodos(periodos: Iterable<string>): string[] {
  return [...new Set(periodos)].sort((a, b) => chaveDoPeriodo(a) - chaveDoPeriodo(b));
}

/** Um aluno consolidado: todos os seus snapshots + o vigente (mais recente). */
export interface Aluno {
  matricula: number;
  polo: string;
  turma: string;
  registros: Registro[];
  vigente: Registro;
  sinalizacao: Sinalizacao;
  porDimensao: Record<DimensaoId, Sinalizacao>;
  fatores: string[];
}

export const DIMENSAO_IDS: readonly DimensaoId[] = ['academica', 'socioeconomica', 'saude_mental', 'infraestrutura'];

function primeiroPreenchido<K extends keyof Registro>(registros: Registro[], campo: K): Registro[K] | null {
  for (let i = registros.length - 1; i >= 0; i--) {
    const v = registros[i][campo];
    if (v !== null && v !== '') return v;
  }
  return null;
}

/**
 * Agrupa os snapshots por matrícula. Com `periodo`, considera só quem
 * respondeu naquele período (e esse registro passa a ser o vigente).
 */
export function consolidarAlunos(registros: Registro[], periodo?: string): Aluno[] {
  const porMatricula = new Map<number, Registro[]>();
  for (const r of registros) {
    const lista = porMatricula.get(r.matricula) ?? [];
    lista.push(r);
    porMatricula.set(r.matricula, lista);
  }
  const alunos: Aluno[] = [];
  for (const [matricula, lista] of porMatricula) {
    const ordenados = [...lista].sort((a, b) => chaveDoPeriodo(a.periodo) - chaveDoPeriodo(b.periodo));
    const vigente = periodo ? ordenados.find((r) => r.periodo === periodo) : ordenados[ordenados.length - 1];
    if (!vigente) continue;
    const porDimensao = Object.fromEntries(DIMENSAO_IDS.map((d) => [d, classificarDimensao(d, vigente)])) as Record<DimensaoId, Sinalizacao>;
    alunos.push({
      matricula,
      // Turma e polo vêm DERIVADOS DO BANCO (view `aluno_vigente`, §4.8):
      // usar o que a API mandou mantém dashboard, vigente.csv e consulta SQL
      // dizendo a mesma coisa. A derivação local (./matricula.ts) só entra
      // quando não há API -- o dataset de demonstração -- ou quando o código
      // do polo ainda não está na tabela `polo` (aí polo_nome vem nulo e o
      // código cru aparece, em vez do polo sumir da tela).
      polo: primeiroPreenchido(ordenados, 'polo_nome')
        ?? poloParaExibir(matricula, primeiroPreenchido(ordenados, 'polo')),
      turma: primeiroPreenchido(ordenados, 'turma')
        ?? turmaParaExibir(matricula, primeiroPreenchido(ordenados, 'primeiro_ano_eletivo')),
      registros: ordenados,
      vigente,
      sinalizacao: classificarAluno(vigente),
      porDimensao,
      fatores: fatoresDoRegistro(vigente),
    });
  }
  return alunos.sort((a, b) => a.matricula - b.matricula);
}

/* ------------------------------------------------------------------ */
/* Indicadores comparáveis entre polos e turmas (doc, itens 4 e 8)     */
/* ------------------------------------------------------------------ */

export type IndicadorId =
  | 'crg_medio' | 'alunos' | 'registros'
  | 'pct_renda_ate_1sm' | 'pct_trabalho_informal'
  | 'pct_saude_mental_ruim' | 'pct_estresse_frequente'
  | 'pct_sem_computador' | 'pct_sem_internet';

export interface Indicador {
  id: IndicadorId;
  rotulo: string;
  dimensao: DimensaoId | 'amostra';
  formatar: (v: number) => string;
  /** Domínio do eixo para a barra comparativa. */
  max: number;
}

const pct = (v: number) => `${v.toFixed(v % 1 ? 1 : 0)}%`;
const inteiro = (v: number) => String(Math.round(v));

export const INDICADORES: readonly Indicador[] = [
  { id: 'crg_medio', rotulo: 'CRG médio', dimensao: 'academica', formatar: (v) => v.toFixed(2), max: 10 },
  { id: 'pct_renda_ate_1sm', rotulo: 'Renda até 1 SM', dimensao: 'socioeconomica', formatar: pct, max: 100 },
  { id: 'pct_trabalho_informal', rotulo: 'Trabalho informal', dimensao: 'socioeconomica', formatar: pct, max: 100 },
  { id: 'pct_saude_mental_ruim', rotulo: 'Saúde mental ruim/muito ruim', dimensao: 'saude_mental', formatar: pct, max: 100 },
  { id: 'pct_estresse_frequente', rotulo: 'Estresse frequente', dimensao: 'saude_mental', formatar: pct, max: 100 },
  { id: 'pct_sem_computador', rotulo: 'Sem computador próprio', dimensao: 'infraestrutura', formatar: pct, max: 100 },
  { id: 'pct_sem_internet', rotulo: 'Sem acesso à internet', dimensao: 'infraestrutura', formatar: pct, max: 100 },
  { id: 'alunos', rotulo: 'Alunos', dimensao: 'amostra', formatar: inteiro, max: 0 },
  { id: 'registros', rotulo: 'Registros', dimensao: 'amostra', formatar: inteiro, max: 0 },
];

export function indicador(id: IndicadorId): Indicador {
  return INDICADORES.find((i) => i.id === id)!;
}

export type Indicadores = Record<IndicadorId, number | null>;

export interface Agregado {
  alunos: number;
  registros: number;
  nBaixo: boolean;
  indicadores: Indicadores;
  porSinalizacao: Record<Sinalizacao, number>;
}

function media(valores: (number | null)[]): number | null {
  const validos = valores.filter((v): v is number => v !== null);
  if (!validos.length) return null;
  return validos.reduce((s, v) => s + v, 0) / validos.length;
}

/** % de alunos cujo vigente satisfaz o predicado, entre os que responderam. */
function percentual(alunos: Aluno[], campo: keyof Registro, predicado: (v: string) => boolean): number | null {
  const respondidos = alunos.filter((a) => a.vigente[campo] !== null && a.vigente[campo] !== '');
  if (!respondidos.length) return null;
  const sim = respondidos.filter((a) => predicado(String(a.vigente[campo]))).length;
  return (sim / respondidos.length) * 100;
}

export function agregar(alunos: Aluno[]): Agregado {
  const porSinalizacao: Record<Sinalizacao, number> = { ok: 0, atencao: 0, critico: 0, sem_dado: 0 };
  for (const a of alunos) porSinalizacao[a.sinalizacao]++;
  return {
    alunos: alunos.length,
    registros: alunos.reduce((s, a) => s + a.registros.length, 0),
    nBaixo: alunos.length < N_MINIMO,
    porSinalizacao,
    indicadores: {
      alunos: alunos.length,
      registros: alunos.reduce((s, a) => s + a.registros.length, 0),
      crg_medio: media(alunos.map((a) => a.vigente.CRG)),
      pct_renda_ate_1sm: percentual(alunos, 'renda', (v) => v === 'Até 1 salário mínimo'),
      pct_trabalho_informal: percentual(alunos, 'trabalho', (v) => /informal|autônomo|autonomo/i.test(v)),
      pct_saude_mental_ruim: percentual(alunos, 'saude_mental', (v) => v === 'Ruim' || v === 'Muito ruim'),
      pct_estresse_frequente: percentual(alunos, 'estresse', (v) => v === 'Sim, frequentemente' || v === 'Sim, a maior parte do tempo'),
      pct_sem_computador: percentual(alunos, 'computador_proprio', (v) => v === 'Não'),
      pct_sem_internet: percentual(alunos, 'acesso_internet', (v) => v === 'Não'),
    },
  };
}

export interface AgregadoPolo extends Agregado { polo: string }
export interface AgregadoTurma extends Agregado { turma: string; polo: string }

function agruparPor<K extends string>(alunos: Aluno[], chave: (a: Aluno) => K): Map<K, Aluno[]> {
  const grupos = new Map<K, Aluno[]>();
  for (const a of alunos) {
    const k = chave(a);
    grupos.set(k, [...(grupos.get(k) ?? []), a]);
  }
  return grupos;
}

export function agregarPorPolo(alunos: Aluno[]): AgregadoPolo[] {
  return [...agruparPor(alunos, (a) => a.polo)]
    .map(([polo, lista]) => ({ polo, ...agregar(lista) }))
    .sort((a, b) => b.alunos - a.alunos || a.polo.localeCompare(b.polo));
}

export function agregarPorTurma(alunos: Aluno[], polo: string): AgregadoTurma[] {
  const doPolo = alunos.filter((a) => a.polo === polo);
  return [...agruparPor(doPolo, (a) => a.turma)]
    .map(([turma, lista]) => ({ turma, polo, ...agregar(lista) }))
    .sort((a, b) => chaveDoPeriodo(a.turma) - chaveDoPeriodo(b.turma));
}

/* ------------------------------------------------------------------ */
/* Trajetória longitudinal por dimensão (doc, item 7)                   */
/* ------------------------------------------------------------------ */

/** `rotulo` é o período de coleta, ou o semestre letivo na dimensão acadêmica
 *  -- os dois eixos são diferentes e não se misturam na mesma série. */
export interface PontoTrajetoria { rotulo: string; valor: number | null }

/** '2024.1' -> 4049, para ordenar cronologicamente. */
function chaveSemestre(semestre: string): number {
  const m = semestre.match(/^(\d{4})\.(\d)/);
  return m ? Number(m[1]) * 2 + Number(m[2]) : Number.POSITIVE_INFINITY;
}

/**
 * Trajetória do aluno numa dimensão.
 *
 * A acadêmica sai de `crgSemestres` (GET /crg-semestres), e não do CRG dos
 * registros: o passo 2 do lote grava o CRG do último semestre apurado em
 * TODOS os períodos do aluno, então uma série sobre ele seria uma reta
 * horizontal por construção -- era o que este gráfico desenhava. Sem
 * histórico acadêmico a série vem vazia, e quem exibe avisa; inventar pontos
 * a partir do CRG repetido seria pior que não mostrar nada.
 *
 * As outras três dimensões continuam por período de coleta, que é o eixo
 * certo delas: são respostas de questionário.
 */
export function trajetoriaPorDimensao(
  aluno: Aluno,
  dimensao: DimensaoId,
  crgSemestres: CrgSemestre[] = [],
): PontoTrajetoria[] {
  if (dimensao === 'academica') {
    return crgSemestres
      .filter((c) => c.matricula === aluno.matricula)
      .sort((a, b) => chaveSemestre(a.semestre) - chaveSemestre(b.semestre))
      .map((c) => ({ rotulo: c.semestre, valor: c.crg }));
  }
  return aluno.registros.map((r) => ({ rotulo: r.periodo, valor: pontuarDimensao(dimensao, r) }));
}

/** Variação entre o primeiro e o último ponto com valor; null se < 2 pontos. */
export function variacao(pontos: PontoTrajetoria[]): number | null {
  const validos = pontos.filter((p) => p.valor !== null) as { valor: number }[];
  if (validos.length < 2) return null;
  return validos[validos.length - 1].valor - validos[0].valor;
}
