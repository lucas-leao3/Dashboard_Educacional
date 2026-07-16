import Sidebar from '../components/Sidebar';
import MetricCard from '../components/MetricCard';
import ChartBidimensional from '../components/ChartBidimensional';
import ChartDistribuicao from '../components/ChartDistribuicao';
import ChartLongitudinal from '../components/ChartLongitudinal';

// Ícone de pessoas (Matrículas) de acordo com a foto
const IconPeople = () => (
  <svg className="w-6 h-6 text-white/90" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
);

// Ícone de seta de tendência (CRG) de acordo com a foto
const IconTrending = () => (
  <svg className="w-6 h-6 text-white/95" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
    <polyline points="17 6 23 6 23 12"/>
  </svg>
);

interface DashboardProps {
  tipo: 'bidimensional' | 'distribuicao' | 'longitudinal';
}

export default function Dashboard({ tipo }: DashboardProps) {
  let pageTitle = 'Visualização Bidimensional';
  if (tipo === 'distribuicao') {
    pageTitle = 'Visualização Distribuída';
  } else if (tipo === 'longitudinal') {
    pageTitle = 'Visualização Longitudinal';
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans">
      {/* Sidebar Fixo à Esquerda */}
      <Sidebar />

      {/* Conteúdo à Direita */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Top Header Bar */}
        <header className="shrink-0 w-full bg-[#f8fafc] border-b border-slate-150 px-8 py-3.5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-400 tracking-wide">{pageTitle}</h2>
        </header>

        {/* Área de Conteúdo com Gradiente Suave */}
        <main
          className="flex-1 overflow-y-auto px-10 py-8 space-y-7 flex flex-col justify-start"
          style={{
            background: 'linear-gradient(135deg, #e0ebff 0%, #ebe7fe 40%, #f7f9ff 100%)',
          }}
        >
          {/* Cards de Métricas alinhados à direita */}
          <div className="flex justify-end gap-5">
            <MetricCard
              label="Matrículas Únicas"
              value="56"
              icon={<IconPeople />}
              variant="light"
            />
            <MetricCard
              label="CRG Médio"
              value="8,850"
              icon={<IconTrending />}
              variant="dark"
            />
          </div>

          {/* Card do Gráfico Dinâmico */}
          <div className="flex-1 min-h-[450px]">
            {tipo === 'bidimensional' && <ChartBidimensional />}
            {tipo === 'distribuicao' && <ChartDistribuicao />}
            {tipo === 'longitudinal' && <ChartLongitudinal />}
          </div>
        </main>
      </div>
    </div>
  );
}
