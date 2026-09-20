import { useContext } from 'react';
import { Contexto } from './DadosProvider';
import type { Dados } from './DadosProvider';

export { TODOS_PERIODOS } from './DadosProvider';

export function useDados(): Dados {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error('useDados precisa estar dentro de <DadosProvider>');
  return ctx;
}
