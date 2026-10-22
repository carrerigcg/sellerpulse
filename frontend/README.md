# Frontend do SellerPulse

Next.js 16 (App Router), React 19, TypeScript e Tailwind. Publicado na Vercel.

A visão geral do produto está no [`README.md`](../README.md) da raiz, e as
convenções e armadilhas do projeto no [`CLAUDE.md`](../CLAUDE.md).

## Rodando

```bash
npm ci
npm run dev        # http://localhost:3000
```

Use **npm**. O `package-lock.json` é o que a CI instala com `npm ci`;
`yarn`, `pnpm` e `bun` ignoram esse arquivo e resolvem versões por conta
própria, então não reproduzem o que a CI roda.

**No Windows, prefira `npm ci` a `npm install`.** O `npm install` rodado no
Windows **poda** `@emnapi/core` e `@emnapi/runtime` do topo do lockfile — os
dois só são alcançáveis por pacotes opcionais de outra plataforma — e o
`npm ci` da CI, em Linux, recusa o lockfile podado com `EUSAGE`. O `npm ci`
não reescreve o lockfile, então não cai nisso. Se precisar de `npm install`
para adicionar dependência, confira o diff do lockfile antes de commitar: nada
que existia nele pode desaparecer. Detalhes no comentário do passo
`npm ci` em `.github/workflows/tests.yml`.

O front lê a API de `NEXT_PUBLIC_API_URL` (ver `.env.local.example`). Para
desenvolver contra o backend local, suba-o com `DATABASE_URL` apontando para o
banco de teste e `WORKER_IN_PROCESS=0`. **Não** suba com o `backend/.env`
puro: ele aponta para a Supabase de produção, e o worker vem ligado por
padrão — drenaria a fila de verdade.

## Verificação

```bash
npm test && npm run lint && npm run build
```

O `build` **não** prova que as páginas funcionam. As rotas de `/dashboard` e
`/demo` são dinâmicas (`ƒ`) e nunca são renderizadas no build — um erro de
fronteira RSC passa por `lint` e `build` e só aparece no navegador. Abrir a
página faz parte da verificação.

## Prints da vitrine

```bash
npm run build && rm -rf .next/cache/fetch-cache && npx next start -p 3100
npm run prints
```

Regenera `public/landing/` a partir da demonstração rodando local. O passo a
passo, e as armadilhas que fazem o print sair errado sem erro nenhum, estão
no topo de `scripts/captura-prints.mjs`.
