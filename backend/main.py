from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import close_pool, get_pool
from backend.demo_refresh import regenera_demo_se_vencida
from backend.ml.tokens import valida_chave_de_cifra
from backend.routers import demo, metrics, ml, segmentation
from backend.worker.runner import loop as worker_loop
from backend.worker.runner import worker_habilitado

# Carrega backend/.env em desenvolvimento. `load_dotenv` NAO sobrescreve
# variaveis ja presentes no ambiente, entao em producao (Render) os valores
# da plataforma continuam valendo e a ausencia do arquivo e inofensiva.
load_dotenv(Path(__file__).resolve().parent / ".env")

_log = logging.getLogger(__name__)


def demo_refresh_habilitado() -> bool:
    """LIGA so com `DEMO_REFRESH_IN_PROCESS=1` explicito -- opt-in, nao opt-out.

    A segunda instrucao desta feature e `DELETE FROM orders`. Num default
    opt-out, todo ambiente que nunca ouviu falar dela roda o refresh por
    inercia: um clone novo, um runner de CI, qualquer script que importe
    `backend.main` -- e basta um `DEMO_SELLER_ID` errado pra apagar os pedidos
    de um seller. A assimetria e todo o argumento: esquecer a variavel no
    opt-in deixa a demo velha (cosmetico), esquecer no opt-out apaga dado
    (destrutivo). Entre as duas, o default tem que ser a falha barata.

    DIVERGE de `worker_habilitado()` DE PROPOSITO, que continua opt-out: o
    worker so le e escreve as linhas da propria fila, este refresh APAGA. Nao
    "arrume" a inconsistencia -- ela e a decisao.
    """
    return os.environ.get("DEMO_REFRESH_IN_PROCESS") == "1"


async def _refresca_demo(pool) -> None:
    """Wrapper que NAO deixa o refresh da demo derrubar a API.

    A demo e vitrine; a API serve clientes pagos. Qualquer excecao aqui (banco
    fora, schema velho, seller apontado errado) nao pode virar boot quebrado.
    Loga nos dois caminhos de proposito: um refresh que para de funcionar em
    silencio e exatamente o bug que esta feature existe pra consertar.
    """
    try:
        status = await regenera_demo_se_vencida(pool)
        _log.info("[demo] refresh da demo: %s", status)
    except Exception:  # noqa: BLE001 — boundary da task de fundo
        _log.exception("[demo] refresh da demo falhou")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Abre o pool e, se habilitado, sobe o worker da fila no mesmo processo.

    O worker mora aqui porque o plano gratuito do Render nao tem Background
    Worker. `WORKER_IN_PROCESS=0` desliga — usado nos testes de router, que
    precisam que ninguem drene a fila que eles acabaram de popular.

    O refresh da demo tambem sai daqui, em task de fundo -- mas so quando
    ligado explicitamente (ver `demo_refresh_habilitado`). Nunca no caminho
    sincrono do boot: o free tier do Render hiberna e o visitante que acorda a
    instancia ja espera ~25s: somar a regeneracao de ~780 pedidos a essa
    espera faria a pagina de aquisicao parecer quebrada.
    """
    # Falha no boot, nao no primeiro usuario. Sem isto, uma chave de cifra
    # faltando ou malformada deixa o deploy subir e o health check passar, e o
    # erro aparece como 500 no meio do callback OAuth de quem conectar primeiro
    # — com os tokens dele nao gravados.
    valida_chave_de_cifra()

    pool = await get_pool()
    parar = asyncio.Event()
    tarefa: asyncio.Task | None = None
    if worker_habilitado():
        tarefa = asyncio.create_task(worker_loop(pool, parar=parar), name="sellerpulse-worker")

    tarefa_demo: asyncio.Task | None = None
    if demo_refresh_habilitado():
        tarefa_demo = asyncio.create_task(_refresca_demo(pool), name="sellerpulse-demo-refresh")
    try:
        yield
    finally:
        if tarefa is not None:
            parar.set()
            # Espera de verdade: task vazada deixaria o processo pendurado no
            # shutdown, e o Render mataria o container a forca no deploy.
            await tarefa
        if tarefa_demo is not None:
            # Diferente do worker, esta task nao tem evento de parada: ela e uma
            # transacao unica que nao da pra interromper num ponto seguro. Entao
            # cancela e espera o cancelamento ser processado — o `await` e o que
            # garante que a task nao sobrevive ao shutdown. O rollback da
            # transacao em andamento fica com o asyncpg/Postgres: a demo com dado
            # velho e um resultado aceitavel, demo vazia nao seria.
            tarefa_demo.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarefa_demo
        await close_pool()


app = FastAPI(title="SellerPulse API", lifespan=lifespan)

# Origens liberadas no CORS. Fixar so a URL de producao quebraria a cada
# deploy de preview da Vercel, que recebe um subdominio novo — entao a lista
# vem de CORS_ORIGINS (separada por virgula) somada aos defaults abaixo.
_ORIGENS_PADRAO = [
    "http://localhost:3000",
    "https://frontend-three-rosy-iwes33l1kk.vercel.app",
]
_extras = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_ORIGENS_PADRAO, *_extras],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(demo.router)
app.include_router(metrics.router)
app.include_router(ml.router)
app.include_router(segmentation.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
