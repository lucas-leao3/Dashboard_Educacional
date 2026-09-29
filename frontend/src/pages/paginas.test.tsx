import { describe, expect, test } from 'vitest';
import { renderToString } from 'react-dom/server';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Contexto } from '../hooks/DadosProvider';
import type { Dados } from '../hooks/DadosProvider';
import { crgSemestresDemonstracao, registrosDemonstracao } from '../data/mockData';
import { consolidarAlunos, ordenarPeriodos } from '../domain/agregacao';
import { registro } from '../test/fixtures';
import Polos from './Polos';
import Turmas from './Turmas';
import Alunos from './Alunos';
import Perfil from './Perfil';
import PaginaDados from './Dados';
import Analises from './Analises';
import IaChat from './IaChat';

const alunos = consolidarAlunos(registrosDemonstracao);
const dados: Dados = {
  carregando: false, origem: 'demonstracao', registros: registrosDemonstracao,
  periodos: ordenarPeriodos(registrosDemonstracao.map((r) => r.periodo)),
  periodo: '', setPeriodo: () => {}, alunos, alunosTodos: alunos, crgSemestres: crgSemestresDemonstracao,
  lote: null, lotes: [], recarregar: async () => {},
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
          <Route path="/analises/bidimensional" element={<Analises tipo="bidimensional" />} />
          <Route path="/analises/distribuicao" element={<Analises tipo="distribuicao" />} />
          <Route path="/analises/longitudinal" element={<Analises tipo="longitudinal" />} />
          <Route path="/ia-chat" element={<IaChat />} />
        </Routes>
      </MemoryRouter>
    </Contexto.Provider>,
  ).replace(/<!-- -->/g, '');
}

function render(rota: string) {
  return renderComContexto(dados, rota);
}

const primeiro = alunos.find((a) => a.polo === 'Cametá' && a.registros.length >= 2)!;

describe('telas da hierarquia Polo → Turma → Aluno → Perfil', () => {
  test('Polos lista os três polos com n visível', () => {
    const html = render('/');
    for (const polo of ['Cametá', 'Oeiras', 'Limoeiro']) expect(html).toContain(polo);
    expect(html).toMatch(/n=\d+ alunos/);
    expect(html).toContain('Comparativo por Polo');
  });
  test('Turmas do polo mostra cards de turma com link para os alunos', () => {
    const html = render(`/polo/${encodeURIComponent(primeiro.polo)}`);
    expect(html).toContain(`Turmas do polo ${primeiro.polo}`);
    expect(html).toContain(`/polo/${encodeURIComponent(primeiro.polo)}/turma/${encodeURIComponent(primeiro.turma)}`);
  });
  test('Alunos da turma mostra as quatro dimensões e a legenda com "Sem dado"', () => {
    const html = render(`/polo/${encodeURIComponent(primeiro.polo)}/turma/${encodeURIComponent(primeiro.turma)}`);
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

  test('aparece com id e período extraído quando a origem é a API e há um lote', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lote }, '/');
    expect(html).toContain('Lote 2026-09-L01');
    expect(html).toContain('período 2025.2, 2026.1');
    expect(html).toContain('só com alunos integrados');
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

const loteFechado = {
  id: '2026-09-L01', executado_em: '2026-09-12T10:00:00Z', fechado_em: '2026-09-12T11:00:00Z', periodos_cobertos: ['2025.2'],
  executado_por: 'Edinaldo', observacao: null, ingestoes: [], excecoes_por_motivo: {},
};

describe('tela Dados', () => {
  test('sem API mostra o aviso e nenhum formulário', () => {
    const html = render('/dados');
    expect(html).toContain('A importação de dados exige a API');
    expect(html).not.toContain('type="file"');
  });
  test('com API e nenhum lote: só o formulário de importação, sem relatório', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [] }, '/dados');
    expect(html).toContain('Importar históricos');
    expect(html).toContain('Responsável pela importação');
    expect(html).not.toContain('Relatório do lote');
  });
  test('com lotes: formulário sempre disponível e relatório do mais recente selecionado', () => {
    const anterior = { ...loteFechado, id: '2026-08-L01' };
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [anterior, loteFechado], lote: loteFechado }, '/dados');
    expect(html).toContain('Importar históricos');
    expect(html).toContain('Relatório do lote 2026-09-L01');
    expect(html).toContain('2026-08-L01 · 2025.2');
  });
  test('o fluxo antigo (abrir, enviar, fechar) sumiu da tela', () => {
    const html = renderComContexto({ ...dados, origem: 'api', lotes: [loteFechado], lote: loteFechado }, '/dados');
    for (const antigo of ['Abrir lote', 'Fechar lote', 'Períodos cobertos', 'Enviar e rodar']) expect(html).not.toContain(antigo);
  });
});

