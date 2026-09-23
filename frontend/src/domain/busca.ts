/**
 * Busca de aluno na barra do cabeçalho.
 *
 * Casava só por igualdade exata (matrícula inteira, ou o nome cru inteiro).
 * Como a tela agora mostra o nome capitalizado, copiar o que está na tela e
 * colar na busca não encontrava nada -- a comparação era contra o valor em
 * CAIXA ALTA do banco. Aqui o casamento é por trecho, sem caixa e sem acento.
 */
import type { Aluno } from './agregacao';

/** Minúsculas e sem acento: 'MARIA JOSÉ' e 'maria jose' têm que casar. */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

/**
 * Alunos que casam com o termo, por trecho do nome ou da matrícula.
 *
 * A ordem não é arbitrária: matrícula exata primeiro (quem digita 12 dígitos
 * quer aquele aluno), depois quem COMEÇA com o termo, depois quem apenas o
 * contém. Dentro de cada grupo, por matrícula, para a lista não dançar entre
 * teclas. Termo vazio devolve nada -- listar 111 alunos não é busca.
 */
export function buscarAlunos(alunos: Aluno[], termo: string, limite = 8): Aluno[] {
  const alvo = normalizar(termo);
  if (!alvo) return [];

  const pontuados: { aluno: Aluno; peso: number }[] = [];
  for (const aluno of alunos) {
    const matricula = String(aluno.matricula);
    const nome = normalizar(aluno.vigente.nome ?? '');

    const peso =
      matricula === alvo ? 0
      : nome && nome.startsWith(alvo) ? 1
      : matricula.startsWith(alvo) ? 2
      : nome && nome.includes(alvo) ? 3
      : matricula.includes(alvo) ? 4
      : -1;

    if (peso >= 0) pontuados.push({ aluno, peso });
  }

  return pontuados
    .sort((a, b) => a.peso - b.peso || a.aluno.matricula - b.aluno.matricula)
    .slice(0, limite)
    .map((p) => p.aluno);
}
