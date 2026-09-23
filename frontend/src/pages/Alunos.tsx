import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import CardAluno from '../components/CardAluno';
import Trajetoria from '../components/Trajetoria';
import { textoVariacao } from '../domain/trajetoria';
import KpiCard from '../components/ui/KpiCard';
import LegendaSinalizacao from '../components/ui/LegendaSinalizacao';
import SelectDropdown from '../components/ui/SelectDropdown';
import type { DimensaoId, Sinalizacao } from '../data/tipos';
import { agregar } from '../domain/agregacao';
import type { Aluno } from '../domain/agregacao';
import IdentificacaoAluno from '../components/ui/IdentificacaoAluno';
import { ROTULO_SINALIZACAO, SINALIZACOES } from '../domain/classificacao';
import { DIMENSOES } from '../domain/dimensoes';
import { useDados } from '../hooks/useDados';
import { corDaEntidade } from '../theme/cores';

type Ordem = 'sinalizacao' | 'crg' | 'matricula';
const PESO: Record<Sinalizacao, number> = { critico: 0, atencao: 1, ok: 2, sem_dado: 3 };

function ordenar(lista: Aluno[], ordem: Ordem): Aluno[] {
  return [...lista].sort((a, b) => {
    if (ordem === 'sinalizacao') return PESO[a.sinalizacao] - PESO[b.sinalizacao] || a.matricula - b.matricula;
    if (ordem === 'crg') return (a.vigente.CRG ?? -1) - (b.vigente.CRG ?? -1) || a.matricula - b.matricula;
    return a.matricula - b.matricula;
  });
}

/** % de alunos cujo vigente tem alguma resposta socioeconômica. */
function cobertura(lista: Aluno[]): number {
  if (!lista.length) return 0;
  const com = lista.filter((a) => a.porDimensao.socioeconomica !== 'sem_dado' || a.porDimensao.saude_mental !== 'sem_dado' || a.porDimensao.infraestrutura !== 'sem_dado');
  return Math.round((com.length / lista.length) * 100);
}

/**
 * Alunos da turma selecionada: consolidação das duas maquetes do painel de
 * perfil (KPIs, filtros, grid de cards com 4 dimensões e legenda) mais a
 * trajetória individual por dimensão (doc, itens 5, 6 e 7).
 */
export default function Alunos() {
  const { polo = '', turma = '' } = useParams();
  const nomePolo = decodeURIComponent(polo);
  const nomeTurma = decodeURIComponent(turma);
  const { alunos, alunosTodos, crgSemestres } = useDados();
  const [sinal, setSinal] = useState<Sinalizacao | 'todas'>('todas');
  const [ordem, setOrdem] = useState<Ordem>('sinalizacao');
  const [dimensaoId, setDimensaoId] = useState<DimensaoId>('academica');

  const daTurma = useMemo(() => alunos.filter((a) => a.polo === nomePolo && a.turma === nomeTurma), [alunos, nomePolo, nomeTurma]);
  const resumo = useMemo(() => agregar(daTurma), [daTurma]);
  const visiveis = useMemo(() => ordenar(sinal === 'todas' ? daTurma : daTurma.filter((a) => a.sinalizacao === sinal), ordem), [daTurma, sinal, ordem]);
  const corPolo = corDaEntidade(nomePolo, [...new Set(alunosTodos.map((a) => a.polo))]);

  // Trajetória usa o histórico completo (sem filtro de período) dos alunos da turma.
  const comHistorico = useMemo(() => {
    const ids = new Set(daTurma.map((a) => a.matricula));
    return alunosTodos.filter((a) => ids.has(a.matricula) && a.registros.length >= 2);
  }, [daTurma, alunosTodos]);

  return (
    <AppShell
      titulo={`Turma ${nomeTurma} · ${nomePolo}`}
      subtitulo="1 cartão por aluno, com o registro mais recente do período filtrado. O perfil é o resultado das quatro dimensões, não uma quinta dimensão."
      migalhas={[{ rotulo: 'Polos', to: '/' }, { rotulo: nomePolo, to: `/polo/${polo}` }, { rotulo: `Turma ${nomeTurma}` }]}
    >
      {!daTurma.length ? (
        <p className="text-sm text-slate-500">
          Nenhum aluno desta turma no filtro atual. <Link to={`/polo/${polo}`} className="text-blue-700 font-semibold">Voltar às turmas</Link>.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
            <KpiCard label="Alunos da turma" value={resumo.alunos} hint={resumo.nBaixo ? 'n baixo' : undefined} />
            <KpiCard label="Registros (períodos)" value={resumo.registros} />
            <KpiCard label="CRG médio" value={resumo.indicadores.crg_medio === null ? '—' : resumo.indicadores.crg_medio.toFixed(2)} />
            <KpiCard label="Cobertura do formulário" value={`${cobertura(daTurma)}%`} />
            <KpiCard label="Sinalização crítica" value={resumo.porSinalizacao.critico} tone="critico" />
            <KpiCard label="Em atenção" value={resumo.porSinalizacao.atencao} tone="atencao" />
          </div>

          <section aria-labelledby="titulo-alunos" className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 id="titulo-alunos" className="text-lg font-bold text-slate-900">Perfil multidimensional dos alunos</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  {DIMENSOES.map((d) => d.rotulo).join(' · ')}. Listras cinzas = dado não coletado, não um valor bom.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SelectDropdown
                  label="Sinalização"
                  value={sinal}
                  onChange={setSinal}
                  options={[{ value: 'todas' as const, label: 'Todas' }, ...SINALIZACOES.map((s) => ({ value: s, label: ROTULO_SINALIZACAO[s] }))]}
                />
                <SelectDropdown
                  label="Ordenar"
                  value={ordem}
                  onChange={setOrdem}
                  options={[{ value: 'sinalizacao' as const, label: 'sinalização' }, { value: 'crg' as const, label: 'CRG (menor primeiro)' }, { value: 'matricula' as const, label: 'matrícula' }]}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <LegendaSinalizacao />
              <p className="text-xs text-slate-500" aria-live="polite">{visiveis.length} de {daTurma.length} alunos</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
              {visiveis.map((a) => <CardAluno key={a.matricula} aluno={a} corPolo={corPolo} />)}
            </div>
          </section>

          <section aria-labelledby="titulo-trajetoria" className="rounded-[1.5rem] bg-white border border-slate-200/80 p-6 shadow-[0_4px_20px_rgba(15,23,42,0.03)] space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 id="titulo-trajetoria" className="text-lg font-bold text-slate-900">Trajetória individual</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Só alunos com 2 ou mais períodos ({comHistorico.length} de {daTurma.length}). Passe o mouse sobre os pontos para o valor exato.
                </p>
              </div>
              <SelectDropdown label="Dimensão" value={dimensaoId} onChange={setDimensaoId} options={DIMENSOES.map((d) => ({ value: d.id, label: d.rotulo }))} />
            </div>
            {!comHistorico.length ? (
              <p className="text-sm text-slate-500">Nenhum aluno desta turma tem mais de um período registrado.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {comHistorico.map((a) => (
                  <Link key={a.matricula} to={`/aluno/${a.matricula}`} className="block rounded-xl border border-slate-100 p-3 hover:border-blue-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    <IdentificacaoAluno nome={a.vigente.nome} matricula={a.matricula} compacto />
                    <p className="text-[11px] text-slate-500">{textoVariacao(a, dimensaoId, crgSemestres)}</p>
                    <Trajetoria aluno={a} dimensaoId={dimensaoId} compacto />
                  </Link>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </AppShell>
  );
}
