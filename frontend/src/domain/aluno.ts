/**
 * Como um aluno é identificado na tela. Um lugar só: seis componentes faziam
 * `nome ?? \`Matrícula ${m}\`` por conta própria, e o resultado era uma grade
 * meio com nome e meio com número -- que parecia inconsistência da interface,
 * mas era a cobertura dos PDFs aparecendo. O `nome` não vem do FasiTech; ele
 * é lido do histórico em PDF no passo 2, e só metade da base tem PDF.
 */

/** Marcador de ausência, o mesmo já usado nos KPIs e na tabela de cobertura. */
export const SEM_NOME = '—';

// Partículas que ficam em minúscula no meio do nome (pt-BR).
const PARTICULAS = new Set(['de', 'da', 'do', 'das', 'dos', 'e']);

/** Capitaliza cada trecho, respeitando hífen e apóstrofo ("D'Avila", "Maria-Jose"). */
function capitalizarPalavra(palavra: string): string {
  return palavra.replace(/[^\s\-']+/g, (t) => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase());
}

/**
 * Nome pronto para exibir, ou null se não houver.
 *
 * O SIGAA entrega em CAIXA ALTA, e caixa alta em título de card atrapalha a
 * leitura de uma grade com dezenas de nomes. A transformação é só de
 * exibição: o valor gravado em `usuarios` e o `vigente.csv` do lote continuam
 * com o original, que é o que vale como registro.
 */
export function nomeExibido(nome: string | null | undefined): string | null {
  const limpo = (nome ?? '').trim().replace(/\s+/g, ' ');
  if (!limpo) return null;
  return limpo
    .split(' ')
    .map((palavra, i) =>
      i > 0 && PARTICULAS.has(palavra.toLowerCase()) ? palavra.toLowerCase() : capitalizarPalavra(palavra),
    )
    .join(' ');
}

/**
 * "Nome · matrícula", com o travessão no lugar do nome quando ele falta.
 *
 * A matrícula está SEMPRE presente, e de propósito: ela é o identificador
 * estável do aluno (é dela que saem turma e polo, §4.8) e é por ela que se
 * cruza acadêmico com socioeconômico. Mostrar só o nome faria dois alunos
 * homônimos virarem a mesma linha aos olhos de quem lê.
 */
export function identificacao(nome: string | null | undefined, matricula: number | string): string {
  return `${nomeExibido(nome) ?? SEM_NOME} · ${matricula}`;
}
