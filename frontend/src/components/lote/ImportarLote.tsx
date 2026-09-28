import { useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import type { ImportacaoOut } from '../../data/tipos';
import { pendenciaDaImportacao } from '../../domain/lote';

interface Props {
  ocupado: boolean;
  erro: string | null;
  resultado: ImportacaoOut | null;
  onImportar: (responsavel: string, arquivo: File) => void;
}

const INPUT = 'mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500';

/**
 * Importação de um lote: só o responsável e o .zip dos históricos. Id do
 * lote, período e cruzamento vêm do backend; o lote termina fechado.
 */
export default function ImportarLote({ ocupado, erro, resultado, onImportar }: Props) {
  const [responsavel, setResponsavel] = useState('');
  const [arquivo, setArquivo] = useState<File | null>(null);
  const pendencia = pendenciaDaImportacao(responsavel, arquivo);

  function escolher(e: ChangeEvent<HTMLInputElement>) {
    setArquivo(e.target.files?.[0] ?? null);
  }

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (pendencia === null && arquivo) onImportar(responsavel, arquivo);
  }

  return (
    <section className="rounded-2xl bg-white border border-slate-200/80 p-5 space-y-4" aria-labelledby="importar-titulo">
      <div>
        <h2 id="importar-titulo" className="text-base font-bold text-slate-800">Importar históricos</h2>
        <p className="mt-1 text-sm text-slate-500">
          O período, o identificador do lote e o cruzamento com o socioeconômico são obtidos automaticamente.
          Ao terminar, o lote é fechado: não pode ser editado, receber arquivos nem ser reprocessado.
        </p>
      </div>

      <form onSubmit={enviar} className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <label className="block text-sm">
          <span className="font-medium text-slate-700">Responsável pela importação</span>
          <input className={INPUT} value={responsavel} onChange={(e) => setResponsavel(e.target.value)} disabled={ocupado} autoComplete="name" />
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-700">Arquivo .zip com os históricos (PDF)</span>
          <input type="file" accept=".zip" onChange={escolher} disabled={ocupado} className="mt-1 block w-full text-sm" />
        </label>
        <button type="submit" disabled={ocupado || pendencia !== null} title={pendencia ?? undefined} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {ocupado ? 'Importando…' : 'Importar'}
        </button>
      </form>

      {erro && (
        <p role="alert" className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">
          {erro} — nada foi gravado; corrija e importe de novo.
        </p>
      )}
      {resultado && <ResultadoImportacao resultado={resultado} />}
    </section>
  );
}

function ResultadoImportacao({ resultado }: { resultado: ImportacaoOut }) {
  const { arquivos, resumo } = resultado;
  return (
    <ul className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-900 space-y-1">
      <li className="font-semibold">Lote {resultado.id} importado e fechado.</li>
      <li>Período (extraído dos históricos): {resultado.periodos_cobertos.join(', ')}</li>
      <li>
        {arquivos.gravados.length} histórico(s) gravado(s), {arquivos.ignorados.length} ignorado(s)
        {arquivos.ignorados.length > 0 && `: ${arquivos.ignorados.join(', ')}`}
      </li>
      <li>{resumo.integrados} aluno(s) integrado(s), {resumo.nao_integrados} não integrado(s).</li>
    </ul>
  );
}
