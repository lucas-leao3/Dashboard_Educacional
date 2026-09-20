import { useMemo } from 'react';
import AppShell from '../components/layout/AppShell';
import MetricCard from '../components/MetricCard';
import ChartBidimensional from '../components/ChartBidimensional';
import ChartDistribuicao from '../components/ChartDistribuicao';
import ChartLongitudinal from '../components/ChartLongitudinal';
import { agregar } from '../domain/agregacao';
import { useDados } from '../hooks/useDados';

// Ícone de pessoas (Matrículas)
const IconPeople = () => (
  <svg className="w-6 h-6 text-white/90" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
);

// Ícone de seta de tendência (CRG)
const IconTrending = () => (
  <svg className="w-6 h-6 text-white/95" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
    <polyline points="17 6 23 6 23 12"/>
  </svg>
);

const TITULO = {
  bidimensional: 'Análise Bidimensional',
  distribuicao: 'Distribuição',
  longitudinal: 'Análise Longitudinal',
} as const;

interface AnalisesProps {
  tipo: keyof typeof TITULO;
}

/** Gráficos agregados do dashboard anterior, agora dentro da moldura comum. */
export default function Analises({ tipo }: AnalisesProps) {
  const { alunos } = useDados();
  const resumo = useMemo(() => agregar(alunos), [alunos]);
  const crg = resumo.indicadores.crg_medio;

  return (
    <AppShell titulo={TITULO[tipo]} migalhas={[{ rotulo: 'Análises' }, { rotulo: TITULO[tipo] }]}>
      {/* Cards de Métricas alinhados à direita */}
      <div className="flex flex-wrap justify-end gap-5">
        <MetricCard label="Matrículas Únicas" value={String(resumo.alunos)} icon={<IconPeople />} variant="light" />
        <MetricCard label="CRG Médio" value={crg === null ? '—' : crg.toFixed(3).replace('.', ',')} icon={<IconTrending />} variant="dark" />
      </div>

      {/* Card do Gráfico Dinâmico */}
      <div className="min-h-[450px] pb-8">
        {tipo === 'bidimensional' && <ChartBidimensional />}
        {tipo === 'distribuicao' && <ChartDistribuicao />}
        {tipo === 'longitudinal' && <ChartLongitudinal />}
      </div>
    </AppShell>
  );
}