describe('telas de Análises (nenhuma delas pode voltar a usar número fixo)', () => {
  test('Bidimensional tira as categorias dos dados, não de uma lista fixa', () => {
    // Contexto com categorias que NÃO existem no dataset de demonstração: se a
    // tela ainda lesse uma lista fixa, nenhuma delas apareceria.
    const registros = [
      registro({ id: 1, matricula: 202016040001, CRG: 8, cor_etnia: 'Quilombola' }),
      registro({ id: 2, matricula: 202016040002, CRG: 6, cor_etnia: 'Amarelo' }),
    ];
    const alunosProprios = consolidarAlunos(registros);
    const html = renderComContexto(
      { ...dados, registros, alunos: alunosProprios, alunosTodos: alunosProprios, crgSemestres: [] },
      '/analises/bidimensional',
    );
    expect(html).toContain('Quilombola');
    expect(html).toContain('Amarelo');
    expect(html).toContain('n por categoria');
    expect(html).not.toContain('Indígena');   // estava fixo no código antigo
  });

  test('Bidimensional avisa quando ninguém do filtro tem nota', () => {
    const registros = [registro({ id: 1, matricula: 202016040001, CRG: null, cor_etnia: 'Pardo' })];
    const semNota = consolidarAlunos(registros);
    const html = renderComContexto(
      { ...dados, registros, alunos: semNota, alunosTodos: semNota, crgSemestres: [] },
      '/analises/bidimensional',
    );
    expect(html).toContain('Nenhum aluno do filtro tem CRG apurado');
  });

  test('Distribuição declara o n e não promete curva ajustada', () => {
    const html = render('/analises/distribuicao');
    expect(html).toContain('Distribuição');
    expect(html).toMatch(/n = \d+/);
    expect(html).toContain('com CRG apurado');
  });

  test('Longitudinal anuncia séries sobre semestres e avisa o não apurado', () => {
    const html = render('/analises/longitudinal');
    expect(html).toContain('Análise Longitudinal');
    expect(html).toMatch(/sobre \d+ semestre\(s\)/);
    // A demonstração reproduz 2025.2 e 2026.1 sem apuração, como a base real.
    expect(html).toContain('Sem apuração (lacuna na linha)');
  });

  test('os KPIs do topo saem dos mesmos alunos que os gráficos', () => {
    const html = render('/analises/bidimensional');
    expect(html).toContain(String(alunos.length));   // Matrículas Únicas
  });

  test('Bidimensional abre com a dimensão e o polo da URL', () => {
    const html = render('/analises/bidimensional?dimensao=renda&polo=Camet%C3%A1');
    expect(html).toMatch(/<option value="renda" selected="">/);
    expect(html).toMatch(/<option value="Cametá" selected="">/);
  });
  test('Distribuição e Longitudinal abrem com o polo da URL', () => {
    expect(render('/analises/distribuicao?polo=Oeiras')).toMatch(/<option value="Oeiras" selected="">/);
    expect(render('/analises/longitudinal?polo=Oeiras')).toMatch(/<option value="Oeiras" selected="">/);
  });
});

