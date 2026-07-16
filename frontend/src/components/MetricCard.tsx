import React from 'react';

interface MetricCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  variant?: 'light' | 'dark';
}

export default function MetricCard({ label, value, icon, variant = 'light' }: MetricCardProps) {
  const isLight = variant === 'light';

  return (
    <div
      className="rounded-2xl px-6 py-4.5 w-[230px] shadow-[0_8px_30px_rgba(0,0,0,0.03)] flex flex-col justify-between h-[106px] transition-all duration-300 hover:translate-y-[-2px] hover:shadow-[0_12px_35px_rgba(0,0,0,0.06)] cursor-default"
      style={{
        background: isLight
          ? 'linear-gradient(135deg, #1d5ad8 0%, #154eb5 100%)' // Azul real vibrante
          : 'linear-gradient(135deg, #1146b8 0%, #0b3185 100%)', // Azul real profundo
      }}
    >
      <div>
        <p className="text-[10px] font-bold tracking-wider text-white/70 uppercase">
          {label}
        </p>
      </div>
      {/* Alinhamento justify-between afasta o valor e o ícone exatamente como nas imagens de referência */}
      <div className="flex items-end justify-between leading-none w-full">
        <span className="text-[34px] font-extrabold text-white tracking-tight leading-none">{value}</span>
        <span className="text-white/80 pb-0.5">{icon}</span>
      </div>
    </div>
  );
}
