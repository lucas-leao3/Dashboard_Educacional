import type { DimensaoId, Registro } from '../data/tipos';

/**
 * As quatro dimensões da reunião de alinhamento (item 2 do documento).
 * "Trabalho & Renda" deixou de ser dimensão: trabalho, renda, moradia e
 * transporte ficam dentro de Dados Socioeconômicos.
 */
export interface Dimensao {
  id: DimensaoId;
  rotulo: string;
  rotuloCurto: string;
  descricao: string;
  /** O que o eixo Y da trajetória mostra para esta dimensão. */
  escala: { rotulo: string; min: number; max: number; maiorEhMelhor: boolean };
  /** Campos do registro exibidos no perfil individual, nesta ordem. */
  campos: { campo: keyof Registro; rotulo: string }[];
}

export const DIMENSOES: readonly Dimensao[] = [
  {
    id: 'academica',
    rotulo: 'Dados Acadêmicos',
    rotuloCurto: 'Acadêmica',
    descricao: 'CRG, situação acadêmica e evolução por período.',
    escala: { rotulo: 'CRG', min: 0, max: 10, maiorEhMelhor: true },
    // CRG não entra aqui: já é a linha de índice ("escala") do card.
    campos: [
      { campo: 'primeiro_ano_eletivo', rotulo: 'Ingresso (turma)' },
      { campo: 'periodo', rotulo: 'Período do registro' },
    ],
  },
  {
    id: 'socioeconomica',
    rotulo: 'Dados Socioeconômicos',
    rotuloCurto: 'Socioeconômica',
    descricao: 'Trabalho, renda, moradia, transporte e demais informações socioeconômicas.',
    escala: { rotulo: 'Índice de vulnerabilidade', min: 0, max: 4, maiorEhMelhor: false },
    campos: [
      { campo: 'renda', rotulo: 'Renda familiar' },
      { campo: 'trabalho', rotulo: 'Trabalho' },
      { campo: 'assistencia_estudantil', rotulo: 'Assistência estudantil' },
      { campo: 'tipo_moradia', rotulo: 'Moradia' },
      { campo: 'deslocamento', rotulo: 'Transporte' },
      { campo: 'escolaridade_mae', rotulo: 'Escolaridade da mãe' },
      { campo: 'escolaridade_pai', rotulo: 'Escolaridade do pai' },
    ],
  },
  {
    id: 'saude_mental',
    rotulo: 'Dados de Saúde Mental',
    rotuloCurto: 'Saúde Mental',
    descricao: 'Indicadores do formulário e sua evolução ao longo dos períodos.',
    escala: { rotulo: 'Índice de alerta', min: 0, max: 4, maiorEhMelhor: false },
    campos: [
      { campo: 'saude_mental', rotulo: 'Autoavaliação' },
      { campo: 'estresse', rotulo: 'Estresse' },
      { campo: 'acompanhamento', rotulo: 'Acompanhamento psicológico' },
    ],
  },
  {
    id: 'infraestrutura',
    rotulo: 'Dados de Infraestrutura',
    rotuloCurto: 'Infraestrutura',
    descricao: 'Computador, internet, recursos tecnológicos e demais indicadores disponíveis.',
    escala: { rotulo: 'Índice de carência', min: 0, max: 3, maiorEhMelhor: false },
    campos: [
      { campo: 'acesso_internet', rotulo: 'Acesso à internet' },
      { campo: 'computador_proprio', rotulo: 'Computador próprio' },
      { campo: 'qtd_computador', rotulo: 'Computadores em casa' },
      { campo: 'qtd_celular', rotulo: 'Celulares' },
      { campo: 'gasto_internet', rotulo: 'Gasto com internet' },
    ],
  },
];

export function dimensao(id: DimensaoId): Dimensao {
  return DIMENSOES.find((d) => d.id === id)!;
}
