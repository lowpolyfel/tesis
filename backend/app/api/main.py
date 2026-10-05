"""Aplicación FastAPI. Desde `backend/`:  uvicorn app.api.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.orchestration import Servicio, crear_dependencias

from .routes import lel, requisitos, sandbox


def create_app(servicio: Servicio | None = None) -> FastAPI:
    """`servicio` permite inyectar dobles en las pruebas; si falta, se arma con la
    configuración real al arrancar (spaCy, catálogos, Ollama, Mongo o JSON)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.servicio is None:
            logging.basicConfig(level=logging.INFO)
            app.state.servicio = Servicio(crear_dependencias())
        yield

    app = FastAPI(title="Tesis: núcleo de agentes", version="0.1.0", lifespan=lifespan)
    app.state.servicio = servicio
    for r in (requisitos.router, lel.router, sandbox.router):
        app.include_router(r)
    return app


app = create_app()
