"use client";

import { useRouter } from "next/navigation";

import { createClient } from "@/lib/supabase/client";

/**
 * `className` existe pelo mesmo motivo do CTA da demo: no trilho de ícones a
 * caixa útil é de 39px (64 do `md:w-16` menos os 12+12 do `p-3`), e "Sair" em
 * `text-sm` com `px-3` mais borda pede 52px — a última letra saía desenhada
 * fora da pílula. Quem sabe em que estágio está é o rodapé da sidebar, não
 * este botão, então a decisão vem de lá.
 */
export function BotaoSair({ className = "" }: { className?: string }) {
  const router = useRouter();

  async function sair() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={sair}
      className={`rounded-lg border border-line py-1.5 font-medium transition hover:bg-surface ${className || "px-3 text-sm"}`}
    >
      Sair
    </button>
  );
}
