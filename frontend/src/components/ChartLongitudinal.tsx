import {
  LineChart,
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
import {
  mockDataLongitudinal,
  yAxisOptions,
  xLongitudinalOptions,
  turmaOptions,
  alunoOptions,
  poloOptions,
} from '../data/mockData';

export default function ChartLongitudinal() {
  const [eixoY, setEixoY] = useState('CRG');
  const [eixoX, setEixoX] = useState('2024-2027');
  const [turma, setTurma] = useState('2024.4');
  const [aluno, setAluno] = useState('Todos');
  const [polo, setPolo] = useState('Todos');
  return (
    <div className="relative bg-white rounded-[2rem] shadow-[0_12px_40px_rgba(0,0,0,0.03)] border border-slate-100 p-8 w-full">
      {/* Container de filtros / Dropdowns (5 Dropdowns) */}
      <div className="flex justify-end gap-3 mb-8 flex-wrap">
        <SelectDropdown label="Y" options={yAxisOptions} value={eixoY} onChange={setEixoY} />
        <SelectDropdown label="X" options={xLongitudinalOptions} value={eixoX} onChange={setEixoX} />
        <SelectDropdown label="Turma" options={turmaOptions} value={turma} onChange={setTurma} />
        <SelectDropdown label="Aluno" options={alunoOptions} value={aluno} onChange={setAluno} />
        <SelectDropdown label="Polo" options={poloOptions} value={polo} onChange={setPolo} />
      </div>

      {/* Área do Gráfico de Linhas */}
      <div className="w-full pr-4">
        <ResponsiveContainer width="100%" height={380}>
          <LineChart
            data={mockDataLongitudinal}
            margin={{ top: 10, right: 10, left: -20, bottom: 5 }}
          >
            <CartesianGrid vertical={false} stroke="#f1f5f9" strokeDasharray="0" />
            
            <XAxis
              dataKey="ano"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#64748b', fontSize: 13, fontWeight: 500 }}
              dy={12}
            />
            
            <YAxis
              domain={[2, 10]}
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#64748b', fontSize: 13, fontWeight: 500 }}
              ticks={[2, 4, 6, 8, 10]}
              dx={-8}
            />
            
            <Tooltip
              cursor={{ stroke: '#f1f5f9', strokeWidth: 1 }}
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
            />
            
            {/* Linha Azul (Crescente e suave) */}
            <Line
              type="monotone"
              dataKey="turmaA"
              name="Série A"
              stroke="#2563eb"
              strokeWidth={3}
              dot={false}
              activeDot={false}
              isAnimationActive={true}
              animationDuration={800}
            />

            {/* Linha Verde (Pequenas variações, terminando em alta) */}
            <Line
              type="monotone"
              dataKey="turmaB"
              name="Série B"
              stroke="#10b981"
              strokeWidth={3}
              dot={false}
              activeDot={false}
              isAnimationActive={true}
              animationDuration={800}
            />

            {/* Linha Vermelha (Muita variação, pico, queda forte no final) */}
            <Line
              type="monotone"
              dataKey="turmaC"
              name="Série C"
              stroke="#ef4444"
              strokeWidth={3}
              dot={false}
              activeDot={false}
              isAnimationActive={true}
              animationDuration={800}
            />

            {/* Linha Roxa (Começa baixo, sobe, desce, sobe) */}
            <Line
              type="monotone"
              dataKey="turmaD"
              name="Série D"
              stroke="#8b5cf6"
              strokeWidth={3}
              dot={false}
              activeDot={false}
              isAnimationActive={true}
              animationDuration={800}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <BotaoIA />
    </div>
  );
}
