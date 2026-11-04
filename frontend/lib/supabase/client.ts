import { createBrowserClient } from "@supabase/ssr";

/**
 * Cliente Supabase para uso em Client Components.
 * Usa a API getAll/setAll do @supabase/ssr (exigida a partir da v0.5;
 * instalado aqui: @supabase/ssr@0.12.7). A gestão de cookies do browser
 * fica a cargo da própria lib quando getAll/setAll não são customizados.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}

/**
 * Cliente que não lê a URL sozinho, para `/redefinir-senha` trocar o `?code=`
 * do link de recuperação com as próprias mãos.
 *
 * O cliente padrão troca o código na criação e, se a troca falhar, segue com
 * a sessão que já estava aberta: a tela não saberia se a sessão veio do link
 * ou de alguém que deixou o computador logado. Trocando aqui, o erro chega.
 * A sessão nova vai para os mesmos cookies, e o cliente padrão a enxerga.
 */
export function createClientSemLerAUrl() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { isSingleton: false, auth: { detectSessionInUrl: false } },
  );
}
