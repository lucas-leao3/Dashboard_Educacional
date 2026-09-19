import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Contexto } from '../hooks/DadosProvider';
import type { Dados } from '../hooks/DadosProvider';
import { registrosDemonstracao } from '../data/mockData';
import { consolidarAlunos, ordenarPeriodos } from '../domain/agregacao';
import Polos from './Polos';
import Turmas from './Turmas';
import Alunos from './Alunos';
import Perfil from './Perfil';
import PaginaDados from './Dados';

const alunos = consolidarAlunos(registrosDemonstracao);
const dados: Dados = {
  carregando: false, origem: 'demonstracao', registros: registrosDemonstracao,
  periodos: ordenarPeriodos(registrosDemonstracao.map((r) => r.periodo)),
  periodo: '', setPeriodo: () => {}, alunos, alunosTodos: alunos, lote: null, lotes: [], recarregar: async () => {},
};

/** HTML sem os marcadores <!-- --> que o SSR põe entre nós de texto. */
function renderComContexto(contexto: Dados, rota: string) {
  return renderToString(
    <Contexto.Provider value={contexto}>
      <MemoryRouter initialEntries={[rota]}>
        <Routes>
          <Route path="/" element={<Polos />} />
          <Route path="/polo/:polo" element={<Turmas />} />
          <Route path="/polo/:polo/turma/:turma" element={<Alunos />} />
          <Route path="/aluno/:matricula" element={<Perfil />} />
          <Route path="/dados" element={<PaginaDados />} />
        </Routes>
      </MemoryRouter>
    </Contexto.Provider>,
  ).replace(/<!-- -->/g, '');
}

function render(rota: string) {
  return renderComContexto(dados, rota);
}

const primeiro = alunos.find((a) => a.polo === 'Cameta' && a.registros.length >= 2)!;

describe('telas da hierarquia Polo → Turma → Aluno → Perfil', () => {
  test('Polos lista os três polos com n visível', () => {
    const html = render('/');
    for (const polo of ['Cameta', 'Oeiras', 'Limoeiro']) expect(html).toContain(polo);
    expect(html).toMatch(/n=\d+ alunos/);
    expect(html).toContain('Comparativo por Polo');
  });
  test('Turmas do polo mostra cards de turma com link para os alunos', () => {
    const html = render('/polo/Cameta');
    expect(html).toContain('Turmas do polo Cameta');
    expect(html).toContain(`/polo/Cameta/turma/${encodeURIComponent(primeiro.turma)}`);
  });
  test('Alunos da turma mostra as quatro dimensões e a legenda com "Sem dado"', () => {
    const html = render(`/polo/Cameta/turma/${encodeURIComponent(primeiro.turma)}`);
    for (const d of ['Acadêmica', 'Socioeconômica', 'Saúde Mental', 'Infraestrutura']) expect(html).toContain(d);
    expect(html).toContain('Sem dado');
    expect(html).not.toContain('Trabalho &amp; Renda');
    expect(html).not.toContain('Frequência');
  });
  test('Perfil apresenta as quatro dimensões e a trajetória', () => {
    const html = render(`/aluno/${primeiro.matricula}`);
    expect(html).toContain('Dados Acadêmicos');
    expect(html).toContain('Dados Socioeconômicos');
    expect(html).toContain('Dados de Saúde Mental');
    expect(html).toContain('Dados de Infraestrutura');
    expect(html).toContain('Trajetória longitudinal');
  });
  test('Perfil de matrícula inexistente não quebra', () => {
    expect(render('/aluno/999')).toContain('Aluno não encontrado');
  });
});

describe('selo do lote no AppShell', () => {
  const lote = {
    id: '2026-09-L01',
    executado_em: '2026-09-12T10:00:00Z',
    fechado_em: null,
    periodos_cobertos: ['2025.2', '2026.1'],
    executado_por: 'edinaldo',
    observacao: null,
    ingestoes: [{ id: 1, passo: 1, arquivo_sha256: null, executado_em: '2026-09-12T10:00:00Z', registros_lidos: 10, registros_aceitos: 9, registros_rejeitados: 1 }],
    excecoes_por_motivo: { sem_academico: 3, sem_socioeconomico: 2 },
  };

  test('aparece com id e contagem quando a origem é a API e há um lote', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lote }, '/');
    expect(html).toContain('Lote 2026-09-L01');
    expect(html).toContain('5 exceções');
  });

  test('não aparece sem lote, mesmo com origem API', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lote: null }, '/');
    expect(html).not.toContain('Lote 2026-09-L01');
  });

  test('não aparece em modo demonstração mesmo que um lote exista no contexto', () => {
    const html = renderComContexto({ ...dados, origem: 'demonstracao', lote }, '/');
    expect(html).not.toContain('Lote 2026-09-L01');
  });
});

const loteAberto = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: null, periodos_cobertos: ['2026.1'],
  executado_por: null, observacao: null, ingestoes: [], excecoes_por_motivo: {},
};
const ingestao = (passo: number) => ({ id: passo, passo, arquivo_sha256: null, executado_em: '2026-09-12T10:00:00Z', registros_lidos: 1, registros_aceitos: 1, registros_rejeitados: 0 });

describe('tela Dados', () => {
  test('sem API mostra o aviso e nenhum formulário', () => {
    const html = render('/dados');
    expect(html).toContain('A inserção de dados exige a API');
    expect(html).not.toContain('type="file"');
    expect(html).not.toContain('Abrir lote');
  });
  test('com API e nenhum lote começa no passo 1', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [] }, '/dados');
    expect(html).toContain('Abrir lote');
  });
  test('com API e um lote aberto sem ingestões, seleciona esse lote e mostra o passo 2', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [loteAberto], lote: loteAberto }, '/dados');
    expect(html).toContain('type="file"');
    expect(html).not.toContain('Cobertura do lote 2026-09-L01');
  });
  test('lote com passos 1 e 2 mostra o botão Fechar lote', () => {
    const rodado = { ...loteAberto, ingestoes: [ingestao(1), ingestao(2)] };
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [rodado], lote: rodado }, '/dados');
    expect(html).toContain('Fechar lote');
  });
  test('lote fechado mostra "Fechado em" e não mostra ação', () => {
    const fechado = { ...loteAberto, ingestoes: [ingestao(1), ingestao(2)], fechado_em: '2026-09-12T11:00:00Z' };
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [fechado], lote: fechado }, '/dados');
    expect(html).toContain('Fechado em');
    expect(html).not.toContain('Fechar lote');
  });
});
