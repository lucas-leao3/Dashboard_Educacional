import { useMemo } from 'react';
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import SelectDropdown from './ui/SelectDropdown';
import BotaoIA from './ui/BotaoIA';
import AvisoAmostra from './ui/AvisoAmostra';
import { EIXOS_X, eixo, mediaCrgPorCategoria } from '../domain/analises';
import type { BarraCategoria } from '../domain/analises';
import { useDados } from '../hooks/useDados';
import { useFiltroUrl } from '../hooks/useFiltroUrl';
import { TODOS } from '../domain/filtros';

interface PropsTick {
  x?: number;
  y?: number;
  payload?: { value?: string; index?: number };
  barras?: BarraCategoria[];
}

/** Duas linhas no tick: a categoria e o n que sustenta a média. */
function TickCategoria({ x = 0, y = 0, payload, barras = [] }: PropsTick) {
  const barra = barras[payload?.index ?? -1];
  return (
    <g transform={`translate(${x},${y})`}>
      <text textAnchor="middle" dy={16} fill="#64748b" fontSize={13} fontWeight={500}>{payload?.value}</text>
      <text textAnchor="middle" dy={32} fill={barra?.nBaixo ? '#b45309' : '#94a3b8'} fontSize={11} fontWeight={600}>
        n={barra?.nComNota ?? 0}
      </text>
    </g>
  );
}

/**
 * CRG médio por categoria, com os dados do banco. O eixo X sai de `EIXOS_X`
 * (campos que a base realmente tem) e as categorias saem dos próprios dados --
 * nada de lista fixa, que mostrava categorias inexistentes e escondia as reais.
 */
export default function ChartBidimensional() {
  const { alunos } = useDados();
  const [eixoX, setEixoX] = useFiltroUrl('dimensao', 'cor_etnia');
  const [polo, setPolo] = useFiltroUrl('polo', TODOS);

  const polos = useMemo(() => [TODOS, ...new Set(alunos.map((a) => a.polo))].sort(), [alunos]);
  const filtrados = useMemo(
    () => (polo === TODOS ? alunos : alunos.filter((a) => a.polo === polo)),
    [alunos, polo],
  );
  const barras = useMemo(() => mediaCrgPorCategoria(filtrados, eixo(eixoX)), [filtrados, eixoX]);
  const semNota = barras.every((b) => b.valor === null);

  return (
    <div className="relative bg-white rounded-[2rem] shadow-[0_12px_40px_rgba(0,0,0,0.03)] border border-slate-100 p-8 w-full">
      <div className="flex justify-end gap-3.5 mb-8 flex-wrap">
        <SelectDropdown label="X" options={EIXOS_X.map((e) => ({ value: e.id, label: e.rotulo }))} value={eixoX} onChange={setEixoX} />
        <SelectDropdown label="Y" options={[{ value: 'CRG', label: 'CRG' }]} value="CRG" onChange={() => {}} />
        <SelectDropdown label="Polo" options={polos} value={polo} onChange={setPolo} />
      </div>

      {!barras.length || semNota ? (
        <p className="py-24 text-center text-sm text-slate-500">
          {!barras.length ? 'Nenhum aluno no filtro atual.' : 'Nenhum aluno do filtro tem CRG apurado.'}
        </p>
      ) : (
        <>
          <div className="w-full pr-4">
            <ResponsiveContainer width="100%" height={380}>
              <BarChart data={barras} margin={{ top: 10, right: 10, left: -20, bottom: 5 }} barSize={40}>
                <defs>
                  <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#489cf7" />
                    <stop offset="100%" stopColor="#2563eb" />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#f1f5f9" strokeDasharray="0" />
                {/* O n vai DEBAIXO da categoria, não só no rodapé: a barra mais
                    alta desta base é uma categoria de um aluno só, e quem varre o
                    gráfico precisa ver isso sem procurar. */}
                <XAxis
                  dataKey="categoria" axisLine={false} tickLine={false}
                  tick={<TickCategoria barras={barras} />} dy={12} interval={0} height={48}
                />
                <YAxis
                  domain={[0, 10]} axisLine={false} tickLine={false}
                  tick={{ fill: '#64748b', fontSize: 13, fontWeight: 500 }} ticks={[0, 2, 4, 6, 8, 10]} dx={-8}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(37,99,235,0.04)', radius: 6 }}
                  contentStyle={{ background: '#0f172a', border: 'none', borderRadius: 12, color: '#f8fafc', fontSize: 13, boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)', padding: '10px 16px' }}
                  labelStyle={{ color: '#94a3b8', fontWeight: 600, marginBottom: 4 }}
                  /* O n vai no tooltip junto da média: média sem n esconde que
                     uma barra pode valer por um aluno só. */
                  formatter={(valor, _nome, item) => {
                    const b = item?.payload as { n: number; nComNota: number } | undefined;
                    return [
                      `${typeof valor === 'number' ? valor.toFixed(2) : '—'}  (n=${b?.nComNota ?? 0} com nota, de ${b?.n ?? 0})`,
                      'CRG médio',
                    ];
                  }}
                />
                <Bar dataKey="valor" fill="url(#barGradient)" radius={[8, 8, 0, 0]} isAnimationActive animationDuration={800} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <AvisoAmostra barras={barras} />
        </>
      )}

      <BotaoIA />
    </div>
  );
}
