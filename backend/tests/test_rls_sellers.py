"""`sellers` nao pode ter policy de escrita para o papel do navegador.

A chave anon do Supabase vai no frontend, e a API REST automatica do Supabase
(PostgREST) aceita um `PATCH /sellers` de qualquer usuario logado. Com a
`sellers_update_own` da 0002 (sem `with check`, sem restricao de coluna), o
vendedor conseguia reescrever as colunas que so o backend deve gravar:
`ml_seller_id`, `ml_nickname`, `is_demo` e `last_synced_at`. O backend entra
pelo papel `postgres`, que nao passa por RLS, entao nenhum caminho legitimo
precisa dessa policy; o frontend usa o Supabase so para autenticar.

O banco de teste nao aplica as migrations de RLS (dependem de `auth.uid()`), entao
nao da para provar a policy contra ele. O que se prova aqui e a SEQUENCIA dos
arquivos: aplicadas em ordem, nenhuma policy de escrita sobrevive em `sellers`.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"

# Comandos que escrevem. `all` entra: `for all` inclui update, insert e delete.
ESCRITA = {"all", "insert", "update", "delete"}

# O nome pode vir entre aspas com espaco ou hifen: e o que o painel do Supabase
# gera ("Enable update for users based on user_id"). A tabela tambem pode vir
# qualificada e entre aspas. Um regex que so entende `\w+` deixaria uma policy
# de escrita assim passar em silencio.
NOME = r'(?:"(?P<nome_aspas>[^"]+)"|(?P<nome>\w+))'
TABELA = r'(?:"?public"?\.)?"?sellers\b"?'

CRIA = re.compile(
    rf"create\s+policy\s+{NOME}\s+on\s+{TABELA}(?:\s+as\s+\w+)?(?:\s+for\s+(?P<cmd>\w+))?",
    re.IGNORECASE,
)
APAGA = re.compile(
    rf"drop\s+policy\s+(?:if\s+exists\s+)?{NOME}\s+on\s+{TABELA}",
    re.IGNORECASE,
)


def _nome(m: re.Match) -> str:
    # Entre aspas o Postgres respeita a caixa; sem aspas, converte para minuscula.
    return m["nome_aspas"] or m["nome"].lower()


def _sem_comentarios(sql: str) -> str:
    return "\n".join(linha.split("--", 1)[0] for linha in sql.splitlines())


def policies_de_sellers(arquivos: list[tuple[str, str]]) -> dict[str, str]:
    """{nome: comando} das policies de `sellers` depois de aplicar os arquivos em ordem."""
    vivas: dict[str, str] = {}
    for _, sql in sorted(arquivos):
        sql = _sem_comentarios(sql)
        # Cada arquivo, na ordem em que os comandos aparecem nele.
        eventos = [(m.start(), "cria", m) for m in CRIA.finditer(sql)]
        eventos += [(m.start(), "apaga", m) for m in APAGA.finditer(sql)]
        for _, tipo, m in sorted(eventos, key=lambda e: e[0]):
            if tipo == "cria":
                vivas[_nome(m)] = (m["cmd"] or "all").lower()
            else:
                vivas.pop(_nome(m), None)
    return vivas


def test_o_parser_ve_a_policy_criada_e_a_apagada():
    """Sem isto, o teste do repo passaria mesmo com o regex quebrado."""
    cria = ("0002_x.sql", 'create policy "p_upd" on sellers for update using (true);')
    apaga = ("0015_x.sql", 'drop policy if exists "p_upd" on sellers;')
    assert policies_de_sellers([cria]) == {"p_upd": "update"}
    assert policies_de_sellers([cria, apaga]) == {}


def test_policy_sem_for_vale_para_todos_os_comandos():
    """`create policy` sem `for` e `for all` no Postgres."""
    assert policies_de_sellers([("0002_x.sql", "create policy p on sellers using (true);")]) == {
        "p": "all"
    }


def test_nome_com_espaco_e_tabela_qualificada_entre_aspas():
    """O formato que o painel do Supabase gera. Antes do `NOME`/`TABELA`, ficava invisivel."""
    sql = (
        'create policy "Enable update for users based on user_id" '
        'on "public"."sellers" for update using (true);'
    )
    assert policies_de_sellers([("0002_x.sql", sql)]) == {
        "Enable update for users based on user_id": "update"
    }
    drop = 'drop policy "Enable update for users based on user_id" on "public"."sellers";'
    assert policies_de_sellers([("0002_x.sql", sql), ("0015_x.sql", drop)]) == {}


def test_nome_com_hifen_entre_aspas():
    sql = 'create policy "sellers-upd" on sellers for update using (true);'
    assert policies_de_sellers([("0002_x.sql", sql)]) == {"sellers-upd": "update"}


def test_comentario_nao_conta_como_policy():
    sql = '-- create policy "p" on sellers for update using (true);\nselect 1;'
    assert policies_de_sellers([("0002_x.sql", sql)]) == {}


def test_sellers_so_tem_policy_de_leitura():
    arquivos = [(p.name, p.read_text(encoding="utf-8")) for p in MIGRATIONS.glob("*.sql")]
    vivas = policies_de_sellers(arquivos)

    assert vivas, "a policy de leitura sumiu: o vendedor deixaria de ver a propria linha"
    escrita = {nome: cmd for nome, cmd in vivas.items() if cmd in ESCRITA}
    assert escrita == {}, (
        f"policy de escrita em sellers: {escrita} -- o navegador reescreveria "
        "is_demo, ml_seller_id e last_synced_at pela API REST do Supabase"
    )
