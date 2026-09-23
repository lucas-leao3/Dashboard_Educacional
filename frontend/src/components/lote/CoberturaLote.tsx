import KpiCard from '../ui/KpiCard';
import { resumirCobertura } from '../../domain/lote';
import { SEM_NOME, nomeExibido } from '../../domain/aluno';
import { poloParaExibir, turmaParaExibir } from '../../domain/matricula';
import type { Correspondencia, Lote } from '../../data/tipos';

interface Props {
  lote: Lote;
  /** null = ainda carregando. */
  linhas: Correspondencia[] | null;
  erro: string | null;
}

const ROTULO_FALTANDO: Record<Correspondencia['faltando'], string> = {
  '': '—', Academico: 'Acadêmico', SocioEconomico: 'Socioeconômico', Ambos: 'Ambos',
};

/** "Cobertura do lote": o corte transversal (governança §4.7) na tela. */
export default function CoberturaLote({ lote, linhas, erro }: Props) {
  const resumo = linhas ? resumirCobertura(linhas) : null;
  const excecoes = Object.entries(lote.excecoes_por_motivo);

  return (
    <section className="space-y-4" aria-labelledby="cobertura-titulo">
      <h2 id="cobertura-titulo" className="text-base font-bold text-slate-800">Cobertura do lote {lote.id}</h2>

      {resumo && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <KpiCard label="Alunos no lote" value={resumo.total} />
          <KpiCard label="Completos" value={resumo.completos} hint="acadêmico + socioeconômico" />
          <KpiCard label="Falta acadêmico" value={resumo.faltaAcademico} tone={resumo.faltaAcademico ? 'atencao' : undefined} hint="sem histórico em PDF" />
          <KpiCard label="Falta socioeconômico" value={resumo.faltaSocio} tone={resumo.faltaSocio ? 'atencao' : undefined} hint="sem resposta no FasiTech" />
          <KpiCard label="Falta ambos" value={resumo.faltaAmbos} tone={resumo.faltaAmbos ? 'critico' : undefined} />
        </div>
      )}

      <div className="rounded-2xl bg-white border border-slate-200/80 p-5 text-sm">
        <h3 className="font-semibold text-slate-700 mb-2">Ingestões e exceções</h3>
        <ul className="text-slate-600 space-y-1">
          {lote.ingestoes.map((i) => (
            <li key={i.id}>Passo {i.passo}: {i.registros_lidos} lidos, {i.registros_aceitos} aceitos, {i.registros_rejeitados} rejeitados</li>
          ))}
          {excecoes.length === 0 && <li>Nenhuma exceção.</li>}
          {excecoes.map(([motivo, n]) => <li key={motivo}><code>{motivo}</code>: {n}</li>)}
        </ul>
      </div>

      <div className="rounded-2xl bg-white border border-slate-200/80 overflow-x-auto">
        {erro && <p className="p-5 text-sm text-red-700">Não foi possível carregar a correspondência: {erro}</p>}
        {!erro && !linhas && <p className="p-5 text-sm text-slate-500">Carregando…</p>}
        {linhas && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500 bg-slate-50">
              <tr><th className="px-4 py-2">Matrícula</th><th className="px-4 py-2">Nome</th><th className="px-4 py-2">Polo</th><th className="px-4 py-2">Turma</th><th className="px-4 py-2">Acadêmico</th><th className="px-4 py-2">Socioeconômico</th><th className="px-4 py-2">Faltando</th></tr>
            </thead>
            <tbody>
              {linhas.map((l) => (
                <tr key={l.matricula} className="border-t border-slate-100">
                  <td className="px-4 py-2 font-mono">{l.matricula}</td>
                  {/* Tabela: matrícula e nome já são colunas separadas, então aqui
                      não se repete a identificação -- só o mesmo marcador de ausência. */}
                  <td className="px-4 py-2">{nomeExibido(l.nome) ?? <span className="text-slate-400">{SEM_NOME}</span>}</td>
                  {/* Derivados da matrícula (governança §4.8): a API não manda nenhum dos dois. */}
                  <td className="px-4 py-2">{poloParaExibir(l.matricula)}</td>
                  <td className="px-4 py-2">{turmaParaExibir(l.matricula)}</td>
                  <td className="px-4 py-2">{l.academico ? 'Sim' : 'Não'}</td>
                  <td className="px-4 py-2">{l.socioeconomico ? 'Sim' : 'Não'}</td>
                  <td className="px-4 py-2">{ROTULO_FALTANDO[l.faltando]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
