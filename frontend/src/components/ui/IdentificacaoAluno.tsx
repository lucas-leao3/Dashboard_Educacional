import { SEM_NOME, nomeExibido } from '../../domain/aluno';

interface Props {
  nome: string | null | undefined;
  matricula: number;
  /** Versão menor, para grades densas. */
  compacto?: boolean;
}

/**
 * Identificação do aluno em DUAS LINHAS: nome em cima, matrícula embaixo.
 *
 * Em uma linha só ("Nome · matrícula") o `truncate` do card comia justamente
 * a matrícula -- "Andrey Azevedo do Carmo · 20…" --, que é o identificador
 * estável e o que nunca deveria sumir. Empilhado, o nome pode truncar à
 * vontade (ele é longo e variável) e os 12 dígitos cabem sempre.
 *
 * `tabular-nums` mantém os dígitos alinhados entre cards, o que faz a coluna
 * de matrículas ficar legível ao varrer a grade de cima a baixo.
 */
export default function IdentificacaoAluno({ nome, matricula, compacto = false }: Props) {
  const exibido = nomeExibido(nome);
  return (
    <span className="block min-w-0">
      <span
        className={`block truncate font-bold ${compacto ? 'text-sm' : ''} ${
          exibido ? 'text-slate-900 group-hover:text-blue-700' : 'text-slate-400'
        }`}
        title={exibido ?? 'Sem nome no histórico'}
      >
        {exibido ?? SEM_NOME}
      </span>
      <span className="block text-[11px] font-medium text-slate-500 tabular-nums tracking-tight">
        {matricula}
      </span>
    </span>
  );
}
