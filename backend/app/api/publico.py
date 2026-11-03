"""Un solo servidor para publicar Dudamel: la API en /api y la interfaz compilada en /.

Para alojarlo en un servicio con un solo proceso (Render, Koyeb…): la interfaz se compila
con `npm run build -- --mode publico` (llama a /api en el mismo origen) y este módulo la
sirve junto a la API. Mismo origen: la cookie de sesión (SameSite=Lax) viaja sin tocar CORS.

    uvicorn app.api.publico:app --host 0.0.0.0 --port $PORT

DUDAMEL_DIST dice dónde está la interfaz compilada (por omisión, ../frontend/dist).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.main import app as api

DIST = Path(os.environ.get("DUDAMEL_DIST", Path(__file__).resolve().parents[3] / "frontend" / "dist")).resolve()


def crear_publico(dist: Path = DIST) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Starlette no corre el lifespan de una app montada: este lo delega (cola, recuperación)
        async with api.router.lifespan_context(api):
            yield

    publico = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    publico.mount("/api", api)

    @publico.get("/salud", include_in_schema=False)
    def salud():  # para el health check del hosting, sin pasar por la API
        return {"ok": True}

    if (dist / "assets").is_dir():
        publico.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    indice = dist / "index.html"

    @publico.get("/{ruta:path}", include_in_schema=False)
    def interfaz(ruta: str):
        if not indice.is_file():
            return JSONResponse({"detail": f"No está la interfaz compilada en {dist}"}, status_code=503)
        archivo = (dist / ruta).resolve()
        if ruta and archivo.is_file() and archivo.is_relative_to(dist):
            return FileResponse(archivo)
        # cualquier otra ruta es de React Router (/proyectos/…): la decide la interfaz
        return FileResponse(indice, headers={"Cache-Control": "no-cache"})

    return publico


app = crear_publico()
