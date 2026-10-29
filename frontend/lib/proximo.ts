/**
 * Para onde voltar depois do login: o `?proximo=` que o proxy põe quando
 * manda alguém entrar (ex.: quem clicou "Assinar" sem estar logado).
 *
 * Só caminho do próprio site. Um `proximo` que saísse do site transformaria o
 * login num redirecionamento aberto, que é como se monta página falsa de
 * login com o nosso domínio na frente.
 *
 * A conferência é pela ORIGEM do endereço resolvido, e não pelo começo do
 * texto: o navegador remove TAB e quebra de linha de qualquer URL, então
 * "/\t/golpe.dev" passaria num teste de prefixo e viraria "//golpe.dev".
 */
export function destinoSeguro(proximo: string | null, origem: string): string {
  if (!proximo) return "/dashboard";
  let url: URL;
  try {
    url = new URL(proximo, origem);
  } catch {
    return "/dashboard";
  }
  if (url.origin !== new URL(origem).origin) return "/dashboard";
  return `${url.pathname}${url.search}${url.hash}`;
}

/** O `proximo` da URL atual, já conferido. Só no navegador. */
export function destinoDepoisDoLogin(): string {
  return destinoSeguro(
    new URLSearchParams(window.location.search).get("proximo"),
    window.location.origin,
  );
}
