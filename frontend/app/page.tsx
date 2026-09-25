import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

/**
 * Raiz do site: encaminha conforme a sessão.
 *
 * Não há landing page ainda — ela é escopo de uma sprint própria, com o
 * vídeo de hero. Até lá, deixar a raiz como página de verdade só produziria
 * uma tela vazia para quem digita o domínio, que foi o que acontecia aqui.
 * Redirecionar é o comportamento honesto enquanto a vitrine não existe.
 */
export default async function Home() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  redirect(user ? "/dashboard" : "/login");
}
