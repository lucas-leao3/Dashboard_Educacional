import type { Sinalizacao } from '../../data/tipos';
import { ROTULO_SINALIZACAO } from '../../domain/classificacao';
import { COR_SINALIZACAO } from '../../theme/cores';

interface Props {
  valor: Sinalizacao;
  tamanho?: 'sm' | 'md';
}

/** Ponto colorido + texto: a sinalização nunca é comunicada só pela cor. */
export default function SinalizacaoBadge({ valor, tamanho = 'sm' }: Props) {
  const cor = COR_SINALIZACAO[valor];
  const classe = tamanho === 'md' ? 'text-sm px-3 py-1' : 'text-[11px] px-2 py-0.5';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${cor.fundo} ${cor.texto} ${classe}`}>
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: cor.hex }} aria-hidden="true" />
      {ROTULO_SINALIZACAO[valor]}
    </span>
  );
}
