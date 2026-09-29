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
  /* Derivados da matrícula pela view `aluno_vigente` (governança §4.8). O
     banco é quem calcula; vêm null quando a origem é a demonstração. */
  turma: string | null;
  polo_cod: string | null;
  polo_nome: string | null;
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
  /** Carimbado no fim da importação. Lote fechado é imutável. */
  fechado_em: string | null;
  /** Extraídos dos históricos (semestre letivo da data de emissão), nunca digitados. */
  periodos_cobertos: string[];
  /** O responsável pela importação. */
  executado_por: string | null;
  observacao: string | null;
  ingestoes: Ingestao[];
  excecoes_por_motivo: Record<string, number>;
}

/**
 * Espelha `CrgSemestreOut` (backend/app/schemas/crg.py): um ponto da
 * trajetória acadêmica. `crg` null = semestre não apurado (governança §4.6);
 * quem desenha faz lacuna ali, nunca zero.
 */
export interface CrgSemestre {
  matricula: number;
  semestre: string;
  crg: number | null;
}

/** Sinalização de uma dimensão ou do aluno (doc de alinhamento, item 10). */
export type Sinalizacao = 'ok' | 'atencao' | 'critico' | 'sem_dado';

/** As quatro dimensões definidas na reunião (doc de alinhamento, item 2). */
export type DimensaoId = 'academica' | 'socioeconomica' | 'saude_mental' | 'infraestrutura';

export const SEM_TURMA = 'Sem turma informada';
export const SEM_POLO = 'Sem polo informado';

/** Espelha `ResumoRelatorio` (backend/app/schemas/lotes.py). */
export interface ResumoRelatorio {
  total: number;
  integrados: number;
  nao_integrados: number;
  /** Não integrados por código de motivo. */
  por_motivo: Record<string, number>;
  preenchimento_medio_integrados: number | null;
}

/** Espelha `ImportacaoOut`: o lote já fechado e o que a importação fez. */
export interface ImportacaoOut extends Lote {
  arquivos: { gravados: string[]; ja_existiam: string[]; ignorados: string[] };
  sincronizar: Record<string, unknown>;
  atualizar_crg: Record<string, unknown>;
  arquivos_gerados: string[];
  resumo: ResumoRelatorio;
}

/** Espelha `LinhaRelatorio`: identificação, fontes e completude do registro. */
export interface LinhaRelatorio {
  /** null = registro sem matrícula utilizável (falha de identificação). */
  matricula: number | null;
  nome: string | null;
  academico: boolean;
  socioeconomico: boolean;
  campos_avaliados: number;
  qtd_campos_sem_resposta: number;
  campos_sem_resposta: string[];
  /** 0-100; null quando não há campo a avaliar. */
  percentual_preenchimento: number | null;
}

export interface LinhaIntegrada extends LinhaRelatorio {
  status: string;
}

export type MotivoNaoIntegrado = 'sem_academico' | 'sem_socioeconomico' | 'falha_identificacao' | 'matricula_nao_encontrada';

export interface LinhaNaoIntegrada extends LinhaRelatorio {
  motivo: MotivoNaoIntegrado;
  motivo_descricao: string;
  detalhe: string | null;
}

/** Espelha `RelatorioOut` (GET /lotes/{id}/relatorio). */
export interface Relatorio {
  lote: string;
  resumo: ResumoRelatorio;
  integrados: LinhaIntegrada[];
  nao_integrados: LinhaNaoIntegrada[];
}

/* Assistente de consultas: espelho de backend/app/schemas/assistente.py */

export type FormaResposta = 'dashboard' | 'dinamico' | 'tabela' | 'texto' | 'nao_entendi';

export interface FiltroConsulta {
  campo: string;
  op: '=' | 'in' | 'entre';
  valor: string | string[];
}

export interface ConsultaEstruturada {
  tipo: 'agregado' | 'lista' | 'operacional' | 'fora_do_catalogo';
  metrica: string | null;
  dimensoes: string[];
  filtros: FiltroConsulta[];
  ordem: { campo: string; direcao: 'asc' | 'desc' } | null;
  limite: number | null;
  interpretacao: string;
}

export interface ExplicacaoAssistente {
  consulta_interpretada: string;
  filtros_aplicados: { rotulo: string; valor: string }[];
  fontes: string[];
  forma: FormaResposta;
}

export type Celula = string | number | null;

export interface GraficoDinamico {
  tipo: 'barras' | 'barras_empilhadas' | 'barras_agrupadas' | 'linha' | 'rosca' | 'histograma';
  titulo: string;
  eixo: string;
  serie: string | null;
  series: string[];
  serie_ordinal: boolean;
  rotulo_valor: string;
  dados: Record<string, Celula>[];
}

export interface BlocoDinamico {
  kpis: { rotulo: string; valor: number | null; n: number }[];
  graficos: GraficoDinamico[];
}

export interface BlocoTabela {
  colunas: { id: string; rotulo: string }[];
  linhas: Record<string, Celula>[];
  total: number;
}

export interface RespostaAssistente {
  id: string;
  pergunta: string | null;
  consulta: ConsultaEstruturada | null;
  forma: FormaResposta;
  explicacao: ExplicacaoAssistente;
  dashboard: { id: string; params: Record<string, string> } | null;
  dinamico: BlocoDinamico | null;
  tabela: BlocoTabela | null;
  texto: { mensagem: string; valor: number | null; n: number | null } | null;
  nao_entendi: { motivo: string; sugestoes: string[] } | null;
}
