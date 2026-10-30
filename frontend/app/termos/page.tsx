import type { Metadata } from "next";

import { TextoLegal } from "@/components/legal/texto-legal";

export const metadata: Metadata = { title: "Termos de Uso · SellerPulse" };

export default function TermosPage() {
  return <TextoLegal arquivo="termos-de-uso.md" />;
}
