import { useMemo, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import SelectDropdown from './ui/SelectDropdown';
import BotaoIA from './ui/BotaoIA';
import { agregar, N_MINIMO } from '../domain/agregacao';
import { histogramaCrg } from '../domain/analises';
import { useDados } from '../hooks/useDados';
import { TODOS } from '../domain/filtros';

/**
 * Quantos alunos em cada faixa de CRG, com os dados do banco.
 *
 * Não há curva sobreposta. A anterior era uma gaussiana decorativa gerada por
 * fórmula, sem relação com os dados; e ajustar uma normal de verdade
 * afirmaria uma distribuição que ninguém testou. No lugar vai a média, que é
 * um fato verificável, marcada sobre o eixo.
 */
export default function ChartDistribuicao() {
  const { alunos } = useDados();
  const [polo, setPolo] = useState(TODOS);

  const polos = useMemo(() => [TODOS, ...new Set(alunos.map((a) => a.polo))].sort(), [alunos]);
  const filtrados = useMemo(
    () => (polo === TODOS ? alunos : alunos.filter((a) => a.polo === polo)),
    [alunos, polo],
  );
  const faixas = useMemo(() => histogramaCrg(filtrados), [filtrados]);
  const comNota = faixas.reduce((s, f) => s + f.frequencia, 0);
  const crgMedio = useMemo(() => agregar(filtrados).indicadores.crg_medio, [filtrados]);

  return (
    <div className="relative bg-white rounded-[2rem] shadow-[0_12px_40px_rgba(0,0,0,0.03)] border border-slate-100 p-8 w-full">
      <div className="flex justify-end gap-3.5 mb-8 flex-wrap">
        <SelectDropdown label="Y" options={[{ value: 'CRG', label: 'CRG' }]} value="CRG" onChange={() => {}} />
        <SelectDropdown label="Polo" options={polos} value={polo} onChange={setPolo} />
      </div>

      {comNota === 0 ? (
        <p className="py-24 text-center text-sm text-slate-500">
          Nenhum aluno do filtro tem CRG apurado — o histórico em PDF é que traz a nota.
        </p>
      ) : (
        <>
          <div className="w-full pr-4">
            <ResponsiveContainer width="100%" height={380}>
              <BarChart data={faixas} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                <defs>
                  <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#489cf7" />
                    <stop offset="100%" stopColor="#2563eb" />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="faixa" axisLine={false} tickLine={false} interval={0}
                  tick={{ fill: '#64748b', fontSize: 12, fontWeight: 500 }} dy={12}
                />
                <YAxis
                  allowDecimals={false} axisLine={false} tickLine={false}
                  tick={{ fill: '#64748b', fontSize: 13, fontWeight: 500 }} dx={-8}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(37,99,235,0.04)', radius: 6 }}
                  contentStyle={{ background: '#0f172a', border: 'none', borderRadius: 12, color: '#f8fafc', fontSize: 13, padding: '10px 16px' }}
                  labelStyle={{ color: '#94a3b8', fontWeight: 600, marginBottom: 4 }}
                  formatter={(v) => [`${v} aluno(s)`, 'Frequência']}
                  labelFormatter={(faixa) => `CRG ${faixa}`}
                />
                {crgMedio !== null && (
                  <ReferenceLine
                    x={faixas[Math.min(9, Math.floor(crgMedio))].faixa}
                    stroke="#0f172a" strokeDasharray="4 4"
                    label={{ value: `média ${crgMedio.toFixed(2)}`, position: 'top', fill: '#0f172a', fontSize: 11, fontWeight: 600 }}
                  />
                )}
                <Bar dataKey="frequencia" fill="url(#barGradient)" radius={[8, 8, 0, 0]} isAnimationActive animationDuration={800} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <p className="mt-6 pt-4 border-t border-slate-100 text-[11px] text-slate-500">
            <span className="font-semibold text-slate-600">n = {comNota}</span> aluno(s) com CRG apurado, de {filtrados.length} no filtro.
            {comNota < N_MINIMO && <span className="text-amber-700"> Amostra abaixo de {N_MINIMO} — leia com cautela.</span>}
            {' '}O limite inferior pertence à faixa; o CRG 10 entra em 9–10.
          </p>
        </>
      )}

      <BotaoIA />
    </div>
  );
}
