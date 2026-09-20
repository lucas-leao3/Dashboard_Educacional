import { useMemo } from 'react';
import AppShell from '../components/layout/AppShell';
import ComparativoGrupos from '../components/ComparativoGrupos';
import type { Grupo } from '../components/ComparativoGrupos';
import KpiCard from '../components/ui/KpiCard';
import LegendaSinalizacao from '../components/ui/LegendaSinalizacao';
import { agregar, agregarPorPolo } from '../domain/agregacao';
import { useDados } from '../hooks/useDados';
import { corDaEntidade } from '../theme/cores';

/** Tela inicial: Visão Geral dos Polos (doc de alinhamento, itens 3 e 4). */
export default function Polos() {
  const { alunos, periodos, periodo } = useDados();
  const porPolo = useMemo(() => agregarPorPolo(alunos), [alunos]);
  const geral = useMemo(() => agregar(alunos), [alunos]);
  const nomes = porPolo.map((p) => p.polo);

  const grupos: Grupo[] = porPolo.map((p) => ({
    chave: p.polo,
    rotulo: p.polo,
    cor: corDaEntidade(p.polo, nomes),
    href: `/polo/${encodeURIComponent(p.polo)}`,
    agregado: p,
  }));

  return (
    <AppShell
      titulo="Visão Geral dos Polos"
      subtitulo="Selecione um polo para ver suas turmas. Compare polos pelo indicador desejado; o tamanho da amostra (n) fica sempre visível."
      migalhas={[{ rotulo: 'Polos' }]}
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Polos" value={porPolo.length} />
        <KpiCard label="Alunos únicos" value={geral.alunos} hint={periodo ? `respondentes em ${periodo}` : 'em todos os períodos'} />
        <KpiCard label="Registros (períodos)" value={geral.registros} hint={`${periodos.length} janela(s) de coleta`} />
        <KpiCard label="Sinalização crítica" value={geral.porSinalizacao.critico} tone="critico" hint={`${geral.porSinalizacao.atencao} em atenção`} />
      </div>

      <ComparativoGrupos
        titulo="Comparativo por Polo"
        descricao="Ranking pelo indicador selecionado. Sem coordenadas geográficas na base, um mapa seria decorativo: este comparativo mostra o mesmo índice com o n sempre visível."
        grupos={grupos}
      />

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
        <LegendaSinalizacao />
        <p>Critério de sinalização provisório — a regra matemática será definida como etapa metodológica do projeto.</p>
      </div>
    </AppShell>
  );
}
