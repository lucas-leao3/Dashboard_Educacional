import type { RespostaAssistente } from '../../data/tipos';
import DashboardDinamico from './DashboardDinamico';
import Explicacao from './Explicacao';
import RespostaTabela from './RespostaTabela';

interface Props {
  resposta: RespostaAssistente;
  onSugestao: (pergunta: string) => void;
}

export default function RespostaView({ resposta, onSugestao }: Props) {
  return (
    <article aria-label={resposta.pergunta ?? 'Consulta'} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      {resposta.pergunta && <p className="text-sm font-semibold text-slate-900">{resposta.pergunta}</p>}
      {resposta.texto && <p className="text-base text-slate-800">{resposta.texto.mensagem}</p>}
      {resposta.tabela && <RespostaTabela tabela={resposta.tabela} />}
      {resposta.dinamico && <DashboardDinamico bloco={resposta.dinamico} />}
      {resposta.nao_entendi && (
        <div className="space-y-2">
          <p className="text-sm text-slate-700">{resposta.nao_entendi.motivo}</p>
          <p className="text-xs text-slate-500">Experimente:</p>
          <ul className="flex flex-wrap gap-2">
            {resposta.nao_entendi.sugestoes.map((s) => (
              <li key={s}><button type="button" onClick={() => onSugestao(s)} className="rounded-full border border-slate-300 px-3 py-1 text-xs hover:border-blue-400">{s}</button></li>
            ))}
          </ul>
        </div>
      )}
      <Explicacao explicacao={resposta.explicacao} />
    </article>
  );
}
