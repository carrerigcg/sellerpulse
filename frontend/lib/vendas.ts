/**
 * Se a vitrine oferece a contratação. Quem trava de verdade é o backend
 * (`VENDAS_ABERTAS` em `POST /conta/checkout`); esta é a mesma variável na
 * Vercel, para a vitrine não mandar ninguém criar conta para algo fechado, sem
 * depender do backend para desenhar a landing. Ausente = fechado.
 */
export function vitrineComVendasAbertas(): boolean {
  return process.env.VENDAS_ABERTAS === "1";
}

/** O que o cartão de plano diz no lugar de "Assinar" enquanto as vendas estão fechadas. */
export const AVISO_DE_VENDAS_FECHADAS = "As vendas abrem em breve.";

export function mensagemParaSaberDaAbertura(plano: string): string {
  return `Olá! Quero saber quando abrem as vendas do plano ${plano} do SellerPulse.`;
}
