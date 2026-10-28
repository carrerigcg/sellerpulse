"""Roda as checagens do CI localmente, num comando só.

    backend/.venv/Scripts/python.exe scripts/verifica.py            # rápido
    backend/.venv/Scripts/python.exe scripts/verifica.py --completo # = CI

O modo **rápido** é o que o agente roda antes de dizer "pronto". Ele olha o que
mudou em relação à `origin/main` (commits da branch mais a árvore de trabalho)
e só roda o que essa mudança pode quebrar:

- ruff check e format nas camadas tocadas;
- a trava de migrations, sempre (custa um segundo e já salvou um deploy);
- pytest do backend só nos arquivos de teste da área: os testes que mudaram e
  os que importam um módulo que mudou;
- vitest, eslint e tsc no front, se o front mudou.

O modo **completo** é o CI inteiro: suíte completa do backend e do legado, e o
build do front. Fica com o CI ou com o Guilherme — a suíte completa do backend
não roda na sessão do agente (ver AGENTS.md).

Usa só a biblioteca padrão, para rodar com qualquer um dos dois interpretadores.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WINDOWS = sys.platform == "win32"
BIN = "Scripts" if WINDOWS else "bin"
PY_LEGADO = RAIZ / ".venv" / BIN / ("python.exe" if WINDOWS else "python")
PY_BACKEND = RAIZ / "backend" / ".venv" / BIN / ("python.exe" if WINDOWS else "python")
NPM = shutil.which("npm") or "npm"


def _git(*args: str) -> list[str]:
    saida = subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=False
    ).stdout
    return [linha.strip() for linha in saida.splitlines() if linha.strip()]


def arquivos_mudados() -> list[str]:
    """Commits da branch desde a origin/main, mais o que não foi commitado."""
    base = _git("merge-base", "HEAD", "origin/main")
    na_branch = _git("diff", "--name-only", f"{base[0]}...HEAD") if base else []
    na_arvore = _git("diff", "--name-only", "HEAD")
    novos = _git("ls-files", "--others", "--exclude-standard")
    return sorted(set(na_branch + na_arvore + novos))


def testes_do_backend(mudados: list[str]) -> list[str]:
    """Arquivos de teste que a mudança pode quebrar.

    Os testes que mudaram, mais os que mencionam um módulo do backend que
    mudou (`from backend.ml.frete_pg import ...` cita `frete_pg`). É uma
    aproximação de propósito: pegar teste a mais custa segundos, e o CI roda a
    suíte inteira de qualquer jeito.
    """
    pasta = RAIZ / "backend" / "tests"
    escolhidos = {m for m in mudados if m.startswith("backend/tests/test_") and m.endswith(".py")}
    modulos = {
        Path(m).stem
        for m in mudados
        if m.startswith("backend/") and m.endswith(".py") and not m.startswith("backend/tests/")
    }
    if modulos:
        padrao = re.compile(r"\b(" + "|".join(map(re.escape, sorted(modulos))) + r")\b")
        for teste in pasta.glob("test_*.py"):
            if padrao.search(teste.read_text(encoding="utf-8")):
                escolhidos.add(teste.relative_to(RAIZ).as_posix())
    return sorted(e for e in escolhidos if (RAIZ / e).exists())


class Placar:
    def __init__(self) -> None:
        self.linhas: list[tuple[str, str, float]] = []

    def roda(self, nome: str, comando: list[str], cwd: Path = RAIZ) -> bool:
        print(f"\n=== {nome}\n$ {' '.join(map(str, comando))}", flush=True)
        inicio = time.monotonic()
        try:
            ok = subprocess.run(comando, cwd=cwd, check=False).returncode == 0
        except FileNotFoundError as exc:
            print(f"não achei o executável: {exc}")
            ok = False
        self.linhas.append((nome, "ok" if ok else "FALHOU", time.monotonic() - inicio))
        return ok

    def pula(self, nome: str, motivo: str) -> None:
        self.linhas.append((nome, f"pulado: {motivo}", 0.0))

    def resumo(self) -> bool:
        print("\n=== resumo")
        for nome, estado, segundos in self.linhas:
            tempo = f"{segundos:5.1f}s" if segundos else "      "
            print(f"  {estado:<40} {tempo}  {nome}")
        return all(not estado.startswith("FALHOU") for _, estado, _ in self.linhas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--completo", action="store_true", help="roda tudo, como o CI")
    completo = parser.parse_args().completo

    mudados = arquivos_mudados()
    toca = {
        "backend": any(m.startswith(("backend/", "scripts/")) for m in mudados),
        "legado": any(m.startswith(("src/", "tests/")) for m in mudados),
        "front": any(m.startswith("frontend/") for m in mudados),
    }
    print(f"modo: {'completo' if completo else 'rápido'} — {len(mudados)} arquivo(s) mudado(s)")

    p = Placar()

    if completo or toca["legado"]:
        p.roda("ruff check (legado)", [str(PY_LEGADO), "-m", "ruff", "check", "src", "tests"])
        p.roda(
            "ruff format (legado)",
            [str(PY_LEGADO), "-m", "ruff", "format", "--check", "src", "tests"],
        )
    else:
        p.pula("ruff (legado)", "src/ e tests/ não mudaram")

    if completo or toca["backend"]:
        p.roda(
            "ruff check (backend)", [str(PY_BACKEND), "-m", "ruff", "check", "backend", "scripts"]
        )
        p.roda(
            "ruff format (backend)",
            [str(PY_BACKEND), "-m", "ruff", "format", "--check", "backend", "scripts"],
        )
    else:
        p.pula("ruff (backend)", "backend/ e scripts/ não mudaram")

    p.roda("migrations aplicadas", [str(PY_BACKEND), "backend/scripts/checa_migrations.py"])

    # O guarda barra ações sem ninguém olhar; um erro nele libera o que devia
    # negar em silêncio. Por isso a bateria roda sempre que ele muda.
    if completo or any(m.startswith(".claude/hooks/") for m in mudados):
        p.roda("guarda (hooks)", ["node", ".claude/hooks/testa_guarda.mjs"])
    else:
        p.pula("guarda (hooks)", ".claude/hooks/ não mudou")

    if completo:
        p.roda(
            "pytest backend (completo)", [str(PY_BACKEND), "-m", "pytest", "backend/tests", "-q"]
        )
        p.roda("pytest legado (completo)", [str(PY_LEGADO), "-m", "pytest", "-q"])
    else:
        testes = testes_do_backend(mudados)
        if testes:
            p.roda(
                f"pytest backend ({len(testes)} arquivo(s) da área)",
                [str(PY_BACKEND), "-m", "pytest", *testes, "-q"],
            )
        elif any(m.startswith("backend/") and m.endswith(".py") for m in mudados):
            p.pula("pytest backend", "nenhum teste cita o .py que mudou — confira à mão")
        else:
            p.pula("pytest backend", "nenhum .py do backend mudou")
        if toca["legado"]:
            p.roda("pytest legado", [str(PY_LEGADO), "-m", "pytest", "-q"])

    front = RAIZ / "frontend"
    if completo or toca["front"]:
        p.roda("vitest", [NPM, "test"], cwd=front)
        p.roda("eslint", [NPM, "run", "lint"], cwd=front)
        if completo:
            p.roda("build (inclui tipos)", [NPM, "run", "build"], cwd=front)
        else:
            p.roda("tsc", [NPM, "exec", "--", "tsc", "--noEmit"], cwd=front)
    else:
        p.pula("front", "frontend/ não mudou")

    ok = p.resumo()
    print("\ntudo verde" if ok else "\nhá falha — não está pronto")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
