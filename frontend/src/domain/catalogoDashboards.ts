import { queryDe } from './filtrosUrl';

type Params = Record<string, string>;

/**
 * id de dashboard (backend: catalogo.DASHBOARDS) -> rota com os filtros.
 * As rotas moram aqui, junto de main.tsx, e não no backend.
 */
const ROTAS: Record<string, (p: Params) => string> = {
  polos: (p) => `/${queryDe({ periodo: p.periodo })}`,
  turmas: (p) => `/polo/${encodeURIComponent(p.polo)}${queryDe({ periodo: p.periodo })}`,
  alunos_turma: (p) => `/polo/${encodeURIComponent(p.polo)}/turma/${encodeURIComponent(p.turma)}${queryDe({ periodo: p.periodo })}`,
  perfil: (p) => `/aluno/${encodeURIComponent(p.matricula)}`,
  bidimensional: (p) => `/analises/bidimensional${queryDe({ dimensao: p.dimensao, polo: p.polo, periodo: p.periodo })}`,
  distribuicao: (p) => `/analises/distribuicao${queryDe({ polo: p.polo, periodo: p.periodo })}`,
  longitudinal: (p) => `/analises/longitudinal${queryDe({ polo: p.polo, turma: p.turma })}`,
};

export function rotaDoDashboard(id: string, params: Params): string | null {
  const rota = ROTAS[id];
  return rota ? rota(params) : null;
}