describe('identificação do aluno é a mesma em toda tela', () => {
  /* Metade da base não tem nome (ele vem do PDF do histórico, não do
     FasiTech), e cada tela resolvia isso por conta própria -- a grade saía
     meio com nome, meio com número. */
  const registros = [
    registro({ id: 1, matricula: 202016040011, periodo: '2024.(1 e 2)', CRG: 8, nome: 'NALBERTH DE LEAO CASTRO' }),
    registro({ id: 2, matricula: 202016040011, periodo: '2025.(3 e 4)', CRG: 8, nome: 'NALBERTH DE LEAO CASTRO' }),
    registro({ id: 3, matricula: 202016040022, periodo: '2024.(1 e 2)', CRG: 6, nome: null }),
    registro({ id: 4, matricula: 202016040022, periodo: '2025.(3 e 4)', CRG: 6, nome: null }),
  ];
  const proprios = consolidarAlunos(registros);
  const contexto = { ...dados, registros, alunos: proprios, alunosTodos: proprios, crgSemestres: [] };

  test('card do aluno: nome e matrícula em linhas próprias, nas duas situações', () => {
    const html = renderComContexto(contexto, '/polo/Cametá/turma/2020');
    // Empilhados: a matrícula tem elemento próprio e não pode ser cortada
    // pelo truncate do nome (era o "Andrey Azevedo do Carmo · 20…").
    expect(html).toContain('>Nalberth de Leao Castro<');
    expect(html).toContain('>202016040011<');
    expect(html).toContain('>202016040022<');   // quem não tem nome
    expect(html).toContain('>—<');
    expect(html).not.toContain('NALBERTH DE LEAO CASTRO');   // caixa alta não chega à tela
    expect(html).not.toContain('Matrícula 202016040011');    // o rótulo antigo sumiu
  });

  test('card: a matrícula nunca fica dentro do elemento que trunca', () => {
    const html = renderComContexto(contexto, '/polo/Cametá/turma/2020');
    const truncados = [...html.matchAll(/class="[^"]*truncate[^"]*"[^>]*>([^<]*)</g)].map((m) => m[1]);
    expect(truncados.some((t) => t.includes('202016040011'))).toBe(false);
  });

  test('perfil: nome no título e matrícula no subtítulo, que não trunca', () => {
    const html = renderComContexto(contexto, '/aluno/202016040011');
    expect(html).toContain('>Nalberth de Leao Castro<');
    expect(html).toContain('Matrícula 202016040011 ·');
  });

  test('perfil de quem não tem nome ainda mostra a matrícula', () => {
    const html = renderComContexto(contexto, '/aluno/202016040022');
    expect(html).toContain('Matrícula 202016040022 ·');
    expect(html).toContain('>—<');
  });
});

describe('busca do cabeçalho', () => {
  test('a caixa aceita nome, não só matrícula', () => {
    const html = render('/');
    // O rótulo e o placeholder antigos diziam só "matrícula", e o
    // inputMode numérico abria teclado numérico no celular.
    expect(html).toContain('Buscar aluno por nome ou matrícula');
    expect(html).toContain('Buscar nome ou matrícula…');
    expect(html).not.toContain('inputmode="numeric"');
    expect(html).not.toContain('Ir para matrícula…');
  });
});

describe('assistente de consultas', () => {
  test('IA Chat avisa que precisa da API em modo demonstração', () => {
    expect(render('/ia-chat')).toContain('modo demonstração');
  });
  test('tela aberta pelo assistente mostra o que foi aplicado', () => {
    const html = renderToString(
      <Contexto.Provider value={dados}>
        <MemoryRouter initialEntries={[{ pathname: '/', state: { assistente: {
          consulta_interpretada: 'Contagem de alunos por Polo', filtros_aplicados: [{ rotulo: 'Período', valor: '2025.(3 e 4)' }],
          fontes: ['aluno_integrado'], forma: 'dashboard' } } }]}>
          <Routes><Route path="/" element={<Polos />} /></Routes>
        </MemoryRouter>
      </Contexto.Provider>,
    ).replace(/<!-- -->/g, '');
    expect(html).toContain('Aberto pelo assistente');
    expect(html).toContain('Período: 2025.(3 e 4)');
  });
});
