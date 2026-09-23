import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import BarrasDimensao from '../components/BarrasDimensao';
import Trajetoria from '../components/Trajetoria';
import { textoVariacao } from '../domain/trajetoria';
import KpiCard from '../components/ui/KpiCard';
import SelectDropdown from '../components/ui/SelectDropdown';
import SinalizacaoBadge from '../components/ui/SinalizacaoBadge';
import type { DimensaoId } from '../data/tipos';
import { SEM_NOME, nomeExibido } from '../domain/aluno';
import { pontuarDimensao } from '../domain/classificacao';
import { DIMENSOES } from '../domain/dimensoes';
import { useDados } from '../hooks/useDados';
import { COR_SINALIZACAO } from '../theme/cores';

/**
 * Perfil individual: etapa final da navegação (doc, item 6). Apresenta as
 * quatro dimensões com os dados do registro vigente e a trajetória por
 * dimensão ao longo dos períodos (item 7).
 */
export default function Perfil() {
  const { matricula = '' } = useParams();
  const { alunos, alunosTodos, periodo, crgSemestres } = useDados();
  const [dimensaoId, setDimensaoId] = useState<DimensaoId>('academica');

  // Com filtro de período, o vigente é o registro daquele período; se o aluno
  // não respondeu nele, mostramos o histórico completo e avisamos.
  const filtrado = useMemo(() => alunos.find((a) => String(a.matricula) === matricula), [alunos, matricula]);
  const completo = useMemo(() => alunosTodos.find((a) => String(a.matricula) === matricula), [alunosTodos, matricula]);
  const aluno = filtrado ?? completo;

  if (!aluno) {
    return (
      <AppShell titulo="Aluno não encontrado" migalhas={[{ rotulo: 'Polos', to: '/' }, { rotulo: `Matrícula ${matricula}` }]}>
        <p className="text-sm text-slate-500">Não há registros para a matrícula {matricula}. <Link to="/" className="text-blue-700 font-semibold">Voltar aos polos</Link>.</p>
      </AppShell>
    );
  }

  const { vigente } = aluno;
  const rotuloTurma = `Turma ${aluno.turma}`;
  const hrefTurma = `/polo/${encodeURIComponent(aluno.polo)}/turma/${encodeURIComponent(aluno.turma)}`;

  return (
    <AppShell
      /* O <h1> do AppShell trunca: o nome fica nele (pode cortar sem perda) e a
         matrícula abre o subtítulo, onde há largura e ela nunca some. */
      titulo={nomeExibido(vigente.nome) ?? SEM_NOME}
      subtitulo={`Matrícula ${aluno.matricula} · ${aluno.polo} · ${rotuloTurma} · registro vigente: ${vigente.periodo}`}
      migalhas={[
        { rotulo: 'Polos', to: '/' },
        { rotulo: aluno.polo, to: `/polo/${encodeURIComponent(aluno.polo)}` },
        { rotulo: rotuloTurma, to: hrefTurma },
        { rotulo: 'Perfil' },
      ]}
    >
      {periodo && !filtrado && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-4 py-2" role="status">
          Este aluno não tem registro em {periodo}; exibindo o registro mais recente disponível.
        </p>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl bg-white border border-slate-200/80 px-5 py-4 shadow-[0_4px_20px_rgba(15,23,42,0.03)]">
          <p className="text-xs font-medium text-slate-500">Perfil (resultado das 4 dimensões)</p>
          <div className="mt-2"><SinalizacaoBadge valor={aluno.sinalizacao} tamanho="md" /></div>
        </div>
        <KpiCard label="CRG vigente" value={vigente.CRG === null ? 'sem nota' : vigente.CRG.toFixed(2)} />
        <KpiCard label="Períodos registrados" value={aluno.registros.length} hint={aluno.registros.map((r) => r.periodo).join(', ')} />
        <div className="rounded-2xl bg-white border border-slate-200/80 px-5 py-4 shadow-[0_4px_20px_rgba(15,23,42,0.03)] col-span-2 lg:col-span-1">
          <p className="text-xs font-medium text-slate-500">Fatores de alerta</p>
          <p className="mt-2 text-sm text-slate-700 leading-snug">{aluno.fatores.length ? aluno.fatores.join(' · ') : 'nenhum'}</p>
        </div>
      </div>

      <section aria-labelledby="titulo-dimensoes" className="space-y-3">
        <h2 id="titulo-dimensoes" className="text-lg font-bold text-slate-900">As quatro dimensões</h2>
        <div className="rounded-2xl bg-white border border-slate-200/80 p-5 shadow-[0_4px_20px_rgba(15,23,42,0.03)] max-w-xl">
          <BarrasDimensao porDimensao={aluno.porDimensao} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {DIMENSOES.map((d) => {
            const s = aluno.porDimensao[d.id];
            const indice = pontuarDimensao(d.id, vigente);
            return (
              <article key={d.id} className="rounded-2xl bg-white border border-slate-200/80 p-5 shadow-[0_4px_20px_rgba(15,23,42,0.03)]" style={{ borderTopColor: COR_SINALIZACAO[s].hex, borderTopWidth: 3 }}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-bold text-slate-900">{d.rotulo}</h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">{d.descricao}</p>
                  </div>
                  <SinalizacaoBadge valor={s} />
                </div>
                <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
                  {d.campos.map(({ campo, rotulo }) => {
                    const v = vigente[campo];
                    return (
                      <div key={campo} className="contents">
                        <dt className="text-slate-500">{rotulo}</dt>
                        <dd className={`font-medium ${v === null || v === '' ? 'text-slate-400 italic' : 'text-slate-800'}`}>
                          {v === null || v === '' ? 'não informado' : typeof v === 'number' ? v.toFixed(2) : String(v)}
                        </dd>
                      </div>
                    );
                  })}
                  <dt className="text-slate-500 pt-1.5 border-t border-slate-100">{d.escala.rotulo}</dt>
                  <dd className="font-semibold text-slate-800 pt-1.5 border-t border-slate-100">{indice === null ? '—' : d.id === 'academica' ? indice.toFixed(2) : `${indice} / ${d.escala.max}`}</dd>
                </dl>
              </article>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="titulo-trajetoria" className="rounded-[1.5rem] bg-white border border-slate-200/80 p-6 shadow-[0_4px_20px_rgba(15,23,42,0.03)] space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="titulo-trajetoria" className="text-lg font-bold text-slate-900">Trajetória longitudinal</h2>
            <p className="text-xs text-slate-500 mt-0.5">Evolução por período usando o histórico do aluno · {textoVariacao(aluno, dimensaoId, crgSemestres)}.</p>
          </div>
          <SelectDropdown label="Dimensão" value={dimensaoId} onChange={setDimensaoId} options={DIMENSOES.map((d) => ({ value: d.id, label: d.rotulo }))} />
        </div>
        {aluno.registros.length < 2 ? (
          <p className="text-sm text-slate-500">Só há um período registrado; a trajetória precisa de pelo menos dois.</p>
        ) : (
          <Trajetoria aluno={completo ?? aluno} dimensaoId={dimensaoId} />
        )}
      </section>

      <p className="text-xs text-slate-500">Critério de sinalização provisório — a regra matemática será definida como etapa metodológica do projeto.</p>
    </AppShell>
  );
}
