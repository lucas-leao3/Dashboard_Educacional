import { useId } from 'react';

export interface OpcaoSelect<T extends string = string> {
  value: T;
  label: string;
}

interface SelectDropdownProps<T extends string> {
  /** Rótulo lido por leitores de tela e mostrado como prefixo da opção. */
  label: string;
  value: T;
  options: readonly (OpcaoSelect<T> | T)[];
  onChange: (value: T) => void;
  /** Mostra "Rótulo: valor" dentro do select (padrão) ou só o valor. */
  prefixo?: boolean;
  className?: string;
}

const IconChevron = () => (
  <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

/** Select em formato de "chip", compartilhado por todos os filtros do painel. */
export default function SelectDropdown<T extends string>({
  label, value, options, onChange, prefixo = true, className = '',
}: SelectDropdownProps<T>) {
  const id = useId();
  const normalizadas = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o));
  return (
    <div className={`relative inline-block ${className}`}>
      <label htmlFor={id} className="sr-only">{label}</label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="appearance-none bg-white border border-slate-200 text-slate-700 text-xs font-semibold rounded-full pl-4 pr-10 py-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400/50 transition-colors hover:bg-slate-50 max-w-full"
      >
        {normalizadas.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {prefixo ? `${label}: ${opt.label}` : opt.label}
          </option>
        ))}
      </select>
      <span className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
        <IconChevron />
      </span>
    </div>
  );
}
