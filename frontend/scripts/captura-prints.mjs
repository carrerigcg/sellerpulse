// frontend/scripts/captura-prints.mjs
/**
 * Regera os prints da vitrine a partir da demonstracao rodando local.
 *
 * POR QUE ISTO EXISTE
 *
 * Os prints de `public/landing/` foram capturados a mao e envelheceram em
 * silencio: quando custo de produto, cobertura e Desempenho dos anuncios
 * entraram no produto, a vitrine continuou mostrando as telas de antes.
 * Ninguem percebeu porque regerar era um ritual manual que so uma pessoa
 * sabia fazer. Com um comando, regerar deixa de depender de memoria.
 *
 * COMO USAR
 *
 *   1. Suba o backend de teste com o seller de demonstracao semeado
 *      (`backend-teste` no .claude/launch.json aponta pro banco de teste).
 *   2. npm run build && rm -rf .next/cache/fetch-cache && npx next start -p 3100
 *   3. npm run prints
 *
 * DUAS ARMADILHAS, as duas descobertas gerando print errado em silencio:
 *
 * SEMEIE COM `regenera_demo`, NAO COM `seed_seller.py`. O script de seed
 * ancora as datas em `ANCHOR_DATE` (1/8/2026, fixo), e a janela padrao da
 * demo e "ultimos 90 dias ate hoje" -- a tela sai com uma dezena de dias de
 * pedido e "-84%" em todos os KPIs. `backend/demo_refresh.regenera_demo`
 * aceita `anchor=datetime.now(UTC)`, que e o que producao usa, e a tela fica
 * com o periodo cheio.
 *
 * APAGUE `.next/cache/fetch-cache` ANTES DE SERVIR. `lib/demo.ts` pede
 * `revalidate: 3600` de proposito (o Render hiberna). Com o cache quente, o
 * servidor devolve o dado da execucao anterior e os prints saem iguaizinhos
 * aos de antes -- mesmo tamanho em bytes, nenhum erro. Foi exatamente assim
 * que a vitrine envelheceu da primeira vez.
 *
 * BUILD DE PRODUCAO, NAO `next dev`: o servidor de desenvolvimento desenha um
 * selo flutuante no canto inferior esquerdo que sai no print. O visitante
 * nunca ve esse selo, entao um print com ele e a foto de algo que nao existe.
 *
 * POR QUE O PROTOCOLO DE DEVTOOLS, E NAO A FLAG `--screenshot`
 *
 * A flag so fotografa o topo da pagina. O funil mora no fim de uma pagina
 * longa, e pedir a ancora (`#desempenho-anuncios`) faz o Chrome rolar mas
 * fotografar a superficie antes de pintar: sai um PNG branco de 5851 bytes,
 * com codigo de saida 0 e nenhum aviso. Medido duas vezes, com o mesmo
 * tamanho exato nas duas.
 *
 * O protocolo resolve com `captureBeyondViewport`, que recorta qualquer
 * retangulo da pagina sem rolar nada -- e dai da pra enquadrar um ELEMENTO,
 * que e melhor enquadramento do que "os primeiros 900 pixels".
 *
 * Sem Playwright e sem Puppeteer: usa o Chrome ja instalado e o WebSocket
 * nativo do Node (>= 22). Nenhuma dependencia nova no package.json.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.env.PRINTS_BASE_URL ?? "http://localhost:3100";
const DESTINO = "public/landing";

const CAMINHOS_DO_CHROME = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);

/**
 * `altura` e o viewport da captura. Sem `seletor`, o print e o viewport
 * inteiro a partir do topo -- e essas dimensoes precisam bater com o que
 * `showcase.tsx` declara, ou o Next reserva o espaco errado e a pagina pula
 * ao carregar (CLS).
 *
 * Com `seletor`, o print e o retangulo daquele elemento mais uma folga, e a
 * altura final sai do proprio conteudo. Quem for declarar esse arquivo num
 * componente precisa ler a dimensao real depois de gerar.
 */
