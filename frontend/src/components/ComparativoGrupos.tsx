import { useState } from 'react';
import { Link } from 'react-router-dom';
import { INDICADORES, indicador } from '../domain/agregacao';
import type { Agregado, IndicadorId } from '../domain/agregacao';
import { DIMENSOES } from '../domain/dimensoes';
import SelectDropdown from './ui/SelectDropdown';
import type { OpcaoSelect } from './ui/SelectDropdown';
import { COR_PRIMARIA } from '../theme/cores';

export interface Grupo {
  chave: string;
  rotulo: string;
  /** Cor de identidade (polos). Sem cor, usa a primária: o rótulo já identifica. */
  cor?: string;
  href: string;
  agregado: Agregado;
}

interface Props {
  titulo: string;
  descricao?: string;
  grupos: Grupo[];
  indicadorInicial?: IndicadorId;
}

const OPCOES: OpcaoSelect<IndicadorId>[] = INDICADORES.map((i) => {
  const dim = DIMENSOES.find((d) => d.id === i.dimensao);
  return { value: i.id, label: dim ? `${i.rotulo} (${dim.rotuloCurto})` : i.rotulo };
});

/**
 * Ranking horizontal comparando polos (ou turmas) por um indicador
 * selecionável, com o tamanho da amostra sempre visível (doc, itens 4 e 8).
 * Construído em HTML: cada linha é um link para descer na hierarquia.
 */
export default function ComparativoGrupos({ titulo, descricao, grupos, indicadorInicial = 'crg_medio' }: Props) {
  const [indicadorId, setIndicadorId] = useState<IndicadorId>(indicadorInicial);
  const ind = indicador(indicadorId);
  const valores = grupos.map((g) => g.agregado.indicadores[indicadorId]);
  const max = ind.max || Math.max(1, ...valores.map((v) => v ?? 0));

  return (
    <section className="rounded-[1.5rem] bg-white border border-slate-200/80 p-6 shadow-[0_4px_20px_rgba(15,23,42,0.03)]">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
        <div>
          <h2 className="text-lg font-bold text-slate-900">{titulo}</h2>
          {descricao && <p className="text-xs text-slate-500 mt-1 max-w-xl">{descricao}</p>}
        </div>
        <SelectDropdown label="Indicador" value={indicadorId} options={OPCOES} onChange={setIndicadorId} />
      </div>

      <ol className="space-y-3">
        {grupos.map((g, i) => {
          const valor = valores[i];
          const largura = valor === null ? 0 : Math.min(100, (valor / max) * 100);
          return (
            <li key={g.chave}>
              <Link
                to={g.href}
                className="grid grid-cols-[minmax(0,9rem)_1fr] sm:grid-cols-[minmax(0,12rem)_1fr_auto] items-center gap-x-4 gap-y-1 rounded-xl border border-slate-100 px-4 py-3 hover:border-blue-300 hover:bg-blue-50/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 transition-colors"
                aria-label={`${g.rotulo}: ${valor === null ? 'sem dado' : ind.formatar(valor)} em ${ind.rotulo}. Abrir detalhes`}
              >
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 min-w-0">
                  <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: g.cor ?? COR_PRIMARIA }} aria-hidden="true" />
                  <span className="font-semibold text-slate-800 truncate">{g.rotulo}</span>
                  {g.agregado.nBaixo && (
                    <span className="text-[10px] font-bold text-amber-700 bg-amber-50 rounded-full px-1.5 py-px shrink-0">n baixo</span>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden" aria-hidden="true">
                    <div className="h-full rounded-r-full transition-[width] duration-500" style={{ width: `${largura}%`, background: g.cor ?? COR_PRIMARIA }} />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    CRG médio {g.agregado.indicadores.crg_medio === null ? '—' : g.agregado.indicadores.crg_medio.toFixed(2)}
                    <span className="mx-1.5" aria-hidden="true">·</span>
                    n={g.agregado.alunos} alunos ({g.agregado.registros} registros)
                  </p>
                </div>
                <div className="col-start-2 sm:col-start-3 text-right sm:min-w-[7rem]">
                  <span className="text-base font-extrabold text-slate-900">{valor === null ? '—' : ind.formatar(valor)}</span>
                  <span className="block text-[11px] text-slate-500">{ind.rotulo}</span>
                </div>
              </Link>
            </li>
          );
        })}
      </ol>
      {!grupos.length && <p className="text-sm text-slate-500">Nenhum grupo para o filtro atual.</p>}
    </section>
  );
}
