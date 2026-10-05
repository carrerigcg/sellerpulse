/**
 * Marca do SellerPulse.
 *
 * O destaque em laranja fica só na segunda metade da palavra — é a mesma
 * ideia do "em um só lugar" destacado do Adstart: a cor forte aparece numa
 * fatia pequena do texto, não no bloco todo. Isso é o que mantém o laranja
 * "sutil" mesmo sendo uma cor saturada.
 */
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-semibold tracking-tight ${className}`}>
      Seller<span className="text-accent">Pulse</span>
    </span>
  );
}

/** Versão de uma letra e meia, para o trilho de ícones da sidebar, onde os
 *  83px do `Wordmark` não cabem nos 64 disponíveis. Mantém a mesma ideia de
 *  cor: o laranja só na segunda metade. */
export function Monograma({ className = "" }: { className?: string }) {
  return (
    <span className={`font-semibold tracking-tight ${className}`} aria-hidden>
      S<span className="text-accent">P</span>
    </span>
  );
}
