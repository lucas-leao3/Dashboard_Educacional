import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { carregarCrgSemestres, carregarLotes, carregarRegistros } from '../data/api';
import type { Origem } from '../data/api';
import type { CrgSemestre, Lote, Registro } from '../data/tipos';
import { consolidarAlunos, ordenarPeriodos } from '../domain/agregacao';
import type { Aluno } from '../domain/agregacao';

export const TODOS_PERIODOS = '';

export interface Dados {
  carregando: boolean;
  origem: Origem;
  registros: Registro[];
  /** Todos os períodos existentes na base, em ordem cronológica. */
  periodos: string[];
  /** Filtro global de período (doc, item 9). Vazio = todos. */
  periodo: string;
  setPeriodo: (p: string) => void;
  /** Alunos consolidados já respeitando o filtro de período. */
  alunos: Aluno[];
  /** Alunos sem filtro de período (histórico completo), para o perfil. */
  alunosTodos: Aluno[];
  /**
   * Trajetória acadêmica por semestre letivo (GET /crg-semestres). Nunca é
   * filtrada por período: o período é a janela de coleta socioeconômica, e o
   * semestre é o calendário acadêmico -- são eixos diferentes.
   */
  crgSemestres: CrgSemestre[];
  /** O lote vigente (mais recente com ao menos uma ingestão), pro selo do AppShell. */
  lote: Lote | null;
  /** Todos os lotes, na ordem da API (executado_em). Para o seletor da tela Dados. */
  lotes: Lote[];
  /** Refaz as duas cargas. Chamado depois de abrir/enviar/fechar um lote. */
  recarregar: () => Promise<void>;
}

export const Contexto = createContext<Dados | null>(null);

function loteVigente(lotes: Lote[]): Lote | null {
  const comIngestao = lotes.filter((l) => l.ingestoes.length > 0);
  if (comIngestao.length === 0) return null;
  return comIngestao.reduce((mais_recente, atual) =>
    atual.executado_em > mais_recente.executado_em ? atual : mais_recente
  );
}

export function DadosProvider({ children }: { children: ReactNode }) {
  const [registros, setRegistros] = useState<Registro[]>([]);
  const [origem, setOrigem] = useState<Origem>('demonstracao');
  const [carregando, setCarregando] = useState(true);
  const [periodo, setPeriodo] = useState(TODOS_PERIODOS);
  const [lotes, setLotes] = useState<Lote[]>([]);
  const [crgSemestres, setCrgSemestres] = useState<CrgSemestre[]>([]);

  const recarregar = useCallback(async () => {
    const [r, ls, cs] = await Promise.all([carregarRegistros(), carregarLotes(), carregarCrgSemestres()]);
    setRegistros(r.registros);
    setOrigem(r.origem);
    setLotes(ls);
    setCrgSemestres(cs);
    setCarregando(false);
  }, []);

  useEffect(() => {
    let ativo = true;
    Promise.all([carregarRegistros(), carregarLotes(), carregarCrgSemestres()]).then(([r, ls, cs]) => {
      if (!ativo) return;
      setRegistros(r.registros);
      setOrigem(r.origem);
      setLotes(ls);
      setCrgSemestres(cs);
      setCarregando(false);
    });
    return () => { ativo = false; };
  }, []);

  const lote = useMemo(() => loteVigente(lotes), [lotes]);

  const periodos = useMemo(() => ordenarPeriodos(registros.map((r) => r.periodo)), [registros]);
  const alunosTodos = useMemo(() => consolidarAlunos(registros), [registros]);
  const alunos = useMemo(
    () => (periodo ? consolidarAlunos(registros, periodo) : alunosTodos),
    [registros, periodo, alunosTodos],
  );

  const valor = useMemo<Dados>(
    () => ({ carregando, origem, registros, periodos, periodo, setPeriodo, alunos, alunosTodos, crgSemestres, lote, lotes, recarregar }),
    [carregando, origem, registros, periodos, periodo, alunos, alunosTodos, crgSemestres, lote, lotes, recarregar],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

