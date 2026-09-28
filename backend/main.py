from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import close_pool, get_pool
from backend.ml.tokens import valida_chave_de_cifra
from backend.routers import metrics, ml, segmentation
from backend.worker.runner import loop as worker_loop
from backend.worker.runner import worker_habilitado

# Carrega backend/.env em desenvolvimento. `load_dotenv` NAO sobrescreve
# variaveis ja presentes no ambiente, entao em producao (Render) os valores
# da plataforma continuam valendo e a ausencia do arquivo e inofensiva.
load_dotenv(Path(__file__).resolve().parent / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Abre o pool e, se habilitado, sobe o worker da fila no mesmo processo.

    O worker mora aqui porque o plano gratuito do Render nao tem Background
    Worker. `WORKER_IN_PROCESS=0` desliga — usado nos testes de router, que
    precisam que ninguem drene a fila que eles acabaram de popular.
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
    try:
        yield
    finally:
        if tarefa is not None:
            parar.set()
            # Espera de verdade: task vazada deixaria o processo pendurado no
            # shutdown, e o Render mataria o container a forca no deploy.
            await tarefa
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

app.include_router(metrics.router)
app.include_router(ml.router)
app.include_router(segmentation.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
