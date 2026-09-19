import type { Lote } from '../../data/tipos';

interface Props {
  lote: Lote;
  ocupado: boolean;
  onFechar: () => void;
}

export default function PassoFechar({ lote, ocupado, onFechar }: Props) {
  const total = Object.values(lote.excecoes_por_motivo).reduce((s, n) => s + n, 0);
  return (
    <div className="space-y-3 text-sm">
      <p className="text-slate-600">
        Passos 1 e 2 executados, {total} exceção(ões). Confira a cobertura abaixo e o dashboard antes de fechar.
        <strong> Fechar é definitivo:</strong> o lote não se reabre nem recebe mais PDFs.
      </p>
      <button type="button" onClick={onFechar} disabled={ocupado} className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
        {ocupado ? 'Fechando…' : 'Fechar lote'}
      </button>
    </div>
  );
}
