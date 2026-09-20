import type { DimensaoId, Sinalizacao } from '../data/tipos';
import { DIMENSOES } from '../domain/dimensoes';
import { ROTULO_SINALIZACAO } from '../domain/classificacao';
import { COR_SINALIZACAO } from '../theme/cores';

interface Props {
  porDimensao: Record<DimensaoId, Sinalizacao>;
  compacto?: boolean;
}

/** Preenchimento da barra por estado: crítico cheio, atenção 2/3, sem alerta 1/3. */
const LARGURA: Record<Sinalizacao, string> = { critico: '100%', atencao: '66%', ok: '34%', sem_dado: '100%' };

/**
 * As quatro barras do card de perfil. "Sem dado" é hachurado cinza: significa
 * que a informação não foi coletada, não que o valor é bom.
 */
export default function BarrasDimensao({ porDimensao, compacto = false }: Props) {
  return (
    <ul className={`space-y-${compacto ? '1.5' : '2.5'}`}>
      {DIMENSOES.map((d) => {
        const s = porDimensao[d.id];
        const cor = COR_SINALIZACAO[s];
        return (
          <li key={d.id} className="flex items-center gap-3 text-xs">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: cor.hex }} aria-hidden="true" />
            <span className="w-24 shrink-0 text-slate-600 truncate">{d.rotuloCurto}</span>
            <div
              className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden"
              role="img"
              aria-label={`${d.rotulo}: ${ROTULO_SINALIZACAO[s]}`}
            >
              <div
                className={`h-full rounded-full ${s === 'sem_dado' ? 'hachurado' : ''}`}
                style={{ width: LARGURA[s], background: s === 'sem_dado' ? undefined : cor.hex }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
