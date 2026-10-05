"""Procesar un requisito, seguir su traza en vivo y validarlo."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ConfigDict, Field

from app.models import ESTADOS_TERMINALES, Estado, Traza, Validacion
from app.orchestration import ConflictoDeEstado, Servicio

from ..dependencias import obtener_servicio, traza_existente

router = APIRouter(tags=["requisitos"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


class EntradaProcesar(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    texto: str = Field(min_length=1, max_length=2000)


class Aceptado(BaseModel):
    req_id: str
    estado: Estado


@router.post("/procesar", status_code=202, response_model=Aceptado)
def procesar(entrada: EntradaProcesar, tareas: BackgroundTasks, srv: ServicioDep) -> Aceptado:
    """Registra el requisito y corre el grafo en segundo plano; los mensajes se
    siguen en `/eventos/{req_id}`."""
    req_id = srv.registrar(entrada.texto)
    tareas.add_task(srv.ejecutar, req_id)
    return Aceptado(req_id=req_id, estado=Estado.CARGADO)


@router.get("/trazas")
def trazas(srv: ServicioDep) -> list[dict]:
    """Resumen de los requisitos procesados (para reabrir uno desde la sandbox)."""
    return srv.trazas()


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
def validar(req_id: str, validacion: Validacion, tareas: BackgroundTasks, srv: ServicioDep) -> dict:
    """Aprobar, rechazar o editar. `interpretaciones_editadas` lleva, por término,
    la interpretación elegida (otra existente) o reescrita."""
    try:
        srv.preparar_validacion(req_id, validacion)
    except KeyError:
        raise HTTPException(404, f"No existe el requisito {req_id}")
    except ConflictoDeEstado as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    tareas.add_task(srv.reanudar, req_id, validacion)
    return {"req_id": req_id, "decision": validacion.decision}
