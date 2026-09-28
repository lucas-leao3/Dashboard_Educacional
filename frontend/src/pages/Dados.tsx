import { useEffect, useMemo, useState } from 'react';
import AppShell from '../components/layout/AppShell';
import ImportarLote from '../components/lote/ImportarLote';
import RelatorioLote from '../components/lote/RelatorioLote';
import * as api from '../data/api';
import type { ImportacaoOut, Relatorio } from '../data/tipos';
import { criarFluxoLote } from '../hooks/fluxoLote';
import { useDados } from '../hooks/useDados';

/** Tela Dados: importar um lote (responsável + .zip) e ver os relatórios de cada lote. */
export default function Dados() {
  const { origem, carregando, lotes, recarregar } = useDados();
  // null = ainda não escolheu: cai no lote mais recente.
  const [escolhido, setEscolhido] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ImportacaoOut | null>(null);
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [erroRelatorio, setErroRelatorio] = useState<string | null>(null);

  const selecionadoId = escolhido ?? (lotes.length > 0 ? lotes[lotes.length - 1].id : null);
  const lote = useMemo(() => lotes.find((l) => l.id === selecionadoId) ?? null, [lotes, selecionadoId]);
  const loteId = lote?.id ?? null;

  const fluxo = useMemo(() => criarFluxoLote({ api, recarregar }), [recarregar]);

  // Lote fechado não muda: o relatório só precisa ser buscado quando o lote escolhido muda.
  useEffect(() => {
    if (!loteId) { setRelatorio(null); setErroRelatorio(null); return; }
    let ativo = true;
    setRelatorio(null);
    api.carregarRelatorio(loteId)
      .then((r) => { if (ativo) { setRelatorio(r); setErroRelatorio(null); } })
      .catch((e) => { if (ativo) setErroRelatorio(e instanceof api.ErroApi ? e.detail : String(e)); });
    return () => { ativo = false; };
  }, [loteId]);

  async function onImportar(responsavel: string, arquivo: File) {
    setOcupado(true);
    setErro(null);
    setResultado(null);
    const r = await fluxo.importar(responsavel, arquivo);
    setOcupado(false);
    if (r.ok) {
      setResultado(r.dados);
      setEscolhido(r.dados.id);
    } else if (r.erro !== null) {
      setErro(r.erro);
    }
  }

  return (
    <AppShell titulo="Dados" subtitulo="Importe os históricos acadêmicos e confira o que foi integrado em cada lote." migalhas={[{ rotulo: 'Dados' }]} semFiltros>
      {origem === 'demonstracao' && !carregando ? (
        <p className="rounded-2xl bg-amber-50 border border-amber-200 p-5 text-sm text-amber-900">
          A importação de dados exige a API. Suba o backend (<code>docker compose up -d</code>) e recarregue a página.
        </p>
      ) : (
        <div className="space-y-6">
          <ImportarLote ocupado={ocupado} erro={erro} resultado={resultado} onImportar={onImportar} />

          {lotes.length > 0 && selecionadoId && (
            <label className="block text-sm max-w-xs">
              <span className="font-medium text-slate-700">Lote</span>
              <select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={selecionadoId} disabled={ocupado} onChange={(e) => setEscolhido(e.target.value)}>
                {lotes.map((l) => (
                  <option key={l.id} value={l.id}>{l.id} · {l.periodos_cobertos.join(', ')}{l.fechado_em ? '' : ' (aberto)'}</option>
                ))}
              </select>
            </label>
          )}

          {lote && <RelatorioLote lote={lote} relatorio={relatorio} erro={erroRelatorio} />}
        </div>
      )}
    </AppShell>
  );
}
