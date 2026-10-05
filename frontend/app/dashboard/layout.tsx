import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

import { NavegacaoDashboard } from "./navegacao";

export default async function DashboardLayout({
  children,
}: LayoutProps<"/dashboard">) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // O proxy já protege a rota; isto é defesa em profundidade para o caso de
  // o matcher mudar e alguém esquecer desta página.
  if (!user) redirect("/login");

  // A sidebar é montada em `navegacao.tsx`, e não aqui, porque duas das props
  // do `<Sidebar>` são funções (`grupos` carrega os componentes de ícone,
  // `rodape` é a função de `comRotulos`) e função não atravessa a fronteira
  // servidor→cliente. Daqui só desce o email, que é string.
  return (
    <NavegacaoDashboard email={user.email ?? ""}>{children}</NavegacaoDashboard>
  );
}
