"""Aplicación FastAPI. Desde `backend/`:  uvicorn app.api.main:app --reload"""
from __future__ import annotations

import json
import logging
import signal
import threading
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


class ErroresInternosComoJson:
    """Una excepción no controlada se responde como 500 `{detail}` desde dentro de la
    pila de CORS. El 500 por omisión de Starlette sale por fuera de CORSMiddleware, sin
    Access-Control-Allow-Origin, y el navegador lo reporta como falta de conexión."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        iniciada = False

        async def enviar(mensaje):
            nonlocal iniciada
            iniciada = iniciada or mensaje["type"] == "http.response.start"
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception as e:
            if not iniciada:
                detalle = f"Error interno del servidor ({type(e).__name__}); el detalle está en el registro del backend."
                await JSONResponse({"detail": detalle}, status_code=500)(scope, receive, send)
            raise  # uvicorn lo registra con su traceback


class JSONAscii(JSONResponse):
    """JSON con escapes `\\uXXXX`: un sustituto UTF-16 suelto copiado de la entrada no rompe la respuesta."""

    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")


async def entrada_invalida(request: Request, exc: RequestValidationError) -> JSONResponse:
    # El de FastAPI copia `input` en la respuesta y truena al codificarla si trae un sustituto suelto
    return JSONAscii({"detail": jsonable_encoder(exc.errors())}, status_code=422)


def avisar_al_apagar(apagando: threading.Event) -> Callable[[], None]:
    """Al recibir SIGINT o SIGTERM (Ctrl+C, `--reload`), uvicorn espera a que se cierren las
    conexiones antes de apagar, y el SSE de un requisito que espera validación no se cierra
    solo. Se encadena a sus manejadores para marcar `apagando` y que los SSE terminen.
    Las señales solo se atienden en el hilo principal (no con TestClient). Devuelve cómo
    restaurar los manejadores anteriores."""
    if threading.current_thread() is not threading.main_thread():
        return lambda: None
    previos = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previo = signal.getsignal(sig)
        if not callable(previo):
            continue

        def manejar(s, marco, previo=previo):
            apagando.set()
            previo(s, marco)

        previos[sig] = previo
        signal.signal(sig, manejar)
    return lambda: [signal.signal(sig, previo) for sig, previo in previos.items()]


def create_app(servicio: Servicio | None = None) -> FastAPI:
    """`servicio` permite inyectar dobles en las pruebas; si falta, se arma con la
    configuración real al arrancar (spaCy, catálogos, Ollama, Mongo o JSON)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.servicio is None:
            logging.basicConfig(level=logging.INFO)
            app.state.servicio = Servicio(crear_dependencias())
        restaurar = avisar_al_apagar(app.state.apagando)
        app.state.servicio.iniciar()  # trabajador de la cola + recuperación tras reinicio
        yield
        restaurar()
        app.state.servicio.detener()

    app = FastAPI(title="Tesis: núcleo de agentes", version="0.2.0", lifespan=lifespan)
    app.state.servicio = servicio
    app.state.apagando = threading.Event()
    settings = servicio.deps.settings if servicio else get_settings()
    app.add_exception_handler(RequestValidationError, entrada_invalida)
    # Va antes que CORS para quedar dentro de su pila (el último que se agrega es el más externo)
    app.add_middleware(ErroresInternosComoJson)
    # El frontend (Vite, otro puerto) llama a la API y abre EventSource
    app.add_middleware(CORSMiddleware, allow_origins=settings.origenes_cors(),
                       allow_origin_regex=settings.cors_origenes_regex or None, allow_methods=["*"],
                       allow_headers=["*"], allow_credentials=False)
    for r in (requisitos.router, proyectos.router, documentos.router, analisis.router, comparaciones.router,
              calibracion.router, evaluaciones.router, artefactos.router, lel.router, sandbox.router):
        app.include_router(r)
    return app


app = create_app()
