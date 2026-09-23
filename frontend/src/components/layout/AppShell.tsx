import { useMemo, useState } from 'react';
import type { FocusEvent, FormEvent, ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Sidebar from '../Sidebar';
import SeloLote from '../SeloLote';
import IdentificacaoAluno from '../ui/IdentificacaoAluno';
import SelectDropdown from '../ui/SelectDropdown';
import { buscarAlunos } from '../../domain/busca';
import { TODOS_PERIODOS, useDados } from '../../hooks/useDados';

export interface Migalha {
  rotulo: string;
  to?: string;
}

interface Props {
  titulo: string;
  subtitulo?: string;
  migalhas?: Migalha[];
  /** Esconde a barra de filtros globais (usado nas Análises). */
  semFiltros?: boolean;
  children: ReactNode;
}

const IconMenu = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);

const IconBusca = () => (
  <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.5" y2="16.5" />
  </svg>
);

/**
 * Moldura comum das telas: sidebar, cabeçalho com breadcrumb da hierarquia
 * Polo → Turma → Aluno e a barra de filtros globais (período + busca direta
 * por nome ou matrícula, complementar à navegação — doc, itens 3 e 9).
 */
export default function AppShell({ titulo, subtitulo, migalhas = [], semFiltros = false, children }: Props) {
  const [menuAberto, setMenuAberto] = useState(false);
  const [busca, setBusca] = useState('');
  const [listaAberta, setListaAberta] = useState(false);
  const { periodos, periodo, setPeriodo, origem, carregando, alunosTodos, registros, lote } = useDados();
  const navigate = useNavigate();

  // Busca por TRECHO do nome ou da matrícula (ver domain/busca.ts). Como um
  // termo casa com vários alunos, a caixa lista os resultados em vez de pular
  // para um deles -- escolher o primeiro calado esconderia os outros.
  const resultados = useMemo(() => buscarAlunos(alunosTodos, busca), [alunosTodos, busca]);
  const semResultado = busca.trim().length > 0 && resultados.length === 0;

  function irPara(matricula: number) {
    setBusca('');
    setListaAberta(false);
    navigate(`/aluno/${matricula}`);
  }

  /** Enter vai para o primeiro resultado -- o mais relevante pela ordem da busca. */
  function aoSubmeter(e: FormEvent) {
    e.preventDefault();
    if (resultados.length) irPara(resultados[0].matricula);
  }

  /** Fecha só quando o foco sai do conjunto caixa+lista, não a cada clique interno. */
  function aoSairDoFoco(e: FocusEvent<HTMLDivElement>) {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setListaAberta(false);
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans">
      {menuAberto && (
        <button type="button" className="fixed inset-0 z-20 bg-slate-900/30 md:hidden" aria-label="Fechar menu" onClick={() => setMenuAberto(false)} />
      )}
      <Sidebar aberto={menuAberto} onFechar={() => setMenuAberto(false)} />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-slate-200/80">
          <div className="px-4 sm:px-8 py-4 flex items-start gap-3">
            <button
              type="button"
              className="md:hidden mt-1 p-2 rounded-lg text-slate-600 hover:bg-slate-100"
              aria-label="Abrir menu"
              aria-expanded={menuAberto}
              onClick={() => setMenuAberto(true)}
            >
              <IconMenu />
            </button>
            <div className="min-w-0 flex-1">
              <nav aria-label="Localização" className="text-xs text-slate-400 flex flex-wrap items-center gap-1">
                <Link to="/" className="hover:text-blue-700">PainelAcadêmico</Link>
                {migalhas.map((m, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <span aria-hidden="true">/</span>
                    {m.to ? <Link to={m.to} className="hover:text-blue-700">{m.rotulo}</Link> : <span className="text-slate-600 font-medium">{m.rotulo}</span>}
                  </span>
                ))}
              </nav>
              <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight mt-0.5 truncate">{titulo}</h1>
              {subtitulo && <p className="text-sm text-slate-500 mt-0.5">{subtitulo}</p>}
            </div>
            {origem === 'demonstracao' && !carregando && (
              <span className="hidden sm:inline-flex shrink-0 text-[10px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-1" title="A API não respondeu; os dados exibidos são sintéticos.">
                Dados de demonstração
              </span>
            )}
            {origem === 'api' && lote && <SeloLote lote={lote} />}
          </div>

          {!semFiltros && (
            <div className="px-4 sm:px-8 pb-4 flex flex-wrap items-center gap-3">
              <SelectDropdown
                label="Período"
                value={periodo}
                onChange={setPeriodo}
                options={[{ value: TODOS_PERIODOS, label: 'Todos' }, ...periodos.map((p) => ({ value: p, label: p }))]}
              />
              <div className="relative" onBlur={aoSairDoFoco}>
                <form onSubmit={aoSubmeter} className="relative flex items-center" role="search">
                  <label htmlFor="busca-aluno" className="sr-only">Buscar aluno por nome ou matrícula</label>
                  <span className="absolute left-3.5 pointer-events-none"><IconBusca /></span>
                  <input
                    id="busca-aluno"
                    type="search"
                    autoComplete="off"
                    value={busca}
                    onChange={(e) => { setBusca(e.target.value); setListaAberta(true); }}
                    onFocus={() => setListaAberta(true)}
                    onKeyDown={(e) => { if (e.key === 'Escape') { setBusca(''); setListaAberta(false); } }}
                    placeholder="Buscar nome ou matrícula…"
                    aria-describedby="busca-resumo"
                    className="bg-white border border-slate-200 text-slate-700 text-xs font-medium rounded-full pl-9 pr-4 py-2 w-56 focus:outline-none focus:ring-2 focus:ring-blue-400/50"
                  />
                </form>

                <p id="busca-resumo" className="sr-only" aria-live="polite">
                  {busca.trim() ? `${resultados.length} aluno(s) encontrado(s)` : ''}
                </p>

                {listaAberta && busca.trim() && (
                  <div className="absolute z-30 mt-1 w-72 max-w-[85vw] rounded-2xl bg-white border border-slate-200 shadow-lg overflow-hidden">
                    {semResultado ? (
                      <p className="px-4 py-3 text-xs text-slate-500">Nenhum aluno com esse nome ou matrícula.</p>
                    ) : (
                      <ul>
                        {resultados.map((a) => (
                          <li key={a.matricula}>
                            <button
                              type="button"
                              onClick={() => irPara(a.matricula)}
                              className="group w-full text-left px-4 py-2 hover:bg-blue-50 focus:outline-none focus-visible:bg-blue-50"
                            >
                              <IdentificacaoAluno nome={a.vigente.nome} matricula={a.matricula} compacto />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </header>

        <main className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 space-y-6">
          {!carregando && origem === 'api' && registros.length === 0 && (
            <p className="text-sm text-slate-700 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3" role="status">
              A API respondeu, mas ainda não há registros no banco. Abra um lote e execute os passos de ingestão
              (<code>POST /lotes</code>, <code>/alunos/sincronizar</code>, <code>/alunos/atualizar-crg</code>) — ver <code>API_README.md</code>.
            </p>
          )}
          {carregando ? <p className="text-sm text-slate-500" aria-live="polite">Carregando dados…</p> : children}
        </main>
      </div>
    </div>
  );
}
