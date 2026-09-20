import type { Sinalizacao } from '../../data/tipos';
import { COR_SINALIZACAO } from '../../theme/cores';

interface KpiCardProps {
  label: string;
  value: string | number;
  /** Texto pequeno abaixo do valor (ex.: "n=61"). */
  hint?: string;
  /** Colore o valor com a cor de estado correspondente. */
  tone?: Extract<Sinalizacao, 'critico' | 'atencao'>;
}

/** Tile branco de indicador-resumo (as imagens de referência usam 4 a 6 por tela). */
export default function KpiCard({ label, value, hint, tone }: KpiCardProps) {
  return (
    <div className="rounded-2xl bg-white border border-slate-200/80 px-5 py-4 shadow-[0_4px_20px_rgba(15,23,42,0.03)] min-w-0">
      <p className="text-xs font-medium text-slate-500 leading-tight">{label}</p>
      <p className="mt-2 text-3xl font-extrabold tracking-tight leading-none" style={{ color: tone ? COR_SINALIZACAO[tone].hex : '#0f172a' }}>
        {value}
      </p>
      {hint && <p className="mt-1.5 text-[11px] text-slate-400">{hint}</p>}
    </div>
  );
}
