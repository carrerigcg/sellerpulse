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
