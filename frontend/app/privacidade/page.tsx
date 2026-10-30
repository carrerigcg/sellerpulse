import type { Metadata } from "next";

import { TextoLegal } from "@/components/legal/texto-legal";

export const metadata: Metadata = { title: "Política de Privacidade · SellerPulse" };

export default function PrivacidadePage() {
  return <TextoLegal arquivo="politica-de-privacidade.md" />;
}
