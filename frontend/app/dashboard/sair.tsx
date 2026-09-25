"use client";

import { useRouter } from "next/navigation";

import { createClient } from "@/lib/supabase/client";

export function BotaoSair() {
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
      className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium transition hover:bg-surface"
    >
      Sair
    </button>
  );
}
