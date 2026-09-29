import type { BlocoDinamico } from '../../data/tipos';
import KpiCard from '../ui/KpiCard';
import GraficoDinamico from './GraficoDinamico';

export default function DashboardDinamico({ bloco }: { bloco: BlocoDinamico }) {
  return (
    <div className="space-y-4">
      {bloco.kpis.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {bloco.kpis.map((k) => <KpiCard key={k.rotulo} label={k.rotulo} value={k.valor === null ? '—' : k.valor.toLocaleString('pt-BR')} hint={`n=${k.n}`} />)}
        </div>
      )}
      {bloco.graficos.map((g) => <GraficoDinamico key={g.titulo} grafico={g} />)}
    </div>
  );
}
