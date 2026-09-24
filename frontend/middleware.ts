import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Protege /dashboard: sem sessão Supabase válida, redireciona para /login.
 *
 * @supabase/ssr@0.12.7 exige getAll/setAll (não get/set/remove) e o
 * `setAll` do server client recebe um segundo argumento `headers` com
 * cache-control headers de auth, que devem ser propagados para a
 * resposta (ver README do pacote).
 *
 * Nota: no Next.js 16 o arquivo `middleware.ts` foi renomeado para
 * `proxy.ts` (a função continua funcionando de forma idêntica, apenas
 * deprecated). Mantido como `middleware.ts` por ser o que a task pediu.
 */
export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet, headers) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
          Object.entries(headers).forEach(([key, value]) =>
            supabaseResponse.headers.set(key, value),
          );
        },
      },
    },
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
