import { useState } from 'react';
import type { ChangeEvent } from 'react';
import type { HistoricosOut } from '../../data/tipos';
import { filtrarArquivosAceitos } from '../../domain/lote';

interface Props {
  ocupado: boolean;
  onEnviar: (arquivos: File[]) => void;
}

export default function PassoEnviar({ ocupado, onEnviar }: Props) {
  const [aceitos, setAceitos] = useState<File[]>([]);
  const [rejeitados, setRejeitados] = useState<File[]>([]);

  function escolher(e: ChangeEvent<HTMLInputElement>) {
    const r = filtrarArquivosAceitos(Array.from(e.target.files ?? []));
    setAceitos(r.aceitos);
    setRejeitados(r.rejeitados);
  }

  return (
    <div className="space-y-3 text-sm">
      <label className="block">
        <span className="font-medium text-slate-700">Históricos do SIGAA (um .zip ou vários .pdf)</span>
        <input type="file" multiple accept=".zip,.pdf" onChange={escolher} disabled={ocupado} className="mt-1 block w-full text-sm" />
      </label>
      {aceitos.length > 0 && <p className="text-slate-600">{aceitos.length} arquivo(s) selecionado(s).</p>}
      {rejeitados.length > 0 && (
        <p className="text-amber-700">Ignorados (só .zip ou .pdf): {rejeitados.map((f) => f.name).join(', ')}</p>
      )}
      <button type="button" onClick={() => onEnviar(aceitos)} disabled={ocupado || aceitos.length === 0} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
        {ocupado ? 'Enviando e rodando…' : 'Enviar e rodar'}
      </button>
    </div>
  );
}

/** Resumo do último envio: o que gravou, o que ignorou, e os contadores dos passos. */
export function ResultadoEnvio({ resultado }: { resultado: HistoricosOut }) {
  const passo = (nome: string, valor: HistoricosOut['sincronizar']) => {
    if (valor === null) return null;
    const texto = valor === 'ja_executado' ? 'já executado' : Object.entries(valor).filter(([k]) => k !== 'lote' && k !== 'ingestao_id').map(([k, v]) => `${k}=${v}`).join(', ');
    return <li><span className="font-medium">{nome}:</span> {texto}</li>;
  };
  return (
    <ul className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-900 space-y-1">
      <li>{resultado.gravados.length} gravado(s), {resultado.ja_existiam.length} já existia(m), {resultado.ignorados.length} ignorado(s){resultado.ignorados.length > 0 && `: ${resultado.ignorados.join(', ')}`}</li>
      {passo('Passo 1 (sincronizar)', resultado.sincronizar)}
      {passo('Passo 2 (atualizar CRG)', resultado.atualizar_crg)}
    </ul>
  );
}