const ALVOS = [
  { arquivo: "demo-executive.png", rota: "/demo/financeiro", largura: 1440, altura: 900 },
  { arquivo: "demo-executive-mobile.png", rota: "/demo/financeiro", largura: 602, altura: 1100 },
  { arquivo: "demo-produtos.png", rota: "/demo/produtos", largura: 1440, altura: 900 },
  { arquivo: "demo-produtos-mobile.png", rota: "/demo/produtos", largura: 602, altura: 1100 },
  { arquivo: "demo-clientes.png", rota: "/demo/clientes", largura: 1440, altura: 900 },
  { arquivo: "demo-clientes-mobile.png", rota: "/demo/clientes", largura: 602, altura: 1100 },
  {
    arquivo: "demo-funil.png",
    rota: "/demo/produtos",
    largura: 1440,
    altura: 1200,
    seletor: "#desempenho-anuncios",
    folga: 16,
    // A secao inteira tem ~2200px: a tabela lista o catalogo todo. Para a
    // vitrine o que convence sao os quatro numeros do topo, os chips com a
    // contagem de cada diagnostico e as primeiras linhas -- o resto e
    // repeticao que so aumenta o arquivo.
    alturaMaxima: 820,
  },
  {
    // Recorte proprio pro celular, pela mesma razao do `browser-frame.tsx`:
    // encolher o de 1136px ate caber em ~340px deixa a tabela ilegivel. A
    // 602px a pagina ja serve o layout estreito, entao o texto nasce perto do
    // tamanho em que vai ser lido.
    arquivo: "demo-funil-mobile.png",
    rota: "/demo/produtos",
    largura: 602,
    altura: 1100,
    seletor: "#desempenho-anuncios",
    folga: 12,
    alturaMaxima: 900,
  },
];

const espera = (ms) => new Promise((r) => setTimeout(r, ms));

function achaChrome() {
  const encontrado = CAMINHOS_DO_CHROME.find((c) => existsSync(c));
  if (!encontrado) {
    throw new Error(
      `Chrome nao encontrado. Tentei:\n  ${CAMINHOS_DO_CHROME.join("\n  ")}\n` +
        "Aponte o executavel com CHROME_PATH=... npm run prints",
    );
  }
  return encontrado;
}

