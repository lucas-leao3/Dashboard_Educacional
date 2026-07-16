import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  mockDataLongitudinal,
  yAxisOptions,
  xLongitudinalOptions,
  turmaOptions,
  alunoOptions,
  poloOptions,
} from '../data/mockData';

// Chevron para dropdowns
const IconChevron = () => (
  <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9"/>
  </svg>
);

// Ícone de ondas de áudio/voz para o botão de chat flutuante
const IconAudioWave = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"/>
    <line x1="8" y1="9" x2="8" y2="15"/>
    <line x1="16" y1="9" x2="16" y2="15"/>
    <line x1="4" y1="11" x2="4" y2="13"/>
    <line x1="20" y1="11" x2="20" y2="13"/>
  </svg>
);

interface SelectDropdownProps {
  label: string;
  options: string[];
  defaultValue: string;
  noValuePrefix?: boolean;
}

function SelectDropdown({ label, options, defaultValue, noValuePrefix = false }: SelectDropdownProps) {
  return (
    <div className="relative inline-block">
      <select
        defaultValue={defaultValue}
        className="appearance-none bg-slate-50 border border-slate-100/80 text-slate-600 text-xs font-semibold rounded-full pl-4 pr-10 py-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400/40 transition-all hover:bg-slate-100"
      >
        {noValuePrefix ? (
          <option value={defaultValue}>{label}</option>
        ) : (
          options.map((opt) => (
            <option key={opt} value={opt}>
              {label} : {opt}
            </option>
          ))
        )}
        {noValuePrefix && options.filter(opt => opt !== defaultValue).map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
      <span className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
        <IconChevron />
      </span>
    </div>
  );
}

export default function ChartLongitudinal() {
  return (
    <div className="relative bg-white rounded-[2rem] shadow-[0_12px_40px_rgba(0,0,0,0.03)] border border-slate-100 p-8 w-full">
      {/* Container de filtros / Dropdowns (5 Dropdowns) */}
      <div className="flex justify-end gap-3 mb-8 flex-wrap">
        <SelectDropdown label="Y" options={yAxisOptions} defaultValue="CRG" />
        <SelectDropdown label="X" options={xLongitudinalOptions} defaultValue="2024-2027" />
        <SelectDropdown label="Turma" options={turmaOptions} defaultValue="2024" />
        <SelectDropdown label="Aluno" options={alunoOptions} defaultValue="Todos" noValuePrefix={true} />
        <SelectDropdown label="Polo" options={poloOptions} defaultValue="Todos" noValuePrefix={true} />
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

      {/* Botão flutuante de IA Chat no canto inferior direito */}
      <button
        title="Abrir IA Chat"
        className="absolute -bottom-6 -right-2 w-14 h-14 rounded-full flex items-center justify-center shadow-lg hover:shadow-xl hover:scale-110 active:scale-95 transition-all duration-200 cursor-pointer"
        style={{
          background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
          boxShadow: '0 8px 30px rgba(37, 99, 235, 0.35)',
        }}
      >
        <IconAudioWave />
      </button>
    </div>
  );
}
