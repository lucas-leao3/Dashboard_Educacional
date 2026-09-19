/**
 * Tipos espelhando o contrato da API (backend/app/schemas/alunos.py, AlunoOut).
 * Um `Registro` é um snapshot (matricula, periodo); o mesmo aluno aparece
 * uma vez por período respondido.
 */
export interface Registro {
  id: number;
  ingestao_id: number;
  matricula: number;
  periodo: string;
  CRG: number | null;
  nome: string | null;
  data_de_nascimento: string | null;
  primeiro_ano_eletivo: string | null;
  genero: string | null;
  polo: string | null;
  cor_etnia: string | null;
  pcd: string | null;
  tipo_deficiencia: string | null;
  renda: string | null;
  deslocamento: string | null;
  trabalho: string | null;
  assistencia_estudantil: string | null;
  saude_mental: string | null;
  estresse: string | null;
  acompanhamento: string | null;
  escolaridade_pai: string | null;
  escolaridade_mae: string | null;
  qtd_computador: string | null;
  qtd_celular: string | null;
  computador_proprio: string | null;
  gasto_internet: string | null;
  acesso_internet: string | null;
  tipo_moradia: string | null;
  data_hora: string | null;
}

/** Espelha `IngestaoOut` (backend/app/schemas/lotes.py): um passo do lote. */
export interface Ingestao {
  id: number;
  passo: number;
  arquivo_sha256: string | null;
  executado_em: string;
  registros_lidos: number;
  registros_aceitos: number;
  registros_rejeitados: number;
}

/** Espelha `LoteOut` (backend/app/schemas/lotes.py). */
export interface Lote {
  id: string;
  executado_em: string;
  /** Preenchido por POST /lotes/{id}/fechar. Fechado não se reabre. */
  fechado_em: string | null;
  periodos_cobertos: string[];
  executado_por: string | null;
  observacao: string | null;
  ingestoes: Ingestao[];
  excecoes_por_motivo: Record<string, number>;
}

/** Sinalização de uma dimensão ou do aluno (doc de alinhamento, item 10). */
export type Sinalizacao = 'ok' | 'atencao' | 'critico' | 'sem_dado';

/** As quatro dimensões definidas na reunião (doc de alinhamento, item 2). */
export type DimensaoId = 'academica' | 'socioeconomica' | 'saude_mental' | 'infraestrutura';

export const SEM_TURMA = 'Sem turma informada';
export const SEM_POLO = 'Sem polo informado';

/** Espelha `HistoricosOut` (backend/app/schemas/lotes.py). */
export interface HistoricosOut {
  lote: string;
  gravados: string[];
  ja_existiam: string[];
  ignorados: string[];
  /** Contadores do passo, "ja_executado" se já tinha rodado, null se não se pediu ?executar. */
  sincronizar: Record<string, unknown> | 'ja_executado' | null;
  atualizar_crg: Record<string, unknown> | 'ja_executado' | null;
}

/** Espelha `CorrespondenciaOut`: uma linha por matrícula. */
export interface Correspondencia {
  matricula: number;
  nome: string | null;
  academico: boolean;
  socioeconomico: boolean;
  faltando: '' | 'Academico' | 'SocioEconomico' | 'Ambos';
}
