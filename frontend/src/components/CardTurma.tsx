import { Link } from 'react-router-dom';
import type { AgregadoTurma } from '../domain/agregacao';
import { COR_SINALIZACAO } from '../theme/cores';
import { ROTULO_SINALIZACAO, SINALIZACOES } from '../domain/classificacao';

interface Props {
  turma: AgregadoTurma;
}

/** Card de turma dentro de um polo (doc de alinhamento, item 5). */
export default function CardTurma({ turma }: Props) {
  const crg = turma.indicadores.crg_medio;
  const total = Math.max(turma.alunos, 1);
  return (
    <Link
      to={`/polo/${encodeURIComponent(turma.polo)}/turma/${encodeURIComponent(turma.turma)}`}
      className="group block rounded-2xl bg-white border border-slate-200/80 p-5 shadow-[0_4px_20px_rgba(15,23,42,0.03)] hover:border-blue-300 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 transition-all"
      aria-label={`Abrir alunos da turma ${turma.turma}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Turma</p>
          <p className="text-xl font-extrabold text-slate-900 group-hover:text-blue-700">{turma.turma}</p>
        </div>
        {turma.nBaixo && (
          <span className="text-[10px] font-bold text-amber-700 bg-amber-50 rounded-full px-2 py-0.5">n baixo</span>
        )}
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3">
        <div>
          <dt className="text-[11px] text-slate-500">Alunos</dt>
          <dd className="text-2xl font-bold text-slate-900 leading-tight">{turma.alunos}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-slate-500">CRG médio</dt>
          <dd className="text-2xl font-bold text-slate-900 leading-tight">{crg === null ? '—' : crg.toFixed(2)}</dd>
        </div>
      </dl>

      {/* Barra empilhada de sinalizações, com gap de 2px entre segmentos. */}
      <div className="mt-4 flex h-2 gap-0.5 rounded-full overflow-hidden" role="img" aria-label={SINALIZACOES.map((s) => `${ROTULO_SINALIZACAO[s]}: ${turma.porSinalizacao[s]}`).join(', ')}>
        {SINALIZACOES.map((s) =>
          turma.porSinalizacao[s] > 0 ? (
            <div
              key={s}
              className={`h-full ${s === 'sem_dado' ? 'hachurado' : ''}`}
              style={{ width: `${(turma.porSinalizacao[s] / total) * 100}%`, background: s === 'sem_dado' ? undefined : COR_SINALIZACAO[s].hex }}
            />
          ) : null,
        )}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">
        {SINALIZACOES.filter((s) => turma.porSinalizacao[s] > 0)
          .map((s) => `${turma.porSinalizacao[s]} ${ROTULO_SINALIZACAO[s].toLowerCase()}`)
          .join(' · ')}
      </p>
    </Link>
  );
}
