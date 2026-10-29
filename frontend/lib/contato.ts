/**
 * Como falar com o SellerPulse para contratar, enquanto não há checkout.
 *
 * O WhatsApp fica `null` até o número ser definido: um link para um número
 * errado é pior do que nenhum link.
 */
export const EMAIL_DE_CONTATO = "carreri.gcg@gmail.com";
export const WHATSAPP_DE_CONTATO: string | null = "5511992344633";

export function linkDeEmail(assunto: string): string {
  return `mailto:${EMAIL_DE_CONTATO}?subject=${encodeURIComponent(assunto)}`;
}

/** `numero` só com dígitos, com DDI e DDD (ex.: 5511999999999). */
export function linkDeWhatsapp(numero: string, mensagem: string): string {
  return `https://wa.me/${numero}?text=${encodeURIComponent(mensagem)}`;
}
