from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import close_pool, get_pool
from backend.routers import metrics, segmentation

# Carrega backend/.env em desenvolvimento. `load_dotenv` NAO sobrescreve
# variaveis ja presentes no ambiente, entao em producao (Render) os valores
# da plataforma continuam valendo e a ausencia do arquivo e inofensiva.
load_dotenv(Path(__file__).resolve().parent / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
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
app.include_router(segmentation.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
