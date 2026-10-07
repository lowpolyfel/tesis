"""Aplicación FastAPI. Desde `backend/`:  uvicorn app.api.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.orchestration import Servicio, crear_dependencias

from .routes import (
    analisis,
    artefactos,
    calibracion,
    comparaciones,
    documentos,
    evaluaciones,
    lel,
    proyectos,
    requisitos,
    sandbox,
)


def create_app(servicio: Servicio | None = None) -> FastAPI:
    """`servicio` permite inyectar dobles en las pruebas; si falta, se arma con la
    configuración real al arrancar (spaCy, catálogos, Ollama, Mongo o JSON)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.servicio is None:
            logging.basicConfig(level=logging.INFO)
            app.state.servicio = Servicio(crear_dependencias())
        app.state.servicio.iniciar()  # trabajador de la cola + recuperación tras reinicio
        yield
        app.state.servicio.detener()

    app = FastAPI(title="Tesis: núcleo de agentes", version="0.2.0", lifespan=lifespan)
    app.state.servicio = servicio
    settings = servicio.deps.settings if servicio else get_settings()
    # El frontend (Vite, otro puerto) llama a la API y abre EventSource
    app.add_middleware(CORSMiddleware, allow_origins=settings.origenes_cors(), allow_methods=["*"],
                       allow_headers=["*"], allow_credentials=False)
    for r in (requisitos.router, proyectos.router, documentos.router, analisis.router, comparaciones.router,
              calibracion.router, evaluaciones.router, artefactos.router, lel.router, sandbox.router):
        app.include_router(r)
    return app


app = create_app()
