import type { ItemHistorico } from '../../domain/historico';
import { ordenarParaExibir } from '../../domain/historico';

interface Props {
  itens: ItemHistorico[];
  onRepetir: (item: ItemHistorico) => void;
  onEditar: (item: ItemHistorico) => void;
  onFavoritar: (item: ItemHistorico) => void;
  onCompartilhar: (item: ItemHistorico) => void;
}

const ACAO = 'font-semibold text-blue-700 hover:underline';

export default function Historico({ itens, onRepetir, onEditar, onFavoritar, onCompartilhar }: Props) {
  const ordenados = ordenarParaExibir(itens);
  return (
    <aside aria-labelledby="titulo-historico" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <h2 id="titulo-historico" className="text-sm font-bold text-slate-900">Histórico</h2>
      {!ordenados.length ? (
        <p className="text-xs text-slate-500">Suas perguntas ficam aqui, só neste navegador.</p>
      ) : (
        <ul className="space-y-2">
          {ordenados.map((i) => (
            <li key={i.id} className="border-t border-slate-100 pt-2 text-xs">
              <p className="font-medium text-slate-800">{i.favorito && <span aria-label="Favorita">★ </span>}{i.pergunta}</p>
              <div className="mt-1 flex flex-wrap gap-3">
                <button type="button" className={ACAO} onClick={() => onRepetir(i)}>Repetir</button>
                <button type="button" className={ACAO} onClick={() => onEditar(i)}>Editar</button>
                <button type="button" className={ACAO} onClick={() => onFavoritar(i)} aria-pressed={i.favorito}>{i.favorito ? 'Desfavoritar' : 'Favoritar'}</button>
                <button type="button" className={ACAO} onClick={() => onCompartilhar(i)}>Compartilhar</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
