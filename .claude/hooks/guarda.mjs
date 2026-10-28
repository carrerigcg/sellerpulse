// Guarda do SellerPulse: hook PreToolUse que barra as três ações que já
// custaram caro aqui e que não podem depender de alguém lembrar a regra.
//
//   1. Editar uma migration já aplicada em produção (APLICADAS.tsv).
//   2. Subir o backend com o `backend/.env` — o worker vem LIGADO por padrão e
//      o `.env` aponta para a Supabase de produção.
//   3. `git push --force`, e `git checkout -- <arq>` / `git restore` /
//      `git reset --hard` com mudança não commitada: em 2026-10-27 um
//      `git checkout --` usado para desfazer uma mutação apagou o conserto.
//
// Recebe o JSON da ferramenta no stdin. Para negar, devolve
// `permissionDecision: "deny"` com o motivo E o que fazer no lugar — o motivo
// volta para o agente, e sem a alternativa ele só tenta de novo.
//
// Erro interno do próprio guarda LIBERA a ação, com aviso. Um guarda com bug
// que bloqueia tudo pararia o trabalho inteiro em silêncio.

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

const nega = (motivo) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: `[guarda do SellerPulse] ${motivo}`,
      },
    }),
  );
  process.exit(0);
};

const raizDoProjeto = () => process.env.CLAUDE_PROJECT_DIR || process.cwd();

