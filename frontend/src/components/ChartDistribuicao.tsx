import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useState } from 'react';
import SelectDropdown from './ui/SelectDropdown';
import BotaoIA from './ui/BotaoIA';
import { mockDataDistribuicao, yAxisOptions, poloOptions } from '../data/mockData';

// Custom bar shape com cantos superiores arredondados
function RoundedBar(props: any) {
  const { x, y, width, height, index } = props;
  const radius = 8;
  if (!height || height <= 0) return null;
  return (
    <path
      key={index}
      d={`M${x},${y + radius} Q${x},${y} ${x + radius},${y} L${x + width - radius},${y} Q${x + width},${y} ${x + width},${y + radius} L${x + width},${y + height} L${x},${y + height} Z`}
      fill="url(#barGradient)"
    />
  );
}

export default function ChartDistribuicao() {
  const [eixoY, setEixoY] = useState('CRG');
  const [polo, setPolo] = useState('Todos');
  return (
    <div className="relative bg-white rounded-[2rem] shadow-[0_12px_40px_rgba(0,0,0,0.03)] border border-slate-100 p-8 w-full">
      {/* Container de filtros / Dropdowns (Apenas dois na Distribuição) */}
      <div className="flex justify-end gap-3.5 mb-8 flex-wrap">
        <SelectDropdown label="Y" options={yAxisOptions} value={eixoY} onChange={setEixoY} />
        <SelectDropdown label="Polo" options={poloOptions} value={polo} onChange={setPolo} />
      </div>

      {/* Área do Gráfico Composto */}
      <div className="w-full pr-4">
        <ResponsiveContainer width="100%" height={380}>
          <ComposedChart
            data={mockDataDistribuicao}
            margin={{ top: 10, right: 10, left: -20, bottom: 5 }}
            barSize={40}
          >
            <defs>
              <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#489cf7" />
                <stop offset="100%" stopColor="#2563eb" />
              </linearGradient>
            </defs>

            <CartesianGrid vertical={false} stroke="#f1f5f9" strokeDasharray="0" />
            
            <XAxis
              dataKey="categoria"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#64748b', fontSize: 13, fontWeight: 500 }}
              dy={12}
            />
            
            {/* Eixo Y ocultado para focar no formato da distribuição conforme especificado */}
            <YAxis hide={true} domain={[0, 10]} />
            
            <Tooltip
              cursor={{ fill: 'rgba(37,99,235,0.04)', radius: 6 }}
              contentStyle={{
                background: '#0f172a',
                border: 'none',
                borderRadius: 12,
                color: '#f8fafc',
                fontSize: 13,
                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)',
                padding: '10px 16px',
              }}
              labelStyle={{ color: '#94a3b8', fontWeight: 600, marginBottom: 4 }}
              formatter={(value, name) => {
                const labelName = name === 'frequencia' ? 'Frequência' : 'Curva de Distribuição';
                return [typeof value === 'number' ? value.toFixed(2) : value, labelName];
              }}
            />
            
            {/* Barras Verticais */}
            <Bar
              dataKey="frequencia"
              fill="url(#barGradient)"
              shape={<RoundedBar />}
              isAnimationActive={true}
              animationDuration={800}
            />

            {/* Linha da Curva Normal Suave */}
            <Line
              type="monotone"
              dataKey="curva"
              stroke="#475569"
              strokeWidth={2.5}
              dot={false}
              activeDot={false}
              isAnimationActive={true}
              animationDuration={1000}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <BotaoIA />
    </div>
  );
}
