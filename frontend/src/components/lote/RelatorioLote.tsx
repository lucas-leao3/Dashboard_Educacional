import type { ReactNode } from 'react';
import KpiCard from '../ui/KpiCard';
import { SEM_NOME, nomeExibido } from '../../domain/aluno';
import { textoCamposSemResposta, textoPercentual } from '../../domain/lote';
import type { LinhaIntegrada, LinhaNaoIntegrada, LinhaRelatorio, Lote, Relatorio } from '../../data/tipos';

interface Props {
  lote: Lote;
  /** null = ainda carregando. */
  relatorio: Relatorio | null;
  erro: string | null;
}

function formatarData(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('pt-BR');
}

interface Coluna<T> {
  titulo: string;
  valor: (linha: T) => ReactNode;
}

/** Identificação e fontes: as quatro primeiras colunas dos dois relatórios. */
const IDENTIFICACAO: Coluna<LinhaRelatorio>[] = [
  { titulo: 'Matrícula', valor: (l) => <span className="font-mono">{l.matricula ?? '—'}</span> },
  { titulo: 'Nome', valor: (l) => nomeExibido(l.nome) ?? <span className="text-slate-400">{SEM_NOME}</span> },
  { titulo: 'Acadêmico', valor: (l) => (l.academico ? 'Sim' : 'Não') },
  { titulo: 'Socioeconômico', valor: (l) => (l.socioeconomico ? 'Sim' : 'Não') },
];

/** Completude: as três últimas colunas dos dois relatórios. */
const COMPLETUDE: Coluna<LinhaRelatorio>[] = [
  { titulo: 'Sem resposta', valor: (l) => l.qtd_campos_sem_resposta },
  { titulo: 'Campos sem resposta', valor: (l) => textoCamposSemResposta(l.campos_sem_resposta) },
  { titulo: 'Preenchimento', valor: (l) => textoPercentual(l.percentual_preenchimento) },
];

const MOTIVO: Coluna<LinhaNaoIntegrada> = {
  titulo: 'Motivo',
  valor: (l) => (
    <>
      {l.motivo_descricao}
      {l.detalhe && <span className="block text-xs text-slate-400">{l.detalhe}</span>}
    </>
  ),
};

const STATUS: Coluna<LinhaIntegrada> = { titulo: 'Status', valor: (l) => l.status };

function Tabela<T extends LinhaRelatorio>({ id, titulo, descricao, linhas, situacao }: {
  id: string;
  titulo: string;
  descricao: string;
  linhas: T[];
  situacao: Coluna<T>;
}) {
  const colunas: Coluna<T>[] = [...IDENTIFICACAO, situacao, ...COMPLETUDE];
  return (
    <section className="rounded-2xl bg-white border border-slate-200/80" aria-labelledby={id}>
      <div className="p-5 pb-3">
        <h3 id={id} className="font-semibold text-slate-800">{titulo} ({linhas.length})</h3>
        <p className="text-xs text-slate-500 mt-1">{descricao}</p>
      </div>
      {linhas.length === 0 ? (
        <p className="px-5 pb-5 text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500 bg-slate-50">
              <tr>{colunas.map((c) => <th key={c.titulo} className="px-4 py-2 whitespace-nowrap">{c.titulo}</th>)}</tr>
            </thead>
            <tbody>
              {linhas.map((l, i) => (
                <tr key={`${l.matricula ?? 'sem-matricula'}-${i}`} className="border-t border-slate-100">
                  {colunas.map((c) => <td key={c.titulo} className="px-4 py-2 align-top">{c.valor(l)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** Relatórios de um lote: quem entrou nos dashboards e quem ficou de fora, e por quê. */
export default function RelatorioLote({ lote, relatorio, erro }: Props) {
  return (
    <section className="space-y-4" aria-labelledby="relatorio-titulo">
      <div>
        <h2 id="relatorio-titulo" className="text-base font-bold text-slate-800">Relatório do lote {lote.id}</h2>
        <p className="text-sm text-slate-500 mt-1">
          Responsável: {lote.executado_por ?? 'não informado'} · Período: {lote.periodos_cobertos.join(', ') || '—'} ·{' '}
          {lote.fechado_em ? `Fechado em ${formatarData(lote.fechado_em)}` : 'Aberto'}
        </p>
      </div>

      {erro && <p className="rounded-2xl bg-red-50 border border-red-200 p-5 text-sm text-red-700">Não foi possível carregar o relatório: {erro}</p>}
      {!erro && !relatorio && <p className="text-sm text-slate-500">Carregando…</p>}

      {relatorio && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard label="Alunos no lote" value={relatorio.resumo.total} />
            <KpiCard label="Integrados" value={relatorio.resumo.integrados} hint="entram nos dashboards" />
            <KpiCard
              label="Não integrados"
              value={relatorio.resumo.nao_integrados}
              tone={relatorio.resumo.nao_integrados ? 'atencao' : undefined}
              hint="fora de KPIs e gráficos"
            />
            <KpiCard label="Preenchimento médio" value={textoPercentual(relatorio.resumo.preenchimento_medio_integrados)} hint="dos integrados" />
          </div>

          <Tabela
            id="nao-integrados-titulo"
            titulo="Dados não integrados"
            descricao="Registros que não passaram pelo cruzamento acadêmico × socioeconômico. Não compõem KPIs, indicadores nem gráficos."
            linhas={relatorio.nao_integrados}
            situacao={MOTIVO}
          />
          <Tabela
            id="integrados-titulo"
            titulo="Dados integrados"
            descricao="Registros com dados acadêmicos e socioeconômicos vinculados pela matrícula. São a base dos dashboards."
            linhas={relatorio.integrados}
            situacao={STATUS}
          />
          <p className="text-xs text-slate-500">
            Completude: avalia os campos das fontes que o registro tem — o CRG (acadêmico) e as perguntas do questionário
            socioeconômico. Tipo de deficiência só conta para quem declarou deficiência; "Prefiro não responder" conta como resposta.
          </p>
        </>
      )}
    </section>
  );
}
