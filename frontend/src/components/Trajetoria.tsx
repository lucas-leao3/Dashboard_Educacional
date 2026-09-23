import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { DimensaoId } from '../data/tipos';
import { trajetoriaPorDimensao } from '../domain/agregacao';
import type { Aluno } from '../domain/agregacao';
import { dimensao } from '../domain/dimensoes';
import { useDados } from '../hooks/useDados';
import { COR_PRIMARIA } from '../theme/cores';

interface Props {
  aluno: Aluno;
  dimensaoId: DimensaoId;
  /** Versão reduzida para grades de vários alunos. */
  compacto?: boolean;
}

/** Abrevia "2024.(3 e 4)" para "2024 3-4" nos ticks. Semestre ("2024.1") passa direto. */
const abreviar = (p: string) => p.replace(/\.\((\d) e (\d)\)/, ' $1-$2');

/**
 * Trajetória longitudinal de um aluno. A dimensão é selecionável (doc, item
 * 7): acadêmica mostra o CRG por SEMESTRE LETIVO (vindo de /crg-semestres);
 * as demais, o índice da dimensão por período de coleta. Uma série só, logo
 * sem legenda; pontos sem dado quebram a linha.
 */
export default function Trajetoria({ aluno, dimensaoId, compacto = false }: Props) {
  const { crgSemestres } = useDados();
  const d = dimensao(dimensaoId);
  const pontos = trajetoriaPorDimensao(aluno, dimensaoId, crgSemestres);
  const altura = compacto ? 110 : 280;

  if (!pontos.length) {
    return (
      <p className={`text-slate-500 ${compacto ? 'text-[11px] py-6' : 'text-sm py-10'} text-center`}>
        {dimensaoId === 'academica'
          ? 'Sem histórico acadêmico para esta matrícula.'
          : 'Sem períodos registrados para esta dimensão.'}
      </p>
    );
  }

  return (
    <div className="w-full" role="img" aria-label={`Trajetória de ${d.rotulo}: ${pontos.map((p) => `${p.rotulo} ${p.valor ?? 'sem dado'}`).join(', ')}`}>
      <ResponsiveContainer width="100%" height={altura}>
        <LineChart data={pontos} margin={{ top: 12, right: 8, left: compacto ? 8 : -8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#f1f5f9" />
          {/* interval=0: mostra todos os períodos mesmo no sparklines; padding evita cortar os pontos das pontas. */}
          <XAxis
            dataKey="rotulo" tickFormatter={abreviar} interval={0} padding={{ left: 12, right: 12 }}
            axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: compacto ? 10 : 12 }} dy={6}
          />
          <YAxis
            domain={[d.escala.min, d.escala.max]}
            axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }}
            width={compacto ? 28 : 36}
            hide={compacto}
            allowDecimals={false}
          />
          <Tooltip
            cursor={{ stroke: '#cbd5e1', strokeWidth: 1 }}
            contentStyle={{ background: '#0f172a', border: 'none', borderRadius: 10, color: '#f8fafc', fontSize: 12, padding: '8px 12px' }}
            labelStyle={{ color: '#94a3b8', fontWeight: 600, marginBottom: 2 }}
            formatter={(v) => [v === null || v === undefined ? 'sem dado' : v, d.escala.rotulo]}
          />
          <Line
            type="monotone" dataKey="valor" stroke={COR_PRIMARIA} strokeWidth={2}
            dot={{ r: 4, fill: '#fff', stroke: COR_PRIMARIA, strokeWidth: 2 }}
            activeDot={{ r: 5 }}
            connectNulls={false}
            isAnimationActive={!compacto}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
