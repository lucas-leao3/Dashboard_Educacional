import { POLOS_POR_CODIGO } from '../domain/matricula';
import type { CrgSemestre, Registro } from './tipos';

/**
 * Dataset de DEMONSTRAÇÃO, gerado de forma determinística (mesma semente =
 * mesmos dados) com as distribuições observadas no DadosAgrupados.csv:
 * 3 janelas de período, 3 polos, ~75 alunos e ~120 registros. Nenhum dado
 * pessoal real: matrículas e nomes são sintéticos. Usado só quando a API
 * (VITE_API_URL) não está disponível.
 *
 * As matrículas têm os 12 dígitos reais (ano + polo + sequencial) e os campos
 * `polo` e `primeiro_ano_eletivo` saem NULOS -- é exatamente o que o FasiTech
 * devolve. Assim a demonstração exercita a mesma derivação da produção
 * (domain/matricula.ts) em vez de mascarar o problema com dado que a fonte
 * não tem.
 */

// PRNG mulberry32: pequeno e reprodutível.
function criarAleatorio(semente: number) {
  let s = semente >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Sorteia uma opção com pesos (frequências reais do CSV). */
function criarSorteio(aleatorio: () => number) {
  return function sortear<T>(opcoes: [T, number][]): T {
    const total = opcoes.reduce((s, [, p]) => s + p, 0);
    let x = aleatorio() * total;
    for (const [valor, peso] of opcoes) {
      x -= peso;
      if (x <= 0) return valor;
    }
    return opcoes[opcoes.length - 1][0];
  };
}

export const PERIODOS_DEMO = ['2024.(1 e 2)', '2024.(3 e 4)', '2025.(3 e 4)'] as const;

// Códigos de polo (dígitos 5-8 da matrícula) com as frequências reais do CSV.
const POLOS: [string, number][] = [['1604', 61], ['8594', 10], ['8564', 4]];
// Anos de ingresso (dígitos 1-4) com as frequências reais do CSV.
const TURMAS: [string, number][] = [['2020', 4], ['2021', 10], ['2022', 9], ['2023', 10], ['2024', 26], ['2025', 23]];
const RENDA: [string, number][] = [['Até 1 salário mínimo', 93], ['1 a 3 salários mínimos', 19], ['3 a 5 salários mínimos', 7], ['Acima de 5 a 10 salários mínimos', 1]];
const TRABALHO: [string, number][] = [['Não', 90], ['Sim, estágio remunerado', 10], ['Sim, trabalho informal', 10], ['Sim, autônomo/informal', 5], ['Sim, CLT/Concurso', 2], ['Sim, trabalho formal (CLT)', 2]];
const SAUDE: [string | null, number][] = [[null, 38], ['Regular', 28], ['Boa', 24], ['Muito boa', 18], ['Ruim', 8], ['Muito ruim', 3], ['Prefiro não responder', 1]];
const ESTRESSE: [string | null, number][] = [[null, 38], ['Não', 35], ['Sim, ocasionalmente', 31], ['Sim, frequentemente', 11], ['Sim, a maior parte do tempo', 5]];
const ACOMP: [string | null, number][] = [['Nunca', 61], [null, 38], ['Sim, no passado', 12], ['Sim, atualmente', 9]];
const ASSIST: [string | null, number][] = [['Não', 78], ['Sim', 24], [null, 18]];
const COMPUTADOR: [string | null, number][] = [['Sim', 56], [null, 38], ['Não', 26]];
const INTERNET: [string, number][] = [['Sim', 100], ['Não', 13], ['Às vezes', 6], ['Prefiro não responder', 1]];
const QTD_PC: [string | null, number][] = [['1', 67], [null, 38], ['0', 7], ['2', 7], ['Acima de 3', 1]];
const GASTO: [string | null, number][] = [['Entre R$ 50,00 a R$ 150,00', 76], [null, 38], ['Entre R$ 150,00 a R$ 200,00', 4], ['Acima de R$ 200,00', 2]];
const MORADIA: [string, number][] = [['Própria', 69], ['Alugada', 42], ['Cedida', 7], ['Outra', 1]];
const DESLOC: [string, number][] = [['Bicicleta/A pé', 87], ['Carro/Moto próprio', 17], ['Transporte público (ônibus, trem, metrô, etc.)', 9], ['Carona/Fretado', 5], ['Transporte por aplicativo/táxi', 2]];
const GENERO: [string, number][] = [['Feminino', 60], ['Masculino', 40]];
const COR: [string, number][] = [['Parda', 70], ['Preta', 15], ['Branca', 12], ['Indígena', 3]];

export function gerarRegistros(semente = 20260912): Registro[] {
  const aleatorio = criarAleatorio(semente);
  const sortear = criarSorteio(aleatorio);
  const registros: Registro[] = [];
  let id = 1;
  for (let i = 0; i < 75; i++) {
    const codigoPolo = sortear(POLOS);
    const anoIngresso = sortear(TURMAS);
    // Matrícula no formato institucional: ano (4) + polo (4) + sequencial (4).
    const matricula = Number(`${anoIngresso}${codigoPolo}${String(i + 1).padStart(4, '0')}`);
    // Quais janelas o aluno respondeu: 13 têm as 3; o resto 1 ou 2.
    const janelas =
      i < 13 ? [0, 1, 2] : sortear<number[]>([[[2], 30], [[0, 1], 12], [[1, 2], 10], [[0], 6], [[1], 4]]);
    // Perfil "estável" do aluno: os campos socioeconômicos variam pouco entre períodos.
    const base = {
      genero: sortear(GENERO), cor_etnia: sortear(COR), renda: sortear(RENDA), trabalho: sortear(TRABALHO),
      tipo_moradia: sortear(MORADIA), deslocamento: sortear(DESLOC), computador_proprio: sortear(COMPUTADOR),
      acesso_internet: sortear(INTERNET), qtd_computador: sortear(QTD_PC), gasto_internet: sortear(GASTO),
      assistencia_estudantil: sortear(ASSIST),
    };
    const crgInicial = aleatorio() < 0.3 ? null : 3.5 + aleatorio() * 6;
    for (const j of janelas) {
      const semNota = crgInicial === null && j === 2;
      const crg = crgInicial === null ? null : Math.min(10, crgInicial + j * (aleatorio() * 1.8 - 0.4));
      registros.push({
        id: id++, ingestao_id: 1, matricula, periodo: PERIODOS_DEMO[j],
        CRG: semNota || crg === null ? null : Number(crg.toFixed(2)),
        nome: `Aluno ${String(i + 1).padStart(2, '0')}`, data_de_nascimento: null,
        // Nulos de propósito: a API do FasiTech não devolve nenhum dos dois,
        // e sem backend não há os derivados que a view calcularia -- o que
        // faz a demonstração exercitar a derivação local de reserva.
        primeiro_ano_eletivo: null, polo: null,
        turma: null, polo_cod: null, polo_nome: null,
        pcd: 'Não', tipo_deficiencia: null,
        saude_mental: sortear(SAUDE), estresse: sortear(ESTRESSE), acompanhamento: sortear(ACOMP),
        escolaridade_pai: null, escolaridade_mae: null, qtd_celular: '1', data_hora: null,
        ...base,
        // Eventual mudança de situação entre períodos.
        trabalho: aleatorio() < 0.15 ? sortear(TRABALHO) : base.trabalho,
      });
    }
  }
  return registros;
}

export const registrosDemonstracao: Registro[] = gerarRegistros();

/* ------------------------------------------------------------------ */
/* Trajetória acadêmica de demonstração (espelha crg_semestre)          */
/* ------------------------------------------------------------------ */

/** Semestres letivos que a base real cobre: 2020.2 a 2026.1. */
function semestresEntre(inicio: string, fim: string): string[] {
  const chave = (s: string) => Number(s.split('.')[0]) * 2 + Number(s.split('.')[1]);
  const lista: string[] = [];
  for (let ano = 2020; ano <= 2026; ano++) {
    for (const metade of [1, 2]) {
      const s = `${ano}.${metade}`;
      if (chave(s) >= chave(inicio) && chave(s) <= chave(fim)) lista.push(s);
    }
  }
  return lista;
}

/**
 * Um ponto por (aluno, semestre) desde o ingresso. Reproduz as duas coisas
 * que fazem a série real ser o que é: a nota passeia em vez de ser constante,
 * e os dois últimos semestres saem NÃO APURADOS (crg null, governança §4.6) --
 * é assim que a base real está, e é o caso que o gráfico tem que desenhar
 * como lacuna em vez de zero.
 */
export function gerarCrgSemestres(semente = 20260923): CrgSemestre[] {
  const aleatorio = criarAleatorio(semente);
  const pontos: CrgSemestre[] = [];
  const NAO_APURADOS = new Set(['2025.2', '2026.1']);
  for (const matricula of new Set(registrosDemonstracao.map((r) => r.matricula))) {
    const anoIngresso = String(matricula).slice(0, 4);
    let nota = 5.5 + aleatorio() * 3.5;
    for (const semestre of semestresEntre(`${anoIngresso}.1`, '2026.1')) {
      if (NAO_APURADOS.has(semestre)) {
        pontos.push({ matricula, semestre, crg: null });
        continue;
      }
      nota = Math.min(10, Math.max(0, nota + (aleatorio() * 1.6 - 0.7)));
      pontos.push({ matricula, semestre, crg: Number(nota.toFixed(2)) });
    }
  }
  return pontos;
}

export const crgSemestresDemonstracao: CrgSemestre[] = gerarCrgSemestres();

/* ------------------------------------------------------------------ */
/* Séries usadas pelos gráficos de "Análises" (Bidimensional,          */
/* Distribuição, Longitudinal) — mantidos do dashboard anterior.        */
/* ------------------------------------------------------------------ */

export const xAxisOptions = ['Cor/Etnia', 'Gênero', 'Renda', 'Trabalho', 'Polo'];
export const yAxisOptions = ['CRG'];
export const poloOptions = ['Todos', ...POLOS.map(([codigo]) => POLOS_POR_CODIGO[codigo])];
export const xLongitudinalOptions = ['2024-2027', '2020-2024'];
export const turmaOptions = TURMAS.map(([ano]) => ano);
export const alunoOptions = ['Todos'];

export const mockDataBidimensional = [
  { categoria: 'Parda', crg: 7.1 }, { categoria: 'Preta', crg: 6.8 },
  { categoria: 'Branca', crg: 7.4 }, { categoria: 'Indígena', crg: 6.2 },
];

export const mockDataDistribuicao = [2, 3, 4, 5, 6, 7, 8, 9, 10].map((faixa, i, arr) => {
  const centro = (arr.length - 1) / 2;
  const curva = Math.exp(-((i - centro) ** 2) / 6) * 20;
  return { categoria: `${faixa}`, frequencia: Math.round(curva + (i % 2) * 2), curva: Number(curva.toFixed(2)) };
});

export const mockDataLongitudinal = ['2024', '2025', '2026', '2027'].map((ano, i) => ({
  ano, turmaA: 6 + i * 0.8, turmaB: 7 + Math.sin(i) * 0.5, turmaC: 8 - (i === 3 ? 3 : i * 0.3), turmaD: 5 + (i % 2) * 2,
}));
