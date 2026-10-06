"""Procesar un requisito, seguir su traza en vivo y validarlo."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ConfigDict, Field

from app.models import PROYECTO_GENERAL, ESTADOS_TERMINALES, Estado, Traza, Validacion
from app.orchestration import ConflictoDeEstado, Servicio

from ..dependencias import obtener_servicio, traza_existente

router = APIRouter(tags=["requisitos"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


class EntradaProcesar(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    texto: str = Field(min_length=1, max_length=2000)
    proyecto_id: str = PROYECTO_GENERAL


class Aceptado(BaseModel):
    req_id: str
    estado: Estado


@router.post("/procesar", status_code=202, response_model=Aceptado)
def procesar(entrada: EntradaProcesar, srv: ServicioDep) -> Aceptado:
    """Registra el requisito y lo encola; los mensajes se siguen en `/eventos/{req_id}`."""
    try:
        req_id = srv.solicitar(entrada.texto, entrada.proyecto_id)
    except KeyError:
        raise HTTPException(404, f"No existe el proyecto {entrada.proyecto_id}")
    return Aceptado(req_id=req_id, estado=Estado.CARGADO)


@router.get("/trazas")
def trazas(srv: ServicioDep, proyecto_id: str | None = None) -> list[dict]:
    """Resumen de los requisitos procesados, opcionalmente de un proyecto."""
    return srv.trazas(proyecto_id)


@router.get("/cola")
def cola(srv: ServicioDep) -> dict:
    """Qué se está procesando y qué espera turno."""
    return srv.cola.estado()


@router.get("/traza/{req_id}", response_model=Traza)
def traza(t: Annotated[Traza, Depends(traza_existente)]) -> Traza:
    return t


@router.get("/eventos/{req_id}", response_class=EventSourceResponse)
async def eventos(
    request: Request,
    srv: ServicioDep,
    t: Annotated[Traza, Depends(traza_existente)],
    desde: int = 0,
    last_event_id: Annotated[str | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    """SSE: `mensaje` por cada mensaje nuevo (id = secuencia), `estado` en cada
    cambio de estado y `fin` al llegar a un estado terminal. Sondea el repositorio
    (ADR 0006). Al reconectar, `Last-Event-ID` evita repetir mensajes."""
    enviados = desde
    if last_event_id and last_event_id.isdigit():
        enviados = max(enviados, int(last_event_id))
    ultimo_estado = None
    while True:
        actual = await run_in_threadpool(srv.traza, t.req_id)
        for m in actual.mensajes:
            if m.secuencia > enviados:
                yield ServerSentEvent(data=m.model_dump(mode="json"), event="mensaje", id=str(m.secuencia))
                enviados = m.secuencia
        if actual.estado != ultimo_estado:
            ultimo_estado = actual.estado
            yield ServerSentEvent(data={"estado": actual.estado.value, "secuencia": enviados}, event="estado")
        if actual.estado in ESTADOS_TERMINALES:
            yield ServerSentEvent(data={"estado": actual.estado.value}, event="fin")
            return
        if await request.is_disconnected():
            return
        await asyncio.sleep(srv.deps.settings.sse_intervalo_s)


@router.post("/validar/{req_id}", status_code=202)
def validar(req_id: str, validacion: Validacion, srv: ServicioDep) -> dict:
    """Aprobar, rechazar o editar. `interpretaciones_editadas` lleva, por término,
    la interpretación elegida (otra existente) o reescrita. Se encola con prioridad."""
    try:
        srv.solicitar_validacion(req_id, validacion)
    except KeyError:
        raise HTTPException(404, f"No existe el requisito {req_id}")
    except ConflictoDeEstado as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"req_id": req_id, "decision": validacion.decision}
