import { useEffect, useRef } from "react";

/**
 * Qual botão recebe o foco quando uma confirmação fecha: o que a abriu.
 *
 * Abrir a confirmação desmonta esse botão, e fechá-la (Voltar, erro, fim da
 * ação) o monta de novo, sem foco: o teclado caía no `body` e a pessoa
 * recomeçava do topo da página.
 */
export function quemRecebeOFoco<K extends string>(anterior: K | null, atual: K | null): K | null {
  return anterior !== null && atual === null ? anterior : null;
}

/**
 * `aberta` é a chave da confirmação aberta, ou `null`. Devolve o `ref` de cada
 * botão que abre uma confirmação, pela chave dela.
 */
export function useFocoDeVolta<K extends string>(aberta: K | null) {
  const botoes = useRef<Partial<Record<K, HTMLButtonElement | null>>>({});
  const anterior = useRef<K | null>(null);

  useEffect(() => {
    const destino = quemRecebeOFoco(anterior.current, aberta);
    if (destino !== null) botoes.current[destino]?.focus();
    anterior.current = aberta;
  }, [aberta]);

  return (chave: K) => (botao: HTMLButtonElement | null) => {
    botoes.current[chave] = botao;
  };
}
