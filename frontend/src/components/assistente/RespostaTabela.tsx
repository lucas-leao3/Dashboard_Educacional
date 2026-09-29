import { useState } from 'react';
import type { BlocoTabela, Celula } from '../../data/tipos';
import { paraCsv } from '../../domain/csv';

const POR_PAGINA = 25;

/** Inteiro cru (matrícula não ganha separador de milhar); decimal em pt-BR; vazio vira "—". */
function formatar(v: Celula | undefined): string {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  return v;
}

export default function RespostaTabela({ tabela }: { tabela: BlocoTabela }) {
  const [pagina, setPagina] = useState(0);
  const paginas = Math.max(1, Math.ceil(tabela.linhas.length / POR_PAGINA));
  const visiveis = tabela.linhas.slice(pagina * POR_PAGINA, (pagina + 1) * POR_PAGINA);

  const exportar = () => {
    const url = URL.createObjectURL(new Blob([paraCsv(tabela.colunas, tabela.linhas)], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'consulta.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <p>{tabela.total} registro(s){tabela.total > tabela.linhas.length ? ` · mostrando os primeiros ${tabela.linhas.length}` : ''}</p>
        <button type="button" onClick={exportar} className="rounded-lg border border-slate-300 px-3 py-1 font-semibold text-slate-700 hover:border-blue-400">Exportar CSV</button>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead><tr>{tabela.colunas.map((c) => <th key={c.id} scope="col" className="px-2 py-1 text-left font-semibold text-slate-700">{c.rotulo}</th>)}</tr></thead>
          <tbody>
            {visiveis.map((linha, i) => (
              <tr key={i} className="border-t border-slate-100">{tabela.colunas.map((c) => <td key={c.id} className="px-2 py-1">{formatar(linha[c.id])}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {paginas > 1 && (
        <nav aria-label="Paginação" className="flex items-center gap-3 text-xs">
          <button type="button" disabled={pagina === 0} onClick={() => setPagina((p) => p - 1)} className="font-semibold text-blue-700 disabled:text-slate-400">Anterior</button>
          <span>Página {pagina + 1} de {paginas}</span>
          <button type="button" disabled={pagina >= paginas - 1} onClick={() => setPagina((p) => p + 1)} className="font-semibold text-blue-700 disabled:text-slate-400">Próxima</button>
        </nav>
      )}
    </div>
  );
}
