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
      className="rounded-2xl px-6 py-5 w-[220px] shadow-[0_8px_30px_rgb(0,0,0,0.06)] flex flex-col justify-between h-[108px] transition-all duration-300 hover:translate-y-[-2px] hover:shadow-[0_12px_35px_rgb(0,0,0,0.1)]"
      style={{
        background: isLight
          ? 'linear-gradient(135deg, #1d61e1 0%, #154eb5 100%)' // Azul real vívido
          : 'linear-gradient(135deg, #1852cc 0%, #0f3ba1 100%)', // Azul real escuro
      }}
    >
      <div>
        <p className="text-[10px] font-bold tracking-wider text-white/70 uppercase">
          {label}
        </p>
      </div>
      <div className="flex items-end justify-between leading-none">
        <span className="text-[34px] font-extrabold text-white tracking-tight leading-none">{value}</span>
        <span className="text-white/80 pb-0.5">{icon}</span>
      </div>
    </div>
  );
}
