import type { NovoLote } from '../../data/api';
import type { HistoricosOut, Lote } from '../../data/tipos';
import { passoAtual } from '../../domain/lote';
import PassoAbrir from './PassoAbrir';
import PassoEnviar, { ResultadoEnvio } from './PassoEnviar';
import PassoFechar from './PassoFechar';

interface Props {
  lote: Lote | null;
  lotes: Lote[];
  ocupado: boolean;
  erro: string | null;
  resultadoEnvio: HistoricosOut | null;
  onAbrir: (dados: NovoLote) => void;
  onEnviar: (arquivos: File[]) => void;
  onFechar: () => void;
}

const PASSOS = [
  { n: 1, rotulo: 'Abrir' },
  { n: 2, rotulo: 'Enviar PDFs e rodar' },
  { n: 3, rotulo: 'Conferir e fechar' },
] as const;

function formatarData(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('pt-BR');
}

/** Stepper de 3 passos; o passo ativo vem só do estado do lote na API. */
export default function InserirLote({ lote, lotes, ocupado, erro, resultadoEnvio, onAbrir, onEnviar, onFechar }: Props) {
  const atual = passoAtual(lote);

  return (
    <section className="rounded-2xl bg-white border border-slate-200/80 p-5 space-y-4" aria-labelledby="inserir-titulo">
      <h2 id="inserir-titulo" className="text-base font-bold text-slate-800">Inserir lote</h2>

      <ol className="flex flex-wrap gap-2 text-xs">
        {PASSOS.map((p) => {
          const estado = atual === null || p.n < atual ? 'feito' : p.n === atual ? 'atual' : 'pendente';
          const cor = estado === 'feito' ? 'bg-emerald-100 text-emerald-800' : estado === 'atual' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-500';
          return <li key={p.n} className={`rounded-full px-3 py-1 font-semibold ${cor}`} aria-current={estado === 'atual' ? 'step' : undefined}>{p.n}. {p.rotulo}</li>;
        })}
      </ol>

      {erro && <p role="alert" className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">{erro}</p>}

      {atual === 1 && <PassoAbrir lotes={lotes} ocupado={ocupado} onAbrir={onAbrir} />}
      {atual === 2 && <PassoEnviar ocupado={ocupado} onEnviar={onEnviar} />}
      {atual === 3 && lote && <PassoFechar lote={lote} ocupado={ocupado} onFechar={onFechar} />}
      {atual === null && lote?.fechado_em && (
        <p className="text-sm text-slate-600">Fechado em {formatarData(lote.fechado_em)}. Para inserir mais dados, abra um lote novo.</p>
      )}

      {resultadoEnvio && <ResultadoEnvio resultado={resultadoEnvio} />}
    </section>
  );
}
