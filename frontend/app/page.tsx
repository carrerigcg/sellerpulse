import { Acoes } from "@/components/landing/acoes";
import { FinalCta } from "@/components/landing/final-cta";
import { LandingFooter } from "@/components/landing/footer";
import { LandingHeader } from "@/components/landing/header";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { MlFocus } from "@/components/landing/ml-focus";
import { Problem } from "@/components/landing/problem";
import { Showcase } from "@/components/landing/showcase";
import { YourData } from "@/components/landing/your-data";
import { createClient } from "@/lib/supabase/server";

/**
 * Raiz do site: a vitrine, não mais um redirecionamento.
 *
 * Antes da Sprint 3, `/` só checava sessão e mandava pra `/dashboard` ou
 * `/login` — não havia produto pra mostrar. Hoje são cinco telas e uma
 * demonstração pública navegável sem cadastro, e a raiz é a landing: oito
 * seções, quatro pontos de cadastro na rolagem (herói, depois das análises,
 * depois do foco em Mercado Livre, e a faixa final).
 *
 * A ordem das seções conta uma história, e mexer nela quebra a história:
 * dor (`Problem`) → o que você vê (`Showcase`) → o que você FAZ com o que
 * viu (`Acoes`) → como começar (`HowItWorks`) → por que só Mercado Livre
 * (`MlFocus`) → e se eu não confiar (`YourData`) → o empurrão (`FinalCta`).
 *
 * Ainda é assíncrona e ainda chama `getUser()`, mas não pra redirecionar —
 * só pra decidir o que o cabeçalho mostra ("Entrar" ou "Ir pro dashboard").
 * Quem já tem sessão e digita o domínio queria ver a página, não ser
 * chutado pra dentro do produto sem escolha.
 */
export default async function Home() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <>
      <LandingHeader loggedIn={!!user} />
      <main>
        <Hero />
        <Problem />
        <Showcase />
        <Acoes />
        <HowItWorks />
        <MlFocus />
        <YourData />
        <FinalCta />
      </main>
      <LandingFooter />
    </>
  );
}
