import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Cliente Supabase para uso em Server Components.
 * @supabase/ssr@0.12.7 exige a API getAll/setAll (não get/set/remove).
 * `setAll` também recebe um segundo argumento `headers` com cache-control
 * headers de auth — Server Components não conseguem escrever headers de
 * resposta, então ele é ignorado aqui; quem garante que a sessão seja
 * atualizada e propagada é o middleware (frontend/middleware.ts).
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // `setAll` chamado a partir de um Server Component: pode ser
            // ignorado se o middleware já estiver renovando a sessão.
          }
        },
      },
    },
  );
}
