import Link from "next/link";

import { CartoesDePlanos } from "@/components/planos/cartoes-de-planos";

/**
 * Seção de preços — os planos à venda, com o Exclusive em destaque.
 *
 * Vem depois de "Seus dados" e antes da faixa final: quem chegou até aqui já
 * viu o produto, entendeu o que faz e perdeu o medo de conectar a conta; a
 * pergunta seguinte é "quanto custa". O `id` é o destino do "Preços" do
 * cabeçalho, e o `scroll-mt` desconta o cabeçalho fixo.
 *
 * Os cartões são os mesmos de `/planos`, para as duas páginas nunca
 * prometerem coisas diferentes.
 */
export function Precos() {
  return (
    <section id="precos" className="scroll-mt-20 bg-surface/60">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
        <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Planos
        </h2>
        <p className="mt-4 max-w-2xl text-muted">
          Todos conectam a sua conta do Mercado Livre e mostram quanto sobra de cada venda. O que
          muda é o quanto do painel você usa para decidir.
        </p>

        <div className="mt-14">
          <CartoesDePlanos />
        </div>

        <p className="mt-10 text-sm text-muted">
          Quer ver como funciona?{" "}
          <Link href="/demo" className="font-medium text-accent underline hover:text-accent-hover">
            Abra a demonstração
          </Link>
          , com uma loja de exemplo e todas as telas.
        </p>
      </div>
    </section>
  );
}
