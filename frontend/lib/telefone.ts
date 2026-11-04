/**
 * O telefone do vendedor: opcional, só para contato, e WhatsApp só com aceite
 * (spec docs/specs/2026-11-04-telefone-e-verificacao-em-duas-etapas-design.md).
 *
 * Guardado como dígitos, DDD + número, sem o 55: é o que se digita no Brasil,
 * e a máscara fica só na tela.
 */

/** Dígitos do telefone, ou `null` se não fecha DDD + 8 ou 9 dígitos. */
export function normalizaTelefone(texto: string): string | null {
  let digitos = texto.replace(/\D/g, "");
  // Quem cola "+55 11 ..." traz o código do país junto.
  if ((digitos.length === 12 || digitos.length === 13) && digitos.startsWith("55")) {
    digitos = digitos.slice(2);
  }
  if (digitos.length !== 10 && digitos.length !== 11) return null;
  // DDD não começa com 0.
  if (digitos.startsWith("0")) return null;
  return digitos;
}

/** "(11) 98765-4321" ou "(11) 3456-7890". */
export function formataTelefone(digitos: string): string {
  const ddd = digitos.slice(0, 2);
  const resto = digitos.slice(2);
  const meio = resto.length - 4;
  return `(${ddd}) ${resto.slice(0, meio)}-${resto.slice(meio)}`;
}

export type ContatoSalvo = { telefone: string | null; aceitoEm: string | null };

/**
 * Os metadados que o Supabase Auth guarda. O aceite do WhatsApp é a data e
 * hora em que foi dado: sem telefone, não há aceite; desmarcado, some.
 *
 * O aceite é "nesse número": trocar o número com a caixa marcada é um aceite
 * novo, com a data de agora. Reaproveitar a data antiga atestaria um aceite
 * dado antes de o número existir no cadastro.
 */
export function metadadosDeContato(
  telefone: string | null,
  querWhatsapp: boolean,
  anterior: ContatoSalvo | null,
  agora: Date,
): { telefone: string | null; whatsapp_aceito_em: string | null } {
  if (!telefone || !querWhatsapp) return { telefone, whatsapp_aceito_em: null };
  const mesmoNumero = anterior?.telefone === telefone;
  return {
    telefone,
    whatsapp_aceito_em: (mesmoNumero && anterior?.aceitoEm) || agora.toISOString(),
  };
}
