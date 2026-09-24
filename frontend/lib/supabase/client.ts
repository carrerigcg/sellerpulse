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
