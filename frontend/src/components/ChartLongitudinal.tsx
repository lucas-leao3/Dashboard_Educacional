import { useMemo, useState } from 'react';
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import SelectDropdown from './ui/SelectDropdown';
import BotaoIA from './ui/BotaoIA';
import { serieLongitudinal } from '../domain/analises';
import { identificacao } from '../domain/aluno';
import { useDados } from '../hooks/useDados';
import { useFiltroUrl } from '../hooks/useFiltroUrl';
import { TODOS } from '../domain/filtros';
import { COR_PRIMARIA, corDaTurma } from '../theme/cores';

/**
 * CRG médio por SEMESTRE LETIVO, com os dados de `crg_semestre`.
 *
 * O eixo é o semestre, não o período de coleta: o CRG gravado em `usuarios` é
 * o do último semestre apurado, repetido em todos os períodos do aluno -- uma
 * série sobre ele seria uma reta por construção.
 *
 * Semestre sem apuração vira lacuna (`connectNulls={false}`), nunca zero. Na
 * base real 2025.2 e 2026.1 têm 56 alunos e nenhuma nota: desenhados como
 * zero, fariam todas as linhas despencarem no fim.
 */
export default function ChartLongitudinal() {
  const { alunos, crgSemestres } = useDados();
  const [polo, setPolo] = useFiltroUrl('polo', TODOS);
  const [turma, setTurma] = useFiltroUrl('turma', TODOS);
  const [matricula, setMatricula] = useState(TODOS);

  const polos = useMemo(() => [TODOS, ...new Set(alunos.map((a) => a.polo))].sort(), [alunos]);

  const doPolo = useMemo(
    () => (polo === TODOS ? alunos : alunos.filter((a) => a.polo === polo)),
    [alunos, polo],
  );
  const turmas = useMemo(() => [TODOS, ...new Set(doPolo.map((a) => a.turma))].sort(), [doPolo]);
  const daTurma = useMemo(
    () => (turma === TODOS ? doPolo : doPolo.filter((a) => a.turma === turma)),
    [doPolo, turma],
  );
  // O valor continua sendo a matrícula (é a chave); o rótulo é que ganha o nome.
  const matriculas = useMemo(
    () => [
      { value: TODOS, label: TODOS },
      ...[...daTurma]
        .sort((a, b) => a.matricula - b.matricula)
        .map((a) => ({ value: String(a.matricula), label: identificacao(a.vigente.nome, a.matricula) })),
    ],
    [daTurma],
  );

  // Filtro que ficou fora do escopo depois de outro mudar volta para "Todos".
  const turmaAtual = turmas.includes(turma) ? turma : TODOS;
  const matriculaAtual = matriculas.some((m) => m.value === matricula) ? matricula : TODOS;

  const { series, dados } = useMemo(
    () => serieLongitudinal(alunos, crgSemestres, {
      polo: polo === TODOS ? undefined : polo,
      turmas: turmaAtual === TODOS ? undefined : [turmaAtual],
      matricula: matriculaAtual === TODOS ? undefined : Number(matriculaAtual),
    }),
    [alunos, crgSemestres, polo, turmaAtual, matriculaAtual],
  );

  const nomesTurma = useMemo(() => [...new Set(alunos.map((a) => a.turma))], [alunos]);
  const corDaSerie = (serie: string) =>
    serie.startsWith('Turma ') ? corDaTurma(serie.slice(6), nomesTurma) : COR_PRIMARIA;

  const semApuracao = dados.filter((d) => series.every((s) => d[s] === null)).map((d) => d.semestre);

  return (
    <div className="relative bg-white rounded-[2rem] shadow-[0_12px_40px_rgba(0,0,0,0.03)] border border-slate-100 p-8 w-full">
      <div className="flex justify-end gap-3 mb-8 flex-wrap">
        <SelectDropdown label="Y" options={[{ value: 'CRG', label: 'CRG' }]} value="CRG" onChange={() => {}} />
        <SelectDropdown label="Polo" options={polos} value={polo} onChange={setPolo} />
        <SelectDropdown label="Turma" options={turmas} value={turmaAtual} onChange={setTurma} />
        <SelectDropdown label="Aluno" options={matriculas} value={matriculaAtual} onChange={setMatricula} />
      </div>

      {!dados.length ? (
        <p className="py-24 text-center text-sm text-slate-500">
          Nenhum histórico acadêmico no filtro atual. O CRG por semestre vem dos PDFs do SIGAA (passo 2 do lote).
        </p>
      ) : (
        <>
          <div className="w-full pr-4">
            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={dados} margin={{ top: 10, right: 16, left: -20, bottom: 5 }}>
                <CartesianGrid vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="semestre" axisLine={false} tickLine={false} interval={0}
                  tick={{ fill: '#64748b', fontSize: 12, fontWeight: 500 }} dy={12}
                  padding={{ left: 12, right: 12 }}
                />
                <YAxis
                  domain={[0, 10]} ticks={[0, 2, 4, 6, 8, 10]} axisLine={false} tickLine={false}
                  tick={{ fill: '#64748b', fontSize: 13, fontWeight: 500 }} dx={-8}
                />
                <Tooltip
                  cursor={{ stroke: '#cbd5e1', strokeWidth: 1 }}
                  contentStyle={{ background: '#0f172a', border: 'none', borderRadius: 12, color: '#f8fafc', fontSize: 13, padding: '10px 16px' }}
                  labelStyle={{ color: '#94a3b8', fontWeight: 600, marginBottom: 4 }}
                  labelFormatter={(s) => `Semestre ${s}`}
                  formatter={(v, nome) => [v === null || v === undefined ? 'não apurado' : Number(v).toFixed(2), nome]}
                />
                {/* Identidade nunca só pela cor: com 7 turmas os tons vizinhos
                    ficam próximos, e é a legenda que desempata. */}
                {series.length > 1 && <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />}
                {series.map((serie) => (
                  <Line
                    key={serie} type="monotone" dataKey={serie} name={serie}
                    stroke={corDaSerie(serie)} strokeWidth={2}
                    dot={{ r: 4, fill: '#fff', stroke: corDaSerie(serie), strokeWidth: 2 }}
                    activeDot={{ r: 5 }}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <p className="mt-6 pt-4 border-t border-slate-100 text-[11px] text-slate-500">
            <span className="font-semibold text-slate-600">{series.length} série(s)</span> sobre {dados.length} semestre(s).
            {semApuracao.length > 0 && ` Sem apuração (lacuna na linha): ${semApuracao.join(', ')}.`}
            {' '}A média de cada ponto usa só quem tem nota naquele semestre.
          </p>
        </>
      )}

      <BotaoIA />
    </div>
  );
}
