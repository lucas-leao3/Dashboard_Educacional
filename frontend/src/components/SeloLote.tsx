import type { Lote } from '../data/tipos';

function formatarData(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

interface Props {
  lote: Lote;
}

/** Selo do lote vigente no AppShell -- deixa claro de onde vem o dado real. */
export default function SeloLote({ lote }: Props) {
  const total = Object.values(lote.excecoes_por_motivo).reduce((soma, n) => soma + n, 0);
  const detalheExcecoes = Object.entries(lote.excecoes_por_motivo)
    .map(([motivo, n]) => `${motivo}: ${n}`)
    .join(', ');

  return (
    <span
      className="hidden sm:inline-flex shrink-0 text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2.5 py-1"
      title={detalheExcecoes || 'Nenhuma exceção neste lote'}
    >
      Lote {lote.id} · {formatarData(lote.executado_em)} · {total} exceções
    </span>
  );
}
