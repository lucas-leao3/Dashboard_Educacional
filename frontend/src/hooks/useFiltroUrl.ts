import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { comFiltro, lerFiltro } from '../domain/filtrosUrl';

/** Como useState, mas o valor mora na URL (`?nome=valor`). */
export function useFiltroUrl(nome: string, padrao: string): [string, (valor: string) => void] {
  const [params, setParams] = useSearchParams();
  const definir = useCallback(
    (valor: string) => setParams((atuais) => comFiltro(atuais, nome, valor, padrao), { replace: true }),
    [nome, padrao, setParams],
  );
  return [lerFiltro(params, nome, padrao), definir];
}
