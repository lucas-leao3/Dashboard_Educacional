import { N_MINIMO } from '../../domain/agregacao';
import type { BarraCategoria } from '../../domain/analises';

/**
 * Rodapé com o n de cada categoria e o aviso de amostra pequena. Existe
 * porque média sozinha é enganosa: nesta base há categoria com um único
 * aluno, e sem o n a barra dela parece tão sólida quanto a de quarenta.
 */
export default function AvisoAmostra({ barras }: { barras: BarraCategoria[] }) {
  const pequenas = barras.filter((b) => b.nBaixo);
  const semNota = barras.filter((b) => b.valor === null);
  return (
    <div className="mt-6 pt-4 border-t border-slate-100 space-y-1.5 text-[11px] text-slate-500">
      <p>
        <span className="font-semibold text-slate-600">n por categoria: </span>
        {barras.map((b) => `${b.categoria} ${b.nComNota}/${b.n}`).join(' · ')}
      </p>
      {pequenas.length > 0 && (
        <p className="text-amber-700">
          Amostra abaixo de {N_MINIMO} em {pequenas.length === barras.length ? 'todas as categorias' : pequenas.map((b) => b.categoria).join(', ')} — leia com cautela.
        </p>
      )}
      {semNota.length > 0 && (
        <p>Sem CRG apurado (barra ausente): {semNota.map((b) => b.categoria).join(', ')}.</p>
      )}
    </div>
  );
}
