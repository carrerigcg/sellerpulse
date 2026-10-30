import { readFile } from "node:fs/promises";
import path from "node:path";

import Link from "next/link";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Wordmark } from "@/components/brand";

/** Sem `html` no Markdown: o texto é nosso, mas nada aqui precisa dele. */
const ELEMENTOS = {
  h1: (p: React.ComponentProps<"h1">) => (
    <h1 className="text-3xl font-semibold tracking-tight" {...p} />
  ),
  h2: (p: React.ComponentProps<"h2">) => <h2 className="mt-10 text-xl font-semibold" {...p} />,
  h3: (p: React.ComponentProps<"h3">) => <h3 className="mt-6 font-semibold" {...p} />,
  p: (p: React.ComponentProps<"p">) => <p className="mt-3 leading-relaxed" {...p} />,
  ul: (p: React.ComponentProps<"ul">) => <ul className="mt-3 list-disc space-y-2 pl-5" {...p} />,
  a: (p: React.ComponentProps<"a">) => (
    <a className="font-medium text-accent underline hover:text-accent-hover" {...p} />
  ),
  // A rolagem fica na tabela: a página não pode rolar de lado no celular.
  table: (p: React.ComponentProps<"table">) => (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[32rem] border-collapse text-left text-sm" {...p} />
    </div>
  ),
  th: (p: React.ComponentProps<"th">) => (
    <th className="border border-line bg-surface px-3 py-2 font-semibold" {...p} />
  ),
  td: (p: React.ComponentProps<"td">) => <td className="border border-line px-3 py-2" {...p} />,
};

export async function TextoLegal({ arquivo }: { arquivo: string }) {
  const texto = await readFile(path.join(process.cwd(), "content/legal", arquivo), "utf-8");
  return (
    <main className="min-h-screen bg-bg px-4 py-10 text-ink sm:px-6">
      <article className="mx-auto max-w-3xl">
        <Link href="/" aria-label="Página inicial" className="mb-10 inline-block">
          <Wordmark />
        </Link>
        <Markdown remarkPlugins={[remarkGfm]} components={ELEMENTOS}>
          {texto}
        </Markdown>
      </article>
    </main>
  );
}
