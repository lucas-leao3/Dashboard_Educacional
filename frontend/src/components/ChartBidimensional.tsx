import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useState } from 'react';
import SelectDropdown from './ui/SelectDropdown';
import BotaoIA from './ui/BotaoIA';
import { mockDataBidimensional, xAxisOptions, yAxisOptions, poloOptions } from '../data/mockData';

export default function ChartBidimensional() {
  const [eixoX, setEixoX] = useState('Cor/Etnia');
  const [eixoY, setEixoY] = useState('CRG');
  const [polo, setPolo] = useState('Todos');
  return (
    <div className="relative bg-white rounded-[2rem] shadow-[0_12px_40px_rgba(0,0,0,0.03)] border border-slate-100 p-8 w-full">
      {/* Container de filtros / Dropdowns */}
      <div className="flex justify-end gap-3.5 mb-8 flex-wrap">
        <SelectDropdown label="X" options={xAxisOptions} value={eixoX} onChange={setEixoX} />
        <SelectDropdown label="Y" options={yAxisOptions} value={eixoY} onChange={setEixoY} />
        <SelectDropdown label="Polo" options={poloOptions} value={polo} onChange={setPolo} />
      </div>

      {/* Área do Gráfico */}
      <div className="w-full pr-4">
        <ResponsiveContainer width="100%" height={380}>
          <BarChart
            data={mockDataBidimensional}
            margin={{ top: 10, right: 10, left: -20, bottom: 5 }}
            barSize={40} // Largura fixa das barras para combinar com a imagem
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
            
            <YAxis
              domain={[0, 10]}
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#64748b', fontSize: 13, fontWeight: 500 }}
              ticks={[0, 2, 4, 6, 8, 10]}
              dx={-8}
            />
            
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
              formatter={(value) => [typeof value === 'number' ? value.toFixed(2) : value, 'CRG']}
            />
            
            <Bar
              dataKey="crg"
              fill="url(#barGradient)"
              radius={[8, 8, 0, 0]}
              isAnimationActive={true}
              animationDuration={800}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <BotaoIA />
    </div>
  );
}