async function confereServidor() {
  try {
    const r = await fetch(`${BASE}/demo`, { signal: AbortSignal.timeout(15000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  } catch (erro) {
    throw new Error(
      `Nao consegui carregar ${BASE}/demo (${erro.message}).\n` +
        "Suba o build de producao antes:  npm run build && npx next start -p 3100\n" +
        "E confira que o backend de teste esta no ar com o seller semeado.",
    );
  }
}

/** Sobe o Chrome headless e devolve o endereco do protocolo. */
async function sobeChrome(chrome) {
  // Perfil descartavel: reaproveitar diretorio entre execucoes ja devolveu
  // print em branco, sem erro nenhum.
  const perfil = mkdtempSync(join(tmpdir(), "sellerpulse-print-"));
  const processo = spawn(chrome, [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--remote-debugging-port=0",
    `--user-data-dir=${perfil}`,
  ]);

  // A porta escolhida so aparece no stderr. Sem ler dali seria preciso fixar
  // uma porta e torcer pra ela estar livre.
  const endereco = await new Promise((resolve, reject) => {
    const prazo = setTimeout(() => reject(new Error("Chrome nao anunciou a porta em 30s")), 30000);
    processo.stderr.on("data", (bloco) => {
      const achado = /ws:\/\/\S+/.exec(String(bloco));
      if (achado) {
        clearTimeout(prazo);
        resolve(achado[0]);
      }
    });
    processo.on("exit", (codigo) => {
      clearTimeout(prazo);
      reject(new Error(`Chrome saiu antes de subir (codigo ${codigo})`));
    });
  });

  return { processo, perfil, endereco };
}

/** Cliente minimo do protocolo: manda comando, casa a resposta pelo id. */
function abreSessao(endereco) {
  const soquete = new WebSocket(endereco);
  const pendentes = new Map();
  let proximoId = 0;

  const pronto = new Promise((resolve, reject) => {
    soquete.addEventListener("open", resolve, { once: true });
    soquete.addEventListener("error", () => reject(new Error("falha no WebSocket")), {
      once: true,
    });
  });

  soquete.addEventListener("message", (evento) => {
    const msg = JSON.parse(evento.data);
    const aguardando = pendentes.get(msg.id);
    if (!aguardando) return;
    pendentes.delete(msg.id);
    if (msg.error) aguardando.reject(new Error(msg.error.message));
    else aguardando.resolve(msg.result);
  });

  return {
    pronto,
    manda(metodo, params = {}, sessionId) {
      const id = ++proximoId;
      return new Promise((resolve, reject) => {
        pendentes.set(id, { resolve, reject });
        soquete.send(JSON.stringify({ id, method: metodo, params, ...(sessionId && { sessionId }) }));
      });
    },
    fecha: () => soquete.close(),
  };
}

async function recorteDoElemento(sessao, sessionId, seletor, folga, alturaMaxima) {
  const { result } = await sessao.manda(
    "Runtime.evaluate",
    {
    expression: `(() => {
      const el = document.querySelector(${JSON.stringify(seletor)});
      if (!el) return "null";
      const r = el.getBoundingClientRect();
      return JSON.stringify({ x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height });
    })()`,
      returnByValue: true,
    },
    sessionId,
  );

  const caixa = JSON.parse(result.value);
  if (!caixa) throw new Error(`seletor ${seletor} nao existe nesta rota`);

  return {
    x: Math.max(0, caixa.x - folga),
    y: Math.max(0, caixa.y - folga),
    width: caixa.w + folga * 2,
    height: Math.min(caixa.h + folga * 2, alturaMaxima ?? Infinity),
    scale: 1,
  };
}

async function captura(sessao, sessionId, alvo) {
  await sessao.manda(
    "Emulation.setDeviceMetricsOverride",
    {
    width: alvo.largura,
    height: alvo.altura,
    deviceScaleFactor: 1,
    // Abaixo de 768px o Tailwind serve o layout de celular. Sem marcar como
    // movel, o Chrome entrega a versao estreita do layout de desktop.
      mobile: alvo.largura < 768,
    },
    sessionId,
  );

  await sessao.manda("Page.navigate", { url: `${BASE}${alvo.rota}` }, sessionId);
  // O evento de load nao cobre a animacao de entrada dos graficos; sem a
  // pausa, barras e linhas saem pela metade.
  await espera(3500);

  const recorte = alvo.seletor
    ? await recorteDoElemento(sessao, sessionId, alvo.seletor, alvo.folga ?? 0, alvo.alturaMaxima)
    : null;

  const { data } = await sessao.manda(
    "Page.captureScreenshot",
    {
      format: "png",
      ...(recorte ? { clip: recorte, captureBeyondViewport: true } : {}),
    },
    sessionId,
  );

  const caminho = join(DESTINO, alvo.arquivo);
  writeFileSync(caminho, Buffer.from(data, "base64"));
  return caminho;
}

const chrome = achaChrome();
await confereServidor();
console.log(`Chrome:   ${chrome}`);
console.log(`Servidor: ${BASE}\n`);

const { processo, perfil, endereco } = await sobeChrome(chrome);
const sessao = abreSessao(endereco);
await sessao.pronto;

// O socket que o Chrome anuncia no stderr e o do NAVEGADOR: ele so conhece
// `Target`/`Browser`, e um `Page.enable` ali volta "wasn't found". Entao abre
// uma aba e anexa nela; `flatten` faz as respostas virem por este mesmo
// socket, casadas por `sessionId`.
const { targetId } = await sessao.manda("Target.createTarget", { url: "about:blank" });
const { sessionId } = await sessao.manda("Target.attachToTarget", { targetId, flatten: true });
await sessao.manda("Page.enable", {}, sessionId);

let suspeitos = 0;
try {
  for (const alvo of ALVOS) {
    const caminho = await captura(sessao, sessionId, alvo);
    const kb = Math.round(statSync(caminho).size / 1024);
    // Print em branco pesa ~6 KB. Avisar e melhor que gravar e seguir calado.
    const alerta = kb < 15 ? "  <-- SUSPEITO: pode estar em branco" : "";
    if (alerta) suspeitos += 1;
    console.log(`  ${alvo.arquivo.padEnd(28)} ${kb} KB${alerta}`);
  }
} finally {
  sessao.fecha();
  processo.kill();
  // No Windows o `kill` volta antes de o Chrome soltar o perfil, e o apagar
  // falha com EPERM -- derrubando o script DEPOIS de os prints ja estarem
  // gravados. Lixo em %TEMP% nao justifica perder a execucao inteira.
  try {
    rmSync(perfil, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  } catch {
    console.warn(`  (perfil temporario ficou em ${perfil} -- o Windows ainda o segurava)`);
  }
}

console.log(
  suspeitos ? `\n${suspeitos} print(s) suspeito(s) -- confira antes de commitar.` : "\nPronto.",
);
