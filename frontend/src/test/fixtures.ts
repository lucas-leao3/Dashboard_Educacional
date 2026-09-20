import type { Registro } from '../data/tipos';

/** Registro "em branco": tudo nulo, só o obrigatório preenchido. */
export function registro(parcial: Partial<Registro> = {}): Registro {
  return {
    id: 1, ingestao_id: 1, matricula: 1, periodo: '2024.(1 e 2)', CRG: null,
    nome: null, data_de_nascimento: null, primeiro_ano_eletivo: null, genero: null,
    polo: null, cor_etnia: null, pcd: null, tipo_deficiencia: null, renda: null,
    deslocamento: null, trabalho: null, assistencia_estudantil: null, saude_mental: null,
    estresse: null, acompanhamento: null, escolaridade_pai: null, escolaridade_mae: null,
    qtd_computador: null, qtd_celular: null, computador_proprio: null, gasto_internet: null,
    acesso_internet: null, tipo_moradia: null, data_hora: null,
    ...parcial,
  };
}
