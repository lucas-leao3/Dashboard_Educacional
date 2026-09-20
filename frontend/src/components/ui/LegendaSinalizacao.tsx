import { ROTULO_SINALIZACAO, SINALIZACOES } from '../../domain/classificacao';
import { COR_SINALIZACAO } from '../../theme/cores';

/** Legenda dos quatro estados (doc de alinhamento, item 10). */
export default function LegendaSinalizacao() {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500" aria-label="Legenda das sinalizações">
      {SINALIZACOES.map((s) => (
        <li key={s} className="inline-flex items-center gap-1.5">
          <span
            className={`w-2.5 h-2.5 rounded-full ${s === 'sem_dado' ? 'hachurado' : ''}`}
            style={{ background: s === 'sem_dado' ? undefined : COR_SINALIZACAO[s].hex }}
            aria-hidden="true"
          />
          {ROTULO_SINALIZACAO[s]}
        </li>
      ))}
    </ul>
  );
}
