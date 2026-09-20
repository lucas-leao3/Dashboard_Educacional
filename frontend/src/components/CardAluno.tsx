import { Link } from 'react-router-dom';
import type { Aluno } from '../domain/agregacao';
import BarrasDimensao from './BarrasDimensao';
import SinalizacaoBadge from './ui/SinalizacaoBadge';

interface Props {
  aluno: Aluno;
  corPolo: string;
}

/**
 * Card do aluno na listagem da turma (consolidação das duas maquetes).
 * O perfil é resultado das 4 dimensões: mostramos a sinalização derivada e os
 * fatores que a puxaram, não um "arquétipo" como quinta dimensão.
 */
export default function CardAluno({ aluno, corPolo }: Props) {
  const { vigente } = aluno;
  const crg = vigente.CRG === null ? 'sem nota' : `CRG ${vigente.CRG.toFixed(2)}`;
  return (
    <Link
      to={`/aluno/${aluno.matricula}`}
      className="group block rounded-2xl bg-white border border-slate-200/80 p-5 shadow-[0_4px_20px_rgba(15,23,42,0.03)] hover:border-blue-300 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 transition-all"
      aria-label={`Abrir perfil da matrícula ${aluno.matricula}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-bold text-slate-900 truncate group-hover:text-blue-700">
            {vigente.nome ?? `Matrícula ${aluno.matricula}`}
          </p>
          <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1.5 flex-wrap">
            <span className="inline-flex items-center gap-1 rounded-full px-2 py-px font-semibold text-white" style={{ background: corPolo }}>
              {aluno.polo}
            </span>
            <span>{crg}</span>
            <span aria-hidden="true">·</span>
            <span>{aluno.registros.length} período(s)</span>
          </p>
        </div>
        <SinalizacaoBadge valor={aluno.sinalizacao} />
      </div>

      <div className="mt-4">
        <BarrasDimensao porDimensao={aluno.porDimensao} />
      </div>

      <p className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500 leading-relaxed">
        <span className="font-semibold text-slate-700">Fatores: </span>
        {aluno.fatores.length ? aluno.fatores.join(' · ') : 'nenhum fator de alerta identificado'}
      </p>
    </Link>
  );
}
