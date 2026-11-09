# backend/routers/ml.py
"""Endpoints de conexao com o Mercado Livre.

O callback e um endpoint SEM autenticacao por Bearer — o browser chega aqui
vindo do ML, e o cookie de sessao do Supabase vive no dominio da Vercel, nao
neste. Quem prova a identidade e o `state` assinado emitido no /connect/start.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse

from backend.analytics._common import _TZ_VENDEDOR
from backend.db import get_pool
from backend.deps import (
    Acesso,
    Contas,
    get_acesso,
    get_acesso_somavel,
    get_contas,
    get_contas_somaveis,
    le_plano_e_aceite,
    recusa,
    recusa_fora_do_plano,
    recusa_visao_somada,
)
from backend.jobs import queue
from backend.ml import oauth
from backend.ml.tokens import PostgresTokenStore
from backend.planos import (
    ASSINATURA_VIGENTE,
    JOIN_PRINCIPAL,
    PLANOS,
    VERSAO_DOS_TERMOS,
    Recurso,
    conta_abre,
    dias_de_ingestao,
)
from src.ml_client import MLClient
from src.session_auth import OAuthError, exchange_code_for_tokens, sanitize_oauth_error

router = APIRouter(prefix="/ml", tags=["ml"])

_log = logging.getLogger(__name__)


def _destino(caminho: str) -> str:
    return f"{os.environ['FRONTEND_URL'].rstrip('/')}{caminho}"


# No `state`, distingue "conectar uma conta nova" de "(re)conectar a conta
# aberta". O state é assinado: o navegador não troca um pelo outro.
_PREFIXO_NOVA = "nova:"


@router.post("/connect/start")
async def connect_start(acesso: Acesso = Depends(get_acesso)) -> dict[str, str]:
    # Conectar exige plano e aceite: sem eles, o vendedor só vê a demo.
    url, _state = oauth.url_de_consentimento(str(acesso.seller_id))
    return {"url": url}


async def _contas_do_usuario(conn, seller_id: uuid.UUID) -> int:
    return await conn.fetchval(
        "SELECT count(*) FROM sellers WHERE user_id = (SELECT user_id FROM sellers WHERE id = $1)",
        seller_id,
    )


def _recusa_limite() -> HTTPException:
    return recusa(409, "limite-de-contas", "O plano já está com todas as contas conectadas")


@router.post("/contas/nova")
async def nova_conta(acesso: Acesso = Depends(get_acesso_somavel)) -> dict[str, str]:
    """Consentimento para conectar mais uma conta do ML ao mesmo login.

    O limite é conferido aqui e de novo no callback: entre os dois, outro
    consentimento aberto pode ter ocupado a vaga. Aceita a visão somada: age
    sobre o login, e não sobre a conta aberta.
    """
    if acesso.plano.max_contas < 2:
        raise recusa_fora_do_plano()
    pool = await get_pool()
    async with pool.acquire() as conn:
        if await _contas_do_usuario(conn, acesso.principal_id) >= acesso.plano.max_contas:
            raise _recusa_limite()
    url, _state = oauth.url_de_consentimento(f"{_PREFIXO_NOVA}{acesso.principal_id}")
    return {"url": url}


@router.delete("/contas/{conta_id}", status_code=204)
async def remove_conta(conta_id: uuid.UUID, contas: Contas = Depends(get_contas_somaveis)) -> None:
    """Apaga uma conta extra e, em cascata, todos os dados dela.

    Vale fora do Premium: é como quem saiu dele apaga a conta que não abre
    mais. A principal não sai por aqui, e sim com a exclusão da conta, que
    trata assinatura e a prova do aceite. Aceita a visão somada, como
    adicionar: age sobre o login.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        principal = await conn.fetchval(
            "SELECT principal FROM sellers "
            "WHERE id = $1 AND user_id = (SELECT user_id FROM sellers WHERE id = $2)",
            conta_id,
            contas.principal,
        )
        if principal is None:
            raise HTTPException(status_code=404, detail="Conta não encontrada")
        if principal:
            raise recusa(409, "conta-principal", "A conta principal sai com a exclusão da conta")
        await conn.execute("DELETE FROM sellers WHERE id = $1", conta_id)


