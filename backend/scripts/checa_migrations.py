"""Recusa migration que exista no repo e nao esteja registrada como aplicada.

POR QUE ISTO EXISTE

Em 2026-10-14 a feature de custo de produto foi mergeada na main com o codigo
ja consultando `product_costs` -- e a tabela nao existia em producao. Nada
falhou: `ruff`, 166 testes e o build passaram, porque o banco de TESTE tinha a
migration aplicada e o de producao nao. O deploy teria derrubado o dashboard e
a demo publica com erro de relacao inexistente.

A assimetria e a armadilha: o banco de teste e reconstruido por
`setup_test_db.py` a cada CI, entao ele SEMPRE tem a migration nova. Producao
so tem o que alguem aplicou a mao. Nenhum teste podia ver a diferenca, porque
nenhum teste fala com producao -- e nao deve falar.

O QUE ESTE SCRIPT GARANTE, E O QUE NAO GARANTE

Garante que ninguem ESQUECA de aplicar. Nao garante que ninguem MINTA: a linha
do registro e escrita a mao. Uma checagem ao vivo contra o banco pegaria os
dois casos, ao custo de dar o DATABASE_URL de producao ao GitHub Actions --
preco alto demais para o problema, que foi esquecimento.

Uso (da raiz do repo):
    python backend/scripts/checa_migrations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MIGRATIONS = RAIZ / "backend" / "migrations"
REGISTRO = MIGRATIONS / "APLICADAS.tsv"

# Prefixo que marca migration que NUNCA vai para producao (stub do banco de
# teste). Sem isso, `0000_test_auth_stub.sql` apareceria para sempre como
# pendente e o aviso viraria ruido que se aprende a ignorar.
SO_TESTE = "!"


def le_registro(texto: str) -> tuple[set[str], set[str]]:
    """Devolve (aplicadas_em_producao, so_no_banco_de_teste).

    Linhas em branco e comecadas por `#` sao ignoradas. Cada linha de dado e
    `arquivo<TAB>version<TAB>data`; so o arquivo e usado na comparacao, mas as
    outras colunas ficam no registro porque sao o que permite CONFERIR a
    afirmacao contra `supabase_migrations.schema_migrations`.
    """
    aplicadas: set[str] = set()
    so_teste: set[str] = set()
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if linha.startswith(SO_TESTE):
            so_teste.add(linha[len(SO_TESTE) :].strip())
            continue
        aplicadas.add(linha.split("\t")[0].strip())
    return aplicadas, so_teste


def divergencias(
    arquivos: set[str], aplicadas: set[str], so_teste: set[str]
) -> tuple[set[str], set[str]]:
    """Devolve (nao_registradas, registradas_que_sumiram).

    O segundo caso importa tanto quanto o primeiro: uma migration apagada do
    repo mas ainda listada aqui significa que o registro descreve um banco que
    ninguem mais consegue reproduzir.
    """
    conhecidas = aplicadas | so_teste
    return arquivos - conhecidas, conhecidas - arquivos


def main() -> int:
    if not REGISTRO.exists():
        print(f"ERRO: registro nao encontrado em {REGISTRO}", file=sys.stderr)
        return 1

    arquivos = {p.name for p in MIGRATIONS.glob("*.sql")}
    aplicadas, so_teste = le_registro(REGISTRO.read_text(encoding="utf-8"))
    nao_registradas, sumiram = divergencias(arquivos, aplicadas, so_teste)

    if not nao_registradas and not sumiram:
        print(
            f"ok: {len(aplicadas)} migrations registradas como aplicadas em producao"
            f" e {len(so_teste)} marcadas como so-de-teste"
        )
        return 0

    if nao_registradas:
        print("ERRO: migration no repo que nao esta registrada:", file=sys.stderr)
        for nome in sorted(nao_registradas):
            print(f"  - {nome}", file=sys.stderr)
        print(
            "\nAplique em producao e acrescente a linha em"
            f" {REGISTRO.relative_to(RAIZ)}, ou marque com '{SO_TESTE}' se ela nunca"
            " deve sair do banco de teste.\n"
            "\nSe isto for mergeado sem aplicar, o deploy quebra com"
            ' "relation does not exist" -- os testes NAO pegam, porque o banco de'
            " teste e reconstruido do zero a cada CI e sempre tem a migration nova.",
            file=sys.stderr,
        )

    if sumiram:
        print("\nERRO: registro aponta para migration que nao existe mais:", file=sys.stderr)
        for nome in sorted(sumiram):
            print(f"  - {nome}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
