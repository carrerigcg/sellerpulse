"""A trava que impede mergear migration nao aplicada em producao.

O teste mais importante aqui e o ultimo: ele roda a checagem contra o repo de
verdade. Os outros exercitam a logica; esse garante que a trava esta ARMADA
agora, e nao so que funcionaria se alguem a chamasse.
"""

from __future__ import annotations

from backend.scripts.checa_migrations import SO_TESTE, divergencias, le_registro


def test_le_registro_separa_producao_de_teste():
    texto = (
        "# comentario\n"
        "\n"
        "0001_init.sql\t20260923133315\t2026-09-23\n"
        "0002_rls.sql\t20260923133322\t2026-09-23\n"
        "\n"
        "# so teste:\n"
        f"{SO_TESTE}0000_test_auth_stub.sql\n"
    )
    aplicadas, so_teste = le_registro(texto)
    assert aplicadas == {"0001_init.sql", "0002_rls.sql"}
    assert so_teste == {"0000_test_auth_stub.sql"}


def test_acusa_migration_nova_sem_registro():
    """O caso que aconteceu de verdade em 2026-10-14."""
    nao_registradas, sumiram = divergencias(
        arquivos={"0001_init.sql", "0010_item_visits.sql"},
        aplicadas={"0001_init.sql"},
        so_teste=set(),
    )
    assert nao_registradas == {"0010_item_visits.sql"}
    assert sumiram == set()


def test_acusa_registro_apontando_para_arquivo_que_sumiu():
    """Registro descrevendo um banco que ninguem mais consegue reproduzir."""
    nao_registradas, sumiram = divergencias(
        arquivos={"0001_init.sql"},
        aplicadas={"0001_init.sql", "0002_apagada.sql"},
        so_teste=set(),
    )
    assert nao_registradas == set()
    assert sumiram == {"0002_apagada.sql"}


def test_migration_so_de_teste_nao_conta_como_pendente():
    """Senao o aviso vira ruido permanente, e ruido permanente se ignora."""
    nao_registradas, _ = divergencias(
        arquivos={"0000_test_auth_stub.sql"},
        aplicadas=set(),
        so_teste={"0000_test_auth_stub.sql"},
    )
    assert nao_registradas == set()


def test_o_repo_de_verdade_esta_em_dia():
    """Roda a checagem contra os arquivos reais deste repositorio.

    Sem este teste, os de cima provariam que a trava FUNCIONA sem provar que
    ela esta ARMADA. E a diferenca entre ter um alarme e te-lo ligado.
    """
    from backend.scripts.checa_migrations import MIGRATIONS, REGISTRO

    arquivos = {p.name for p in MIGRATIONS.glob("*.sql")}
    aplicadas, so_teste = le_registro(REGISTRO.read_text(encoding="utf-8"))
    nao_registradas, sumiram = divergencias(arquivos, aplicadas, so_teste)

    assert nao_registradas == set(), f"migration sem registro: {sorted(nao_registradas)}"
    assert sumiram == set(), f"registro aponta para arquivo inexistente: {sorted(sumiram)}"
