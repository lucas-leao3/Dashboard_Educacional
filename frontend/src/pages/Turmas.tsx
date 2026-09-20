import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import CardTurma from '../components/CardTurma';
import ComparativoGrupos from '../components/ComparativoGrupos';
import type { Grupo } from '../components/ComparativoGrupos';
import KpiCard from '../components/ui/KpiCard';
import { agregar, agregarPorTurma } from '../domain/agregacao';
import { useDados } from '../hooks/useDados';

/** Turmas do polo selecionado (doc de alinhamento, item 5). */
export default function Turmas() {
  const { polo = '' } = useParams();
  const nomePolo = decodeURIComponent(polo);
  const { alunos } = useDados();

  const doPolo = useMemo(() => alunos.filter((a) => a.polo === nomePolo), [alunos, nomePolo]);
  const turmas = useMemo(() => agregarPorTurma(alunos, nomePolo), [alunos, nomePolo]);
  const resumo = useMemo(() => agregar(doPolo), [doPolo]);

  const grupos: Grupo[] = turmas.map((t) => ({
    chave: t.turma,
    rotulo: `Turma ${t.turma}`,
    href: `/polo/${encodeURIComponent(t.polo)}/turma/${encodeURIComponent(t.turma)}`,
    agregado: t,
  }));

  return (
    <AppShell
      titulo={`Turmas do polo ${nomePolo}`}
      subtitulo="Turma = ano/semestre de ingresso (primeiro ano letivo). Selecione uma turma para ver apenas os alunos pertencentes a ela."
      migalhas={[{ rotulo: 'Polos', to: '/' }, { rotulo: nomePolo }]}
    >
      {!doPolo.length ? (
        <p className="text-sm text-slate-500">
          Nenhum aluno deste polo no filtro atual. <Link to="/" className="text-blue-700 font-semibold">Voltar aos polos</Link>.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard label="Turmas" value={turmas.length} />
            <KpiCard label="Alunos do polo" value={resumo.alunos} hint={resumo.nBaixo ? 'n baixo: leia com cautela' : `${resumo.registros} registros`} />
            <KpiCard label="CRG médio do polo" value={resumo.indicadores.crg_medio === null ? '—' : resumo.indicadores.crg_medio.toFixed(2)} />
            <KpiCard label="Sinalização crítica" value={resumo.porSinalizacao.critico} tone="critico" hint={`${resumo.porSinalizacao.atencao} em atenção`} />
          </div>

          <section aria-labelledby="titulo-turmas">
            <h2 id="titulo-turmas" className="text-lg font-bold text-slate-900 mb-3">Turmas</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {turmas.map((t) => <CardTurma key={t.turma} turma={t} />)}
            </div>
          </section>

          <ComparativoGrupos titulo="Comparativo entre turmas" grupos={grupos} />
        </>
      )}
    </AppShell>
  );
}
