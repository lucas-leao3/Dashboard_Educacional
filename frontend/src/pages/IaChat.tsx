import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import Historico from '../components/assistente/Historico';
import RespostaView from '../components/assistente/RespostaView';
import { ErroApi, executarConsulta, perguntarAssistente } from '../data/api';
import type { RespostaAssistente } from '../data/tipos';
import { rotaDoDashboard } from '../domain/catalogoDashboards';
import { decodificarConsulta, linkDeCompartilhamento } from '../domain/compartilhar';
import { adicionar, alternarFavorito, carregarHistorico, salvarHistorico } from '../domain/historico';
import type { ItemHistorico } from '../domain/historico';
import { useDados } from '../hooks/useDados';

/** Assistente de consultas (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md). */
export default function IaChat() {
  const { origem, carregando } = useDados();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [pergunta, setPergunta] = useState('');
  const [respostas, setRespostas] = useState<RespostaAssistente[]>([]);
  const [historico, setHistorico] = useState<ItemHistorico[]>(() => carregarHistorico());
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);

  useEffect(() => { salvarHistorico(historico); }, [historico]);

  const registrar = useCallback((r: RespostaAssistente, texto: string) => {
    const rota = r.dashboard ? rotaDoDashboard(r.dashboard.id, r.dashboard.params) : null;
    const consulta = r.consulta;
    if (consulta) {
      setHistorico((atual) => adicionar(atual, { id: r.id, pergunta: texto, consulta, forma: r.forma, quando: new Date().toISOString(), favorito: false, rota }));
    }
    // A tela de destino mostra a explicação (AppShell lê o state).
    if (rota) navigate(rota, { state: { assistente: r.explicacao } });
    else setRespostas((atual) => [r, ...atual]);
  }, [navigate]);

  const rodar = useCallback(async (acao: () => Promise<RespostaAssistente>, texto: string) => {
    setEnviando(true);
    setErro(null);
    try {
      registrar(await acao(), texto);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.detail : 'Falha inesperada ao consultar.');
    } finally {
      setEnviando(false);
    }
  }, [registrar]);

  // Link compartilhado: /ia-chat?c=<consulta> reexecuta sem LLM, assim que a API estiver de pé.
  const codigo = params.get('c');
  useEffect(() => {
    if (!codigo || origem !== 'api') return;
    setParams({}, { replace: true });
    const consulta = decodificarConsulta(codigo);
    if (!consulta) {
      setErro('Link de consulta inválido.');
      return;
    }
    void rodar(() => executarConsulta(consulta), consulta.interpretacao || 'Consulta compartilhada');
  }, [codigo, origem, rodar, setParams]);

  const enviar = (e: FormEvent) => {
    e.preventDefault();
    const texto = pergunta.trim();
    if (texto) void rodar(() => perguntarAssistente(texto), texto);
  };

  const compartilhar = (item: ItemHistorico) => {
    const url = linkDeCompartilhamento(item, window.location.origin);
    setLink(url);
    void navigator.clipboard?.writeText(url).catch(() => {});
  };

  const semApi = origem !== 'api';
  return (
    <AppShell
      titulo="IA Chat"
      subtitulo="Pergunte em português. O assistente abre o dashboard certo, monta um gráfico, lista ou responde em texto, e mostra o que entendeu."
      migalhas={[{ rotulo: 'IA Chat' }]}
      semFiltros
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-label="Conversa" className="space-y-4">
          {!carregando && semApi && (
            <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              O assistente consulta o banco pela API, que não está disponível (modo demonstração).
            </p>
          )}
          <form onSubmit={enviar} className="flex gap-2">
            <label htmlFor="pergunta" className="sr-only">Pergunta</label>
            <input
              id="pergunta" value={pergunta} onChange={(e) => setPergunta(e.target.value)} maxLength={500}
              placeholder="Ex.: Compare renda familiar por polo" disabled={semApi || enviando}
              className="flex-1 rounded-xl border border-slate-300 px-4 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            />
            <button type="submit" disabled={semApi || enviando || !pergunta.trim()} className="rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-300">
              {enviando ? 'Consultando…' : 'Perguntar'}
            </button>
          </form>
          {erro && <p role="alert" className="text-sm text-red-700">{erro}</p>}
          {link && <p className="text-xs text-slate-600">Link copiado: <span className="break-all">{link}</span></p>}
          {respostas.map((r) => <RespostaView key={r.id} resposta={r} onSugestao={setPergunta} />)}
        </section>
        <Historico
          itens={historico}
          onRepetir={(i) => void rodar(() => executarConsulta(i.consulta), i.pergunta)}
          onEditar={(i) => setPergunta(i.pergunta)}
          onFavoritar={(i) => setHistorico((h) => alternarFavorito(h, i.id))}
          onCompartilhar={compartilhar}
        />
      </div>
    </AppShell>
  );
}