@router.get("/callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    # O usuario clicou em "Cancelar" na tela do ML.
    if error or not code:
        return RedirectResponse(_destino("/dashboard/conectar?erro=recusado"))

    try:
        sub = oauth.valida_state(state or "")
        nova = sub.startswith(_PREFIXO_NOVA)
        seller_id = uuid.UUID(sub.removeprefix(_PREFIXO_NOVA))
    except (oauth.StateInvalido, ValueError):
        return RedirectResponse(_destino("/dashboard/conectar?erro=state"))

    async with (await get_pool()).acquire() as conn:
        conta = await conn.fetchrow(
            f"SELECT p.id AS principal, s.principal AS e_principal FROM sellers s "
            f"{JOIN_PRINCIPAL} WHERE s.id = $1",
            seller_id,
        )
    if conta is None:
        # A conta foi removida enquanto o consentimento estava aberto.
        return RedirectResponse(_destino("/dashboard/conectar?erro=state"))

    # O state so e emitido para quem tem acesso, mas vale por alguns minutos:
    # quem perdeu o plano nesse meio-tempo nao termina a conexao. Plano e
    # aceite sao os da principal: a conta extra nao tem assinatura propria.
    plano, aceitou = await le_plano_e_aceite(await get_pool(), conta["principal"])
    if plano is None or not aceitou:
        return RedirectResponse(_destino("/dashboard"))
    if (nova and plano.max_contas < 2) or not conta_abre(plano, principal=conta["e_principal"]):
        return RedirectResponse(_destino("/dashboard"))

    # `requests` e sincrono: sem to_thread, estas duas chamadas travariam o
    # event loop que atende todo o resto da API.
    try:
        tokens = await asyncio.to_thread(
            exchange_code_for_tokens,
            client_id=os.environ["ML_CLIENT_ID"],
            client_secret=os.environ["ML_CLIENT_SECRET"],
            code=code,
            redirect_uri=os.environ["ML_REDIRECT_URI"],
        )
    except OAuthError:
        return RedirectResponse(_destino("/dashboard/conectar?erro=troca"))

    try:
        cliente = MLClient(tokens.access_token)
        eu = await asyncio.to_thread(cliente.get, "/users/me")
    except Exception as exc:  # noqa: BLE001 — boundary de rede
        # sanitize_oauth_error evita que um access_token acabe no log. O tipo da
        # excecao vai junto porque e o que distingue "ML fora do ar" de
        # "client_id errado" pra quem le o log do Render.
        _log.warning(
            "[ml:callback] falha em /users/me: %s: %s",
            type(exc).__name__,
            sanitize_oauth_error(str(exc)),
        )
        return RedirectResponse(_destino("/dashboard/conectar?erro=perfil"))

    ml_seller_id = int(eu["id"])
    pool = await get_pool()

    try:
        async with pool.acquire() as conn, conn.transaction():
            # Na conta nova, nenhuma linha existente pode ter esta conta do ML,
            # nem a principal; na reconexao, a propria linha pode.
            dono = await conn.fetchval(
                "SELECT id FROM sellers WHERE ml_seller_id = $1 AND ($3 OR id <> $2)",
                ml_seller_id,
                seller_id,
                nova,
            )
            if dono is not None:
                return RedirectResponse(_destino("/dashboard/conectar?erro=ja-conectada"))

            if nova:
                # Trava na principal: dois callbacks de conta nova ao mesmo tempo
                # contariam as mesmas contas e passariam os dois do limite.
                await conn.execute("SELECT 1 FROM sellers WHERE id = $1 FOR UPDATE", seller_id)
                if await _contas_do_usuario(conn, seller_id) >= plano.max_contas:
                    return RedirectResponse(_destino("/dashboard/conectar?erro=limite-de-contas"))
                seller_id = await conn.fetchval(
                    "INSERT INTO sellers (user_id, principal, ml_seller_id, ml_nickname) "
                    "SELECT user_id, false, $2, $3 FROM sellers WHERE id = $1 RETURNING id",
                    seller_id,
                    ml_seller_id,
                    eu.get("nickname"),
                )
            else:
                await conn.execute(
                    "UPDATE sellers SET ml_seller_id = $2, ml_nickname = $3 WHERE id = $1",
                    seller_id,
                    ml_seller_id,
                    eu.get("nickname"),
                )
    except asyncpg.exceptions.UniqueViolationError:
        # Dois callbacks pra mesma conta do ML no mesmo instante: os dois
        # passam pelo SELECT acima antes de qualquer um gravar. Quem decide
        # e a constraint uniq_ml_seller_id; o SELECT continua ali so pra dar
        # a mensagem certa no caso comum, sem gastar um write que vai falhar.
        return RedirectResponse(_destino("/dashboard/conectar?erro=ja-conectada"))

    await PostgresTokenStore(pool, seller_id).save(tokens)
    await queue.enqueue(pool, seller_id, "backfill")
    return RedirectResponse(_destino("/dashboard/conectar?conectado=1"))


@router.delete("/connection", status_code=204)
async def disconnect(contas: Contas = Depends(get_contas)) -> None:
    """Apaga os tokens e para a sincronizacao. Os dados ingeridos ficam.

    Eles saem junto com a conta, que tem ON DELETE CASCADE desde a Sprint 1 —
    apagar historico aqui seria destruir dado que o usuario nao pediu pra
    destruir, so porque ele desplugou a integracao. E a conta aberta: com uma
    extra aberta, a principal continua conectada.
    """
    seller_id = contas.aberta
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("DELETE FROM oauth_tokens WHERE seller_id = $1", seller_id)
        # A tela e o agendador dizem "conectado" pelo `ml_seller_id`. Sem zerar,
        # o vendedor ficaria sem o botao de conectar e a fila seguiria recebendo
        # job que so falha sem credencial. O callback grava de novo.
        await conn.execute("UPDATE sellers SET ml_seller_id = NULL WHERE id = $1", seller_id)
        # Job que ainda esperava ocuparia a vaga de job ativo e engoliria o
        # backfill da reconexao. O que ja esta rodando termina ou falha sozinho.
        await conn.execute(
            "UPDATE sync_jobs SET status = 'failed', finished_at = now(), "
            "erro = 'conta do Mercado Livre desconectada' "
            "WHERE seller_id = $1 AND status = 'queued'",
            seller_id,
        )


# Abaixo disso, um login nao dispara sincronizacao: o dado esta fresco o
# bastante e cada sync gasta rate limit da API do ML.
LIMIAR_DELTA = timedelta(hours=6)

FOLGA_DO_AGENDADOR = timedelta(hours=1)


def _agora() -> datetime:
    # Separado para os testes fixarem a hora da rodada.
    return datetime.now(UTC)


# A rodada dos planos diarios: a das 06:00, com o resto da manha de folga para
# o atraso do cron do GitHub.
MANHA = range(6, 12)


def _hora_de_sincronizar(plano, *, ultimo: datetime, agora: datetime) -> bool:
    """Esta rodada do agendador sincroniza este vendedor?

    O agendador roda de 6 em 6 horas (spec 2026-11-06-premium-sync-a-cada-6-horas).

    - Plano diario: so na rodada da manha, para o dado estar pronto antes do
      expediente. Por intervalo de 23h, o horario escorregaria para a primeira
      rodada depois do ultimo sync (um backfill as 14h fixaria as 18h) e nao
      voltaria. O limiar do login evita repetir quem acabou de sincronizar.
    - Premium: a cada rodada, com folga. `last_synced_at` e gravado no FIM do
      job, e o cron atrasa: sem a folga, a rodada seguinte veria 5h50 e o
      Premium sincronizaria de 12 em 12 horas. A folga tambem cobre a fila:
      se o delta do ultimo Premium terminar mais de 1h depois da rodada, ele
      cai para 12 em 12 horas sem nada falhar.
    """
    if plano.horas_entre_syncs >= 24:
        return agora.astimezone(_TZ_VENDEDOR).hour in MANHA and agora - ultimo >= LIMIAR_DELTA
    return agora - ultimo >= timedelta(hours=plano.horas_entre_syncs) - FOLGA_DO_AGENDADOR


_MOTIVOS = frozenset({"manual", "login"})


@router.post("/sync")
async def sync(
    motivo: str = "manual",
    acesso: Acesso = Depends(get_acesso_somavel),
) -> dict:
    """Enfileira um delta. QUEM DECIDE SE VALE A PENA E O SERVIDOR.

    `motivo=login` respeita a janela de 6h; `motivo=manual` e ordem direta do
    usuario e sempre enfileira. Deixar essa regra no frontend permitiria que
    uma aba velha, ou um cliente adulterado, a ignorasse.
    """
    if motivo not in _MOTIVOS:
        raise HTTPException(status_code=400, detail=f"motivo invalido: {motivo!r}")
    # Na visao somada nao ha uma conta para sincronizar. O login nao e erro (o
    # front o dispara sozinho no Resumo); o botao e. O Premium ja sincroniza
    # cada conta a cada 6 horas pela rodada agendada.
    if acesso.somada:
        if motivo == "login":
            return {"enfileirado": False, "motivo": "visao-somada"}
        raise recusa_visao_somada()
    seller_id = acesso.seller_id

    # Sem sincronizacao sob demanda, o plano fica so com a diaria agendada. O
    # login nao e erro (o front o dispara sozinho); o botao e.
    if not acesso.plano.libera(Recurso.SYNC_SOB_DEMANDA):
        if motivo == "login":
            return {"enfileirado": False, "motivo": "plano"}
        raise recusa_fora_do_plano()

    pool = await get_pool()
    async with pool.acquire() as conn:
        seller = await conn.fetchrow(
            "SELECT ml_seller_id, last_synced_at FROM sellers WHERE id = $1", seller_id
        )
    if seller is None or seller["ml_seller_id"] is None:
        raise HTTPException(
            status_code=409, detail="Conecte uma conta do Mercado Livre antes de sincronizar"
        )

    if motivo == "login":
        ultimo = seller["last_synced_at"]
        if ultimo is not None and datetime.now(UTC) - ultimo < LIMIAR_DELTA:
            return {"enfileirado": False, "motivo": "recente"}

    # Seller que nunca sincronizou precisa de HISTORICO, nao de delta: `_delta`
    # cai numa janela de 7 dias quando last_synced_at e nulo, e o seller ficaria
    # preso nela pra sempre se o backfill do callback tivesse falhado em
    # definitivo. A decisao e aqui porque so aqui se sabe o estado do seller.
    kind = "delta" if seller["last_synced_at"] is not None else "backfill"
    job_id = await queue.enqueue(pool, seller_id, kind)
    if job_id is None:
        return {"enfileirado": False, "motivo": "ja-em-andamento"}
    return {"enfileirado": True, "job_id": job_id}


# Nome da variavel com o segredo do agendador. Mesma convencao de
# `STATE_SECRET` e `TOKEN_ENCRYPTION_KEY`.
SEGREDO_DO_AGENDADOR = "SYNC_SECRET"


def _confere_segredo(recebido: str | None) -> None:
    """Autentica o agendador. FALHA FECHADA quando nao ha segredo configurado.

    Se `SYNC_SECRET` estiver ausente, este endpoint devolve 503 em vez de
    liberar o acesso. A alternativa — tratar "sem segredo" como "sem exigencia"
    — transformaria uma variavel esquecida num endpoint aberto que enfileira
    trabalho para todos os vendedores. O modo de falha tem que ser o barato.

    `compare_digest` em vez de `==` porque a comparacao ingenua vaza o
    comprimento do prefixo correto pelo tempo de resposta.
    """
    esperado = os.environ.get(SEGREDO_DO_AGENDADOR)
    if not esperado:
        raise HTTPException(status_code=503, detail="sincronizacao agendada nao esta configurada")
    if recebido is None or not secrets.compare_digest(recebido, esperado):
        raise HTTPException(status_code=401, detail="segredo invalido")


@router.post("/sync-todos")
async def sync_todos(x_sync_secret: str | None = Header(default=None)) -> dict:
    """Enfileira sincronizacao para TODOS os vendedores conectados.

    Chamado por um agendador externo, nao por usuario — dai o segredo no
    cabecalho em vez do JWT que os outros endpoints exigem.

    POR QUE ESTE ENDPOINT EXISTE, na ordem do que ele resolve de verdade:

    1. A demonstracao publica para de estar fria. O Render hiberna apos 15 min
       e o projeto do Supabase e pausado apos 7 dias de baixa atividade (plano
       gratuito). Quem clica em "ver demonstracao" depois de um fim de semana
       parado espera 25s, ou encontra o banco pausado. Uma visita por dia
       mantem os dois acordados — e nao com ping cosmetico: escreve pedido e
       visita de verdade.
    2. O dado chega pronto. Hoje o painel renderiza o que esta no banco
       enquanto o job roda, entao quem volta depois de dias ve o estado antigo
       ate recarregar.
    3. As visitas param de ter buraco. O ML devolve no maximo 150 dias; uma
       ausencia maior que isso perde aquele pedaco para sempre.

    NAO duplica logica de sincronizacao: enfileira um job e o worker faz o
    resto, inclusive encadear as visitas depois dos pedidos.
    """
    _confere_segredo(x_sync_secret)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # `ml_seller_id IS NOT NULL` ja exclui o seller de demonstracao, que
        # nao tem conta do ML conectada. Nao filtrar por `is_demo` de
        # proposito: o criterio que importa e "da pra sincronizar", e e esse.
        # Sem plano, nao sincroniza: e cota da API do ML gasta com conta que
        # nao paga. Plano vencido conta como sem plano, pela mesma regra de
        # `le_plano_e_aceite`. Sem o aceite da versao vigente tambem nao: quem
        # recusou os Termos nao autorizou o tratamento dos dados novos. O dado
        # ingerido fica, e volta a atualizar com o plano e o aceite.
        sellers = await conn.fetch(
            f"""
            SELECT s.id, s.last_synced_at, s.principal, a.plano,
                   (SELECT max(j.finished_at) FROM sync_jobs j
                     WHERE j.seller_id = s.id AND j.kind = 'backfill'
                       AND j.status = 'failed') AS backfill_falhou_em
              FROM sellers s
              {JOIN_PRINCIPAL}
              JOIN assinaturas a ON a.seller_id = p.id
             WHERE s.ml_seller_id IS NOT NULL
               AND {ASSINATURA_VIGENTE}
               AND EXISTS (SELECT 1 FROM aceites_de_termos t
                            WHERE t.seller_id = p.id AND t.versao = $1)
            """,
            VERSAO_DOS_TERMOS,
        )

    agora = _agora()
    enfileirados = 0
    pulados: dict[str, int] = {}

    for seller in sellers:
        # Conta extra fora do Premium: os dados ficam, mas nao sincroniza (2.1).
        if not conta_abre(PLANOS[seller["plano"]], principal=seller["principal"]):
            pulados["fora-do-plano"] = pulados.get("fora-do-plano", 0) + 1
            continue
        ultimo = seller["last_synced_at"]
        # Sem sincronização nenhuma, a última tentativa é o backfill que
        # falhou: sem isso, ele era refeito em toda rodada, 4 vezes por dia em
        # qualquer plano, gastando cota do ML com job que morre.
        tentativa = ultimo if ultimo is not None else seller["backfill_falhou_em"]
        if tentativa is not None and not _hora_de_sincronizar(
            PLANOS[seller["plano"]], ultimo=tentativa, agora=agora
        ):
            pulados["recente"] = pulados.get("recente", 0) + 1
            continue

        kind = "delta" if ultimo is not None else "backfill"
        if await queue.enqueue(pool, seller["id"], kind) is None:
            pulados["ja-em-andamento"] = pulados.get("ja-em-andamento", 0) + 1
        else:
            enfileirados += 1

    _log.info(
        "[agendado] %d sellers conectados, %d enfileirados, pulados=%s",
        len(sellers),
        enfileirados,
        pulados or "nenhum",
    )
    # So contagens, nunca os ids: o retorno vai para o log de um agendador
    # externo, e id de job nao ajuda ninguem la.
    return {"sellers": len(sellers), "enfileirados": enfileirados, "pulados": pulados}


# Conectar pede o status a cada 3 s enquanto um job roda. O indice
# (seller_id, created_at) da migration 0025 evita ler a fila inteira.
_ULTIMO_JOB = """
    SELECT id, kind, status, fase, processados, total, erro, warnings,
           created_at, finished_at
    FROM sync_jobs WHERE seller_id = $1
    ORDER BY created_at DESC LIMIT 1
"""


@router.get("/sync/status")
async def sync_status(contas: Contas = Depends(get_contas)) -> dict:
    seller_id = contas.aberta
    pool = await get_pool()
    plano, _ = await le_plano_e_aceite(pool, contas.principal)
    async with pool.acquire() as conn:
        seller = await conn.fetchrow(
            "SELECT ml_seller_id, ml_nickname, last_synced_at FROM sellers WHERE id = $1",
            seller_id,
        )
        job = await conn.fetchrow(_ULTIMO_JOB, seller_id)
        historico_completo = await conn.fetchval(
            "SELECT exists(SELECT 1 FROM sync_jobs WHERE seller_id = $1 "
            "AND kind = 'backfill' AND status = 'done')",
            seller_id,
        )

    return {
        "conectado": seller is not None and seller["ml_seller_id"] is not None,
        "apelido": seller["ml_nickname"] if seller else None,
        "ultima_sincronizacao": (
            seller["last_synced_at"].isoformat() if seller and seller["last_synced_at"] else None
        ),
        "job": None
        if job is None
        else {
            "id": job["id"],
            "kind": job["kind"],
            "status": job["status"],
            "fase": job["fase"],
            "processados": job["processados"],
            "total": job["total"],
            "erro": job["erro"],
            "warnings": json.loads(job["warnings"]) if job["warnings"] else [],
            "criado_em": job["created_at"].isoformat(),
            "concluido_em": job["finished_at"].isoformat() if job["finished_at"] else None,
        },
        # Responde "os numeros do dashboard cobrem os 6 meses?". Sem isso, um
        # backfill que falhou em definitivo some assim que qualquer delta
        # posterior conclui — e a tela diz "sincronizado" sobre historico
        # incompleto, sem nada indicando.
        "historico_completo": bool(historico_completo),
        # O botao "Sincronizar agora" so aparece para quem o plano deixa usar.
        "sincroniza_sob_demanda": plano is not None and plano.libera(Recurso.SYNC_SOB_DEMANDA),
        # Conectar dizia "6 meses" a todos, e a conta extra do Premium importa 12.
        "meses_da_importacao": dias_de_ingestao(plano) // 30,
    }
