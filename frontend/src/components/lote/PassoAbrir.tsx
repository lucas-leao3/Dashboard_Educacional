import { useState } from 'react';
import type { FormEvent } from 'react';
import type { NovoLote } from '../../data/api';
import type { Lote } from '../../data/tipos';
import { sugerirIdLote, validarIdLote } from '../../domain/lote';

interface Props {
  lotes: Lote[];
  ocupado: boolean;
  onAbrir: (dados: NovoLote) => void;
}

const INPUT = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500';

export default function PassoAbrir({ lotes, ocupado, onAbrir }: Props) {
  const [id, setId] = useState(() => sugerirIdLote(new Date(), lotes));
  const [periodos, setPeriodos] = useState('');
  const [por, setPor] = useState('');
  const idValido = validarIdLote(id);
  const lista = periodos.split(/[,\s]+/).map((p) => p.trim()).filter(Boolean);

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (!idValido || lista.length === 0) return;
    onAbrir({ id, periodos_cobertos: lista, executado_por: por.trim() || null });
  }

  return (
    <form onSubmit={enviar} className="space-y-3">
      <label className="block text-sm">
        <span className="font-medium text-slate-700">Id do lote</span>
        <input className={INPUT} value={id} onChange={(e) => setId(e.target.value)} aria-invalid={!idValido} />
        {!idValido && <span className="text-xs text-red-700">Só letras, dígitos, "-" e "_", de 3 a 20 caracteres.</span>}
      </label>
      <label className="block text-sm">
        <span className="font-medium text-slate-700">Períodos cobertos</span>
        <input className={INPUT} value={periodos} onChange={(e) => setPeriodos(e.target.value)} placeholder="2025.2 2026.1" />
        <span className="text-xs text-slate-500">Separe por espaço ou vírgula.</span>
      </label>
      <label className="block text-sm">
        <span className="font-medium text-slate-700">Executado por</span>
        <input className={INPUT} value={por} onChange={(e) => setPor(e.target.value)} />
      </label>
      <button type="submit" disabled={ocupado || !idValido || lista.length === 0} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
        Abrir lote
      </button>
    </form>
  );
}
