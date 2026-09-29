import type { ReactElement } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { GraficoDinamico as Grafico } from '../../data/tipos';
import { corDaSerie, pivotar } from '../../domain/graficoDinamico';
import { COR_PRIMARIA } from '../../theme/cores';

/** "Cametá n=2 · Oeiras n=1": o n fica sempre visível, somado por categoria do eixo. */
function legendaN(g: Grafico): string {
  const porEixo = new Map<string, number>();
  for (const d of g.dados) porEixo.set(String(d[g.eixo]), (porEixo.get(String(d[g.eixo])) ?? 0) + Number(d.n ?? 0));
  return [...porEixo].map(([k, n]) => `${k} n=${n}`).join(' · ');
}

export default function GraficoDinamico({ grafico: g }: { grafico: Grafico }) {
  const campo = g.tipo === 'barras_empilhadas' ? 'percentual' : 'valor';
  const { linhas, series } = pivotar(g.dados, g.eixo, g.serie, campo, g.series);
  const cor = (s: string) => (g.serie ? corDaSerie(s, series, g.serie, g.serie_ordinal) : COR_PRIMARIA);
  const nome = (s: string) => (g.serie ? s : g.rotulo_valor);

  let grafico: ReactElement;
  if (g.tipo === 'rosca') {
    const fatias = g.dados.map((d) => String(d[g.eixo]));
    grafico = (
      <PieChart>
        <Pie data={g.dados} dataKey="valor" nameKey={g.eixo} innerRadius="55%" outerRadius="80%">
          {fatias.map((f) => <Cell key={f} fill={corDaSerie(f, fatias, g.eixo, false)} />)}
        </Pie>
        <Tooltip /><Legend />
      </PieChart>
    );
  } else if (g.tipo === 'linha') {
    grafico = (
      <LineChart data={linhas}>
        <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey={g.eixo} /><YAxis /><Tooltip /><Legend />
        {/* Semestre sem nota é lacuna, nunca zero */}
        {series.map((s) => <Line key={s} dataKey={s} name={nome(s)} stroke={cor(s)} connectNulls={false} />)}
      </LineChart>
    );
  } else if (g.tipo === 'histograma') {
    grafico = (
      <BarChart data={linhas}>
        <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey={g.eixo} /><YAxis allowDecimals={false} /><Tooltip />
        <Bar dataKey="valor" name={g.rotulo_valor} fill={COR_PRIMARIA} />
      </BarChart>
    );
  } else {
    const empilhado = g.tipo === 'barras_empilhadas';
    grafico = (
      <BarChart data={linhas} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" domain={empilhado ? [0, 100] : undefined} unit={empilhado ? '%' : undefined} />
        <YAxis type="category" dataKey={g.eixo} width={160} /><Tooltip />{g.serie && <Legend />}
        {series.map((s) => <Bar key={s} dataKey={s} name={nome(s)} fill={cor(s)} stackId={empilhado ? 'total' : undefined} />)}
      </BarChart>
    );
  }

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-semibold text-slate-800">{g.titulo}</figcaption>
      <div className="h-72"><ResponsiveContainer width="100%" height="100%">{grafico}</ResponsiveContainer></div>
      <p className="text-[11px] text-slate-500">{legendaN(g)}</p>
    </figure>
  );
}
