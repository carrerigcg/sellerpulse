# backend/logging_setup.py
"""Configuracao de logging do backend -- explicita, porque hoje ela e acidental.

Nenhum modulo do projeto configurava logging. As linhas apareciam no Render por
efeito colateral: o construtor do `FastMCP` chama
`logging.basicConfig(level="INFO", format="%(message)s")`, e
`backend/mcp_server.py` instancia um no import. Duas consequencias, as duas
medidas antes de escrever este arquivo:

1. A configuracao morre em SILENCIO se o MCP sair do caminho de import, se ele
   virar lazy, ou se o SDK parar de chamar `basicConfig`. Nenhum teste veria a
   diferenca, e o sintoma em producao seria "os logs sumiram", sem relacao
   obvia com o commit que mexeu no MCP.

2. `format="%(message)s"` emite a mensagem crua, sem nivel. O Render deduz o
   nivel de cada linha pelo COMECO dela: em 25 dias de log, a unica linha
   marcada `level=warning` foi `WARNING: Running pip as the 'root' user`, que
   vem do pip no build justamente porque comeca com o nivel. Todo
   `_log.warning` e `_log.exception` do nosso codigo chegava marcado como
   `info`, invisivel a qualquer filtro de erro do painel.

Dai o nivel vir primeiro no formato. Nao e estetica: e o que faz um traceback
de producao ser encontravel.

Quem chama isto e o ENTRY POINT (`backend/main.py`), uma vez. Codigo de
biblioteca nao configura logging do processo -- a licao esta no paragrafo
acima, e e exatamente o que o SDK do MCP faz de errado.
"""

from __future__ import annotations

import logging
import os

NIVEL_PADRAO = "INFO"

# Nivel PRIMEIRO, por causa do parsing do Render (ver docstring do modulo).
#
# Sem `asctime` de proposito: a plataforma estampa a hora de cada linha, e a
# propria uvicorn omite timestamp no formato default pela mesma razao. Duas
# horas na mesma linha nao informam nada e empurram a mensagem pra direita.
FORMATO = "%(levelname)s %(name)s: %(message)s"


def _resolve_nivel(nivel: str | None) -> tuple[int, str | None]:
    """Traduz nome de nivel em numero. Devolve tambem o nome recusado, se houver.

    Aceita so NOME (`INFO`, `DEBUG`), nao numero: `logging.getLevelName("20")`
    nao faz o caminho de volta, e um `LOG_LEVEL=20` silenciosamente cairia no
    padrao. Nome e o que se escreve numa variavel de ambiente de todo jeito.
    """
    pedido = nivel or os.environ.get("LOG_LEVEL") or NIVEL_PADRAO
    resolvido = logging.getLevelName(pedido.strip().upper())
    if isinstance(resolvido, int):
        return resolvido, None
    # Devolve `pedido` CRU, nao a versao normalizada: quem for consertar vai
    # procurar no ambiente exatamente o que digitou la.
    return logging.getLevelName(NIVEL_PADRAO), pedido


def configura_logging(nivel: str | None = None) -> None:
    """Instala o handler do processo no logger raiz. Idempotente.

    `force=True` e o ponto do exercicio: quando isto roda, o SDK do MCP JA
    pendurou o handler dele na raiz (o import de `backend.mcp_server` acontece
    antes), e dois handlers na raiz significam cada linha duas vezes. Entao
    troca em vez de somar -- e por isso chamar duas vezes tambem nao acumula.

    Nao mexe nos loggers da uvicorn (`uvicorn`, `uvicorn.access`): eles tem
    handler proprio com `propagate=False`, configurados pelo `dictConfig` dela
    antes do app ser importado. O formato `INFO:     GET /... 200 OK` das
    linhas de acesso continua sendo dela.
    """
    numero, recusado = _resolve_nivel(nivel)

    logging.basicConfig(level=numero, format=FORMATO, force=True)

    # O aviso vem DEPOIS de configurar, nao antes: emitido antes, ele sairia
    # pelo handler que estamos substituindo -- ou por nenhum.
    if recusado is not None:
        logging.getLogger(__name__).warning(
            "LOG_LEVEL=%r nao e um nivel conhecido -- seguindo em %s",
            recusado,
            NIVEL_PADRAO,
        )
