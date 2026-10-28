// Bateria do guarda: cada caso diz o que DEVE acontecer, liberar ou negar.
//
//   node .claude/hooks/testa_guarda.mjs
//
// Roda sozinho pelo `scripts/verifica.py` quando `.claude/hooks/` muda. Os
// caminhos de arquivo vêm em três formatos (C:\, C:/ e o /c/ do Git Bash)
// porque o primeiro bug do guarda foi exatamente esse: uma comparação de pasta
// que não casava liberava a edição de migration aplicada sem erro nenhum.
//
// O JSON dos casos é montado aqui, e não na linha de comando: o Git Bash
// reescreve barras invertidas nos argumentos, e isso já fez o teste testar
// outra coisa.
import { execFileSync } from "node:child_process";
import { appendFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const guarda = path.join(raiz, ".claude", "hooks", "guarda.mjs");
const repo = path.join(mkdtempSync(path.join(os.tmpdir(), "guarda-")), "repo-teste");

rmSync(repo, { recursive: true, force: true });
mkdirSync(repo, { recursive: true });
const git = (...a) => execFileSync("git", a, { cwd: repo, stdio: "ignore" });
git("init", "-q");
writeFileSync(path.join(repo, "limpo.txt"), "a\n");
writeFileSync(path.join(repo, "sujo.txt"), "b\n");
git("add", ".");
git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x");
appendFileSync(path.join(repo, "sujo.txt"), "mudou\n");

const mig = (nome, sep = path.sep) => [raiz, "backend", "migrations", nome].join(sep);
const raizBarra = raiz.replace(/\\/g, "/");
const raizMsys = raizBarra.replace(/^([A-Za-z]):/, (_, d) => "/" + d.toLowerCase());

const casos = [
  ["deny", "Edit 0012 (separador nativo)", { tool_name: "Edit", tool_input: { file_path: mig("0012_frete_real.sql") } }],
  ["deny", "Edit 0012 (C:/...)", { tool_name: "Edit", tool_input: { file_path: mig("0012_frete_real.sql", "/").replace(/\\/g, "/") } }],
  ["deny", "Edit 0012 (/c/...)", { tool_name: "Edit", tool_input: { file_path: raizMsys + "/backend/migrations/0012_frete_real.sql" } }],
  ["deny", "Write 0001 (maiúsculas trocadas)", { tool_name: "Write", tool_input: { file_path: raizBarra.toLowerCase() + "/Backend/Migrations/0001_init.sql" } }],
  ["allow", "Write 0014 nova", { tool_name: "Write", tool_input: { file_path: mig("0014_nova.sql") } }],
  ["allow", "Edit 0000 stub (só teste)", { tool_name: "Edit", tool_input: { file_path: mig("0000_test_auth_stub.sql") } }],
  ["allow", "Edit APLICADAS.tsv", { tool_name: "Edit", tool_input: { file_path: mig("APLICADAS.tsv") } }],
  ["allow", "Edit README", { tool_name: "Edit", tool_input: { file_path: path.join(raiz, "README.md") } }],
  ["deny", "uvicorn com .env", { tool_name: "Bash", tool_input: { command: "backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --port 10000" } }],
  ["deny", "uvicorn só com worker=0", { tool_name: "Bash", tool_input: { command: "WORKER_IN_PROCESS=0 python -m uvicorn backend.main:app" } }],
  ["allow", "uvicorn banco de teste + worker=0", { tool_name: "Bash", tool_input: { command: "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sellerpulse_test WORKER_IN_PROCESS=0 python -m uvicorn backend.main:app" } }],
  ["allow", "PowerShell banco de teste + worker=0", { tool_name: "PowerShell", tool_input: { command: '$env:DATABASE_URL="postgresql://x@localhost/sellerpulse_test"; $env:WORKER_IN_PROCESS="0"; python -m uvicorn backend.main:app' } }],
  ["deny", "python -m backend.worker", { tool_name: "Bash", tool_input: { command: "python -m backend.worker" } }],
  ["deny", "preview_start backend", { tool_name: "mcp__Claude_Browser__preview_start", tool_input: { name: "backend" } }],
  ["allow", "preview_start backend-teste", { tool_name: "mcp__Claude_Browser__preview_start", tool_input: { name: "backend-teste" } }],
  ["deny", "git push --force", { tool_name: "Bash", tool_input: { command: "git push --force origin main" } }],
  ["deny", "git push -f (composto)", { tool_name: "Bash", tool_input: { command: "cd x && git push -f" } }],
  ["deny", "git push --force-with-lease", { tool_name: "Bash", tool_input: { command: "git push --force-with-lease" } }],
  ["deny", "git push +main", { tool_name: "Bash", tool_input: { command: "git push origin +main" } }],
  ["allow", "git push -q -u", { tool_name: "Bash", tool_input: { command: "git push -q -u origin feat/x" } }],
  ["deny", "checkout -- sujo", { tool_name: "Bash", cwd: repo, tool_input: { command: "git checkout -- sujo.txt" } }],
  ["allow", "checkout -- limpo", { tool_name: "Bash", cwd: repo, tool_input: { command: "git checkout -q -- limpo.txt" } }],
  ["allow", "checkout de branch", { tool_name: "Bash", cwd: repo, tool_input: { command: "git checkout -q -b nova" } }],
  ["deny", "restore sujo", { tool_name: "Bash", cwd: repo, tool_input: { command: "git restore sujo.txt" } }],
  ["allow", "restore --staged sujo", { tool_name: "Bash", cwd: repo, tool_input: { command: "git restore --staged sujo.txt" } }],
  ["deny", "restore . com sujo", { tool_name: "Bash", cwd: repo, tool_input: { command: "git restore ." } }],
  ["deny", "reset --hard com sujo", { tool_name: "Bash", cwd: repo, tool_input: { command: "git reset --hard" } }],
  ["deny", "composto com checkout sujo", { tool_name: "Bash", cwd: repo, tool_input: { command: "ls && git checkout -- sujo.txt; echo ok" } }],
  ["allow", "Read (fora do escopo)", { tool_name: "Read", tool_input: { file_path: "x" } }],
];

let falhas = 0;
for (const [esperado, nome, entrada] of casos) {
  const out = execFileSync("node", [guarda], {
    input: JSON.stringify(entrada),
    env: { ...process.env, CLAUDE_PROJECT_DIR: raiz },
  }).toString();
  const obtido = (out.match(/"permissionDecision":"(\w+)"/) || [, "allow"])[1];
  const interno = out.includes("falhou") ? " (FALHA INTERNA)" : "";
  const ok = obtido === esperado && !interno;
  if (!ok) falhas++;
  console.log(`${ok ? "ok  " : "ERRO"} ${nome.padEnd(36)} esperado=${esperado} obtido=${obtido}${interno}`);
}

// Falha interna tem que liberar com aviso, nunca travar.
const ruim = execFileSync("node", [guarda], { input: "nao e json", env: { ...process.env, CLAUDE_PROJECT_DIR: raiz } }).toString();
const liberou = !/deny/.test(ruim) && /falhou/.test(ruim);
if (!liberou) falhas++;
console.log(`${liberou ? "ok  " : "ERRO"} ${"entrada inválida libera com aviso".padEnd(36)}`);

rmSync(path.dirname(repo), { recursive: true, force: true });
console.log(falhas ? `\n${falhas} caso(s) errado(s)` : "\ntodos os casos certos");
process.exit(falhas ? 1 : 0);
