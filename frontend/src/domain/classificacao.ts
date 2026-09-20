import type { DimensaoId, Registro, Sinalizacao } from '../data/tipos';

/**
 * CRITÉRIO PROVISÓRIO. O documento de alinhamento (item 10 e nota final)
 * deixa a definição matemática das sinalizações como etapa metodológica
 * pendente. Toda regra fica neste módulo para que a troca seja cirúrgica:
 * cada dimensão expõe `pontuar` (índice numérico, usado também na trajetória
 * longitudinal) e `classificar` (índice -> sinalização).
 */

const SEM_RESPOSTA = new Set([null, undefined, '', 'Prefiro não responder']);
const respondeu = (v: string | null | undefined): v is string => !SEM_RESPOSTA.has(v as string);

/** Detalhe de uma regra que disparou: vai para o bloco "Fatores" do card. */
interface Regra {
  fator: string;
  pontos: number;
  dispara: (r: Registro) => boolean;
}

const eTrabalhoPrecario = (t: string) => /informal|autônomo|autonomo/i.test(t);

const REGRAS_SOCIOECONOMICAS: Regra[] = [
  { fator: 'Renda até 1 SM', pontos: 2, dispara: (r) => r.renda === 'Até 1 salário mínimo' },
  { fator: 'Trabalho informal', pontos: 1, dispara: (r) => respondeu(r.trabalho) && eTrabalhoPrecario(r.trabalho) },
  {
    fator: 'Sem assistência estudantil',
    pontos: 1,
    dispara: (r) => r.renda === 'Até 1 salário mínimo' && r.assistencia_estudantil === 'Não',
  },
];

const REGRAS_SAUDE_MENTAL: Regra[] = [
  { fator: 'Saúde mental: muito ruim', pontos: 4, dispara: (r) => r.saude_mental === 'Muito ruim' },
  { fator: 'Saúde mental: ruim', pontos: 2, dispara: (r) => r.saude_mental === 'Ruim' },
  { fator: 'Saúde mental: regular', pontos: 1, dispara: (r) => r.saude_mental === 'Regular' },
  {
    fator: 'Estresse frequente',
    pontos: 2,
    dispara: (r) => r.estresse === 'Sim, frequentemente' || r.estresse === 'Sim, a maior parte do tempo',
  },
];

const REGRAS_INFRAESTRUTURA: Regra[] = [
  { fator: 'Sem acesso à internet', pontos: 3, dispara: (r) => r.acesso_internet === 'Não' },
  { fator: 'Internet intermitente', pontos: 1, dispara: (r) => r.acesso_internet === 'Às vezes' },
  { fator: 'Sem computador próprio', pontos: 1, dispara: (r) => r.computador_proprio === 'Não' },
  { fator: 'Nenhum computador em casa', pontos: 1, dispara: (r) => r.qtd_computador === '0' },
];

const CAMPOS_POR_DIMENSAO: Record<Exclude<DimensaoId, 'academica'>, (keyof Registro)[]> = {
  socioeconomica: ['renda', 'trabalho', 'assistencia_estudantil', 'tipo_moradia', 'deslocamento'],
  saude_mental: ['saude_mental', 'estresse', 'acompanhamento'],
  infraestrutura: ['acesso_internet', 'computador_proprio', 'qtd_computador', 'gasto_internet'],
};

const REGRAS: Record<Exclude<DimensaoId, 'academica'>, Regra[]> = {
  socioeconomica: REGRAS_SOCIOECONOMICAS,
  saude_mental: REGRAS_SAUDE_MENTAL,
  infraestrutura: REGRAS_INFRAESTRUTURA,
};

/** Limiares (índice -> sinalização) de cada dimensão baseada em regras. */
const LIMIARES: Record<Exclude<DimensaoId, 'academica'>, { atencao: number; critico: number }> = {
  // Renda até 1 SM sem assistência (3) é a situação majoritária da base:
  // vira atenção; crítico exige também trabalho precário (4).
  socioeconomica: { atencao: 1, critico: 4 },
  saude_mental: { atencao: 1, critico: 4 },
  infraestrutura: { atencao: 1, critico: 3 },
};

function temAlgumaResposta(r: Registro, campos: (keyof Registro)[]): boolean {
  return campos.some((c) => respondeu(r[c] as string | null));
}

/**
 * Índice numérico da dimensão para um registro; `null` = sem dado.
 * Acadêmica devolve o CRG (maior é melhor); as demais devolvem a soma dos
 * pontos das regras disparadas (maior é pior).
 */
export function pontuarDimensao(id: DimensaoId, r: Registro): number | null {
  if (id === 'academica') return r.CRG;
  if (!temAlgumaResposta(r, CAMPOS_POR_DIMENSAO[id])) return null;
  return REGRAS[id].filter((regra) => regra.dispara(r)).reduce((soma, regra) => soma + regra.pontos, 0);
}

export function classificarDimensao(id: DimensaoId, r: Registro): Sinalizacao {
  const indice = pontuarDimensao(id, r);
  if (indice === null) return 'sem_dado';
  if (id === 'academica') {
    if (indice < 5) return 'critico';
    if (indice < 7) return 'atencao';
    return 'ok';
  }
  const { atencao, critico } = LIMIARES[id];
  if (indice >= critico) return 'critico';
  if (indice >= atencao) return 'atencao';
  return 'ok';
}

const ORDEM: Sinalizacao[] = ['critico', 'atencao', 'ok', 'sem_dado'];

/** O perfil do aluno é o resultado das quatro dimensões, não uma quinta. */
export function classificarAluno(r: Registro): Sinalizacao {
  const sinais = (['academica', 'socioeconomica', 'saude_mental', 'infraestrutura'] as DimensaoId[]).map((d) =>
    classificarDimensao(d, r),
  );
  return ORDEM.find((s) => sinais.includes(s)) ?? 'sem_dado';
}

/** Fatores que puxaram a sinalização, na ordem das dimensões. */
export function fatoresDoRegistro(r: Registro): string[] {
  const fatores: string[] = [];
  if (r.CRG !== null && r.CRG < 5) fatores.push('CRG abaixo de 5');
  for (const id of ['socioeconomica', 'saude_mental', 'infraestrutura'] as const) {
    for (const regra of REGRAS[id]) if (regra.dispara(r)) fatores.push(regra.fator);
  }
  return fatores;
}

export const ROTULO_SINALIZACAO: Record<Sinalizacao, string> = {
  ok: 'Sem alerta',
  atencao: 'Atenção',
  critico: 'Crítico',
  sem_dado: 'Sem dado',
};

export const SINALIZACOES: readonly Sinalizacao[] = ['ok', 'atencao', 'critico', 'sem_dado'];