// O mesmo arquivo chega como `C:\Users\...`, `C:/Users/...` ou, vindo do Git
// Bash, `/c/Users/...`. Sem normalizar, a comparação de pasta falha em
// silêncio e a guarda libera exatamente o que devia barrar (pego no teste).
const normaliza = (p) =>
  path
    .resolve(p.replace(/^\/([a-z])\//i, "$1:/"))
    .replace(/\\/g, "/")
    .toLowerCase();

// ---------- 1. migration aplicada ----------

function migrationsAplicadas() {
  const tsv = readFileSync(
    path.join(raizDoProjeto(), "backend", "migrations", "APLICADAS.tsv"),
    "utf8",
  );
  return new Set(
    tsv
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#") && !l.startsWith("!"))
      .map((l) => l.split("\t")[0]),
  );
}

function checaMigration(entrada) {
  const arquivo = entrada.tool_input?.file_path || entrada.tool_input?.notebook_path;
  if (!arquivo) return;
  const pasta = normaliza(path.join(raizDoProjeto(), "backend", "migrations"));
  if (!normaliza(arquivo).startsWith(pasta + "/")) return;
  const nome = path.basename(arquivo);
  if (migrationsAplicadas().has(nome)) {
    nega(
      `${nome} já está aplicada em produção (APLICADAS.tsv). Reescrever uma ` +
        "migration aplicada faz o repo mentir sobre o banco. Crie uma migration " +
        "nova com o próximo número (ver docs/operacao.md, seção 4).",
    );
  }
}

// ---------- 2 e 3. comandos de shell ----------

// Separa o comando em trechos por ; && || | e quebra de linha. Não é um parser
// de shell, e não precisa ser: o objetivo é achar o `git ...` ou o `uvicorn`
// dentro de uma linha composta.
const trechos = (comando) => comando.split(/&&|\|\||[;|\n]/).map((t) => t.trim()).filter(Boolean);

function checaBackend(comando) {
  const sobeBackend =
    (/uvicorn/.test(comando) && /backend\.main/.test(comando)) ||
    /-m\s+backend\.worker\b/.test(comando);
  if (!sobeBackend) return;
  const workerDesligado = /WORKER_IN_PROCESS['"]?\]?\s*=\s*['"]?0\b/.test(comando);
  const bancoDeTeste = /sellerpulse_test/.test(comando);
  if (!(workerDesligado && bancoDeTeste)) {
    nega(
      "Subir o backend sem DATABASE_URL apontando para sellerpulse_test E sem " +
        "WORKER_IN_PROCESS=0 liga o worker contra a Supabase de PRODUÇÃO (o " +
        "default é 1 e o backend/.env aponta para lá). Use a config " +
        "`backend-teste` do .claude/launch.json, ou passe as duas variáveis no " +
        "comando (ver docs/operacao.md, seção 1).",
    );
  }
}

function checaPushForcado(trecho) {
  if (!/^git\s+push\b/.test(trecho)) return;
  if (/(^|\s)(--force(-with-lease)?(=\S*)?|-f|--mirror)(\s|$)/.test(trecho) || /\s\+\S+/.test(trecho)) {
    nega(
      "Push forçado reescreve histórico publicado, e a `main` publica em " +
        "produção. Se a branch divergiu, traga a base (merge ou rebase local) e " +
        "faça push normal. Se for mesmo necessário, o Guilherme roda à mão.",
    );
  }
}

function sujos(cwd, caminhos) {
  try {
    const saida = execFileSync("git", ["status", "--porcelain", "--", ...caminhos], {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return saida
      .split(/\r?\n/)
      .filter((l) => l && !l.startsWith("??"))
      .map((l) => l.slice(3));
  } catch {
    return [];
  }
}

const SEM_PERDER =
  "Para desfazer uma mutação, restaure da cópia que você fez antes " +
  "(`cp \"$TEMP/x.bak\" arquivo`) e confira com `diff -q` — ver " +
  "docs/operacao.md, seção 3. Se quer mesmo descartar, commite ou faça " +
  "`git stash` antes, e diga ao Guilherme o que foi descartado.";

function checaDescarte(trecho, cwd) {
  let caminhos = null;

  const checkout = trecho.match(/^git\s+checkout\b(.*)$/);
  if (checkout) {
    const partes = checkout[1].split(/\s+--\s+/);
    if (partes.length < 2) return; // troca de branch: o git já recusa se for perder algo
    caminhos = partes[1].split(/\s+/).filter(Boolean);
  }

  const restore = trecho.match(/^git\s+restore\b(.*)$/);
  if (restore) {
    const args = restore[1].split(/\s+/).filter(Boolean);
    const soStage = args.includes("--staged") && !args.includes("--worktree") && !args.includes("-W");
    if (soStage) return; // só tira do stage, não toca no arquivo
    const semOpcoes = [];
    for (let i = 0; i < args.length; i++) {
      if (args[i] === "--source" || args[i] === "-s") i++;
      else if (!args[i].startsWith("-")) semOpcoes.push(args[i]);
    }
    caminhos = semOpcoes.length ? semOpcoes : ["."];
  }

  if (/^git\s+reset\b.*--hard\b/.test(trecho)) caminhos = ["."];

  if (!caminhos) return;
  const perdidos = sujos(cwd, caminhos.map((c) => c.replace(/^["']|["']$/g, "")));
  if (perdidos.length) {
    nega(
      `Isto apagaria mudança não commitada em: ${perdidos.slice(0, 5).join(", ")}` +
        `${perdidos.length > 5 ? " e mais" : ""}. ${SEM_PERDER}`,
    );
  }
}

function checaShell(entrada) {
  const comando = entrada.tool_input?.command || "";
  checaBackend(comando);
  const cwd = entrada.cwd || raizDoProjeto();
  for (const t of trechos(comando)) {
    checaPushForcado(t);
    checaDescarte(t, cwd);
  }
}

// ---------- preview do backend de produção ----------

function checaPreview(entrada) {
  if (entrada.tool_input?.name === "backend") {
    nega(
      "A config `backend` sobe o servidor com o backend/.env de produção e o " +
        "worker ligado. Use `backend-teste` (banco local, worker desligado).",
    );
  }
}

// ---------- entrada ----------

try {
  const entrada = JSON.parse(readFileSync(0, "utf8") || "{}");
  const ferramenta = entrada.tool_name || "";
  if (/^(Edit|Write|MultiEdit|NotebookEdit)$/.test(ferramenta)) checaMigration(entrada);
  else if (/^(Bash|PowerShell)$/.test(ferramenta)) checaShell(entrada);
  else if (ferramenta === "mcp__Claude_Browser__preview_start") checaPreview(entrada);
} catch (erro) {
  process.stdout.write(
    JSON.stringify({ systemMessage: `guarda do SellerPulse falhou e liberou a ação: ${erro.message}` }),
  );
}
process.exit(0);
