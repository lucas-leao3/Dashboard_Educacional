import type { Lote } from '../data/tipos';

function formatarData(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

interface Props {
  lote: Lote;
}

/**
 * Selo do lote vigente no AppShell -- deixa claro de onde vem o dado real e
 * que os indicadores usam só alunos integrados.
 */
export default function SeloLote({ lote }: Props) {
  const periodo = lote.periodos_cobertos.join(', ');
  return (
    <span
      className="hidden sm:inline-flex shrink-0 text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2.5 py-1"
      title="Indicadores calculados só com alunos integrados (acadêmico + socioeconômico). Os demais estão no relatório do lote, na tela Dados."
    >
      Lote {lote.id}{periodo && ` · período ${periodo}`} · {formatarData(lote.executado_em)}
    </span>
  );
}
