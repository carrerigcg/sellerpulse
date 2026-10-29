/**
 * Para onde voltar depois do login: o `?proximo=` que o proxy põe quando
 * manda alguém entrar (ex.: quem clicou "Assinar" sem estar logado).
 *
 * Só caminho do próprio site. Um `proximo=https://outro.site` ou
 * `proximo=//outro.site` transformaria o login num redirecionamento aberto,
 * que é como se monta página falsa de login com o nosso domínio na frente.
 */
export function destinoSeguro(proximo: string | null): string {
  if (!proximo || !proximo.startsWith("/") || proximo.startsWith("//") || proximo.startsWith("/\\")) {
    return "/dashboard";
  }
  return proximo;
}

/** O `proximo` da URL atual, já conferido. Só no navegador. */
export function destinoDepoisDoLogin(): string {
  return destinoSeguro(new URLSearchParams(window.location.search).get("proximo"));
}
