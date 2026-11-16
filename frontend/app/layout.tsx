import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { URL_DO_SITE } from "@/lib/site";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// `metadataBase`: a prévia do link compartilhado (WhatsApp, LinkedIn) monta
// as URLs absolutas a partir dele.
export const metadata: Metadata = {
  metadataBase: new URL(URL_DO_SITE),
  title: "SellerPulse",
  description:
    "Analytics para vendedores do Mercado Livre — receita, produtos e clientes em um só lugar.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
