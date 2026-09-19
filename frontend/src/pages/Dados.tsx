import { useEffect, useMemo, useState } from 'react';
import AppShell from '../components/layout/AppShell';
import CoberturaLote from '../components/lote/CoberturaLote';
import InserirLote from '../components/lote/InserirLote';
import * as api from '../data/api';
import type { NovoLote } from '../data/api';
import type { Correspondencia, HistoricosOut } from '../data/tipos';
import { criarFluxoLote } from '../hooks/fluxoLote';
import { useDados } from '../hooks/useDados';

const NOVO = '__novo__';

/** Tela Dados: inserir um lote (abrir → enviar e rodar → fechar) e ver a cobertura. */
export default function Dados() {
  const { origem, carregando, lotes, recarregar } = useDados();
  // null = ainda não escolheu: cai no lote mais recente, ou em "novo" se não há nenhum.
  const [escolhido, setEscolhido] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultadoEnvio, setResultadoEnvio] = useState<HistoricosOut | null>(null);
  const [linhas, setLinhas] = useState<Correspondencia[] | null>(null);
  const [erroCobertura, setErroCobertura] = useState<string | null>(null);
  const [versao, setVersao] = useState(0); // incrementa após enviar/fechar para recarregar a cobertura

  const selecionadoId = escolhido ?? (lotes.length > 0 ? lotes[lotes.length - 1].id : NOVO);
  const lote = useMemo(() => lotes.find((l) => l.id === selecionadoId) ?? null, [lotes, selecionadoId]);

  const fluxo = useMemo(() => criarFluxoLote({ api, recarregar }), [recarregar]);

  useEffect(() => {
    if (!lote) { setLinhas(null); setErroCobertura(null); return; }
    let ativo = true;
    setLinhas(null);
    api.carregarCorrespondencia(lote.id)
      .then((ls) => { if (ativo) { setLinhas(ls); setErroCobertura(null); } })
      .catch((e) => { if (ativo) setErroCobertura(e instanceof api.ErroApi ? e.detail : String(e)); });
    return () => { ativo = false; };
  }, [lote?.id, lote?.fechado_em, versao]);

  async function rodar<T>(acao: () => Promise<{ ok: true; dados: T } | { ok: false; erro: string | null; status: number }>, depois?: (dados: T) => void) {
    setOcupado(true);
    setErro(null);
    const r = await acao();
    setOcupado(false);
    if (r.ok) depois?.(r.dados);
    else if (r.erro !== null) setErro(r.status === 502 || r.status === 503 ? `${r.erro} — os PDFs ficaram gravados; reenvie os mesmos arquivos para retomar.` : r.erro);
  }

  const onAbrir = (d: NovoLote) => rodar(() => fluxo.abrir(d), (novo) => { setEscolhido(novo.id); setResultadoEnvio(null); });
  const onEnviar = (arquivos: File[]) => rodar(() => fluxo.enviar(selecionadoId, arquivos), (saida) => { setResultadoEnvio(saida); setVersao((v) => v + 1); });
  const onFechar = () => rodar(() => fluxo.fechar(selecionadoId), () => setVersao((v) => v + 1));

  return (
    <AppShell titulo="Dados" subtitulo="Insira um lote de dados e confira a cobertura do que entrou." migalhas={[{ rotulo: 'Dados' }]} semFiltros>
      {origem === 'demonstracao' && !carregando ? (
        <p className="rounded-2xl bg-amber-50 border border-amber-200 p-5 text-sm text-amber-900">
          A inserção de dados exige a API. Suba o backend (<code>docker compose up -d</code>) e recarregue a página.
        </p>
      ) : (
        <div className="space-y-6">
          <label className="block text-sm max-w-xs">
            <span className="font-medium text-slate-700">Lote</span>
            <select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={selecionadoId} disabled={ocupado} onChange={(e) => { setEscolhido(e.target.value); setErro(null); setResultadoEnvio(null); }}>
              <option value={NOVO}>Novo lote</option>
              {lotes.map((l) => <option key={l.id} value={l.id}>{l.id}{l.fechado_em ? ' (fechado)' : ''}</option>)}
            </select>
          </label>

          <InserirLote lote={lote} lotes={lotes} ocupado={ocupado} erro={erro} resultadoEnvio={resultadoEnvio} onAbrir={onAbrir} onEnviar={onEnviar} onFechar={onFechar} />

          {lote && <CoberturaLote lote={lote} linhas={linhas} erro={erroCobertura} />}
        </div>
      )}
    </AppShell>
  );
}
