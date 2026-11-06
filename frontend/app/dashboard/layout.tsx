import { redirect } from "next/navigation";

import { SeletorDeConta } from "@/components/contas/seletor-de-conta";
import { VoltaParaPrincipal } from "@/components/contas/volta-para-principal";
import { RegistroDeAcesso } from "@/components/registro-de-acesso";
import { ApiError, getAcesso } from "@/lib/api";
import { contasDoSeletor } from "@/lib/contas";
import { destinoSemAcesso } from "@/lib/plano";
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

  // Sem plano, só a demo; com plano e sem aceite, os termos primeiro. O
  // backend recusa os dados do mesmo jeito (402/403) — isto é o caminho, não
  // a trava. Se a pergunta falhar, o painel abre e cada tela mostra o próprio
  // erro, como antes: um backend dormindo não pode virar "contrate um plano".
  const acesso = await getAcesso().catch((e: unknown) =>
    // A conta do seletor não abre mais: a escolha é apagada no navegador, e
    // nenhuma tela é montada com ela no meio do caminho.
    e instanceof ApiError && e.codigo === "conta-invalida" ? ("conta-invalida" as const) : null,
  );
  if (acesso === "conta-invalida") return <VoltaParaPrincipal />;
  const destino = acesso && destinoSemAcesso(acesso);
  if (destino) redirect(destino);
  const contas = acesso ? contasDoSeletor(acesso) : [];

  // A sidebar é montada em `navegacao.tsx`, e não aqui, porque duas das props
  // do `<Sidebar>` são funções (`grupos` carrega os componentes de ícone,
  // `rodape` é a função de `comRotulos`) e função não atravessa a fronteira
  // servidor→cliente. Daqui só desce o email, que é string.
  return (
    <>
      <RegistroDeAcesso />
      <NavegacaoDashboard email={user.email ?? ""}>
        {acesso && contas.length > 0 && (
          <SeletorDeConta contas={contas} aberta={acesso.conta_aberta} />
        )}
        {children}
      </NavegacaoDashboard>
    </>
  );
}
