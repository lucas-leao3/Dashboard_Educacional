import type { ExplicacaoAssistente, FormaResposta } from '../../data/tipos';

export const ROTULO_FORMA: Record<FormaResposta, string> = {
  dashboard: 'Dashboard existente', dinamico: 'Dashboard dinâmico', tabela: 'Tabela', texto: 'Texto', nao_entendi: 'Não entendi',
};

/** As quatro respostas que toda consulta deve (spec, Resposta explicável). */
export default function Explicacao({ explicacao }: { explicacao: ExplicacaoAssistente }) {
  const filtros = explicacao.filtros_aplicados.map((f) => `${f.rotulo}: ${f.valor}`).join(' · ');
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
      <dt className="font-semibold text-slate-700">Consulta interpretada</dt><dd>{explicacao.consulta_interpretada}</dd>
      <dt className="font-semibold text-slate-700">Filtros aplicados</dt><dd>{filtros || 'Nenhum'}</dd>
      <dt className="font-semibold text-slate-700">Fonte dos dados</dt><dd>{explicacao.fontes.join(', ') || '—'}</dd>
      <dt className="font-semibold text-slate-700">Forma de resposta</dt><dd>{ROTULO_FORMA[explicacao.forma]}</dd>
    </dl>
  );
}
