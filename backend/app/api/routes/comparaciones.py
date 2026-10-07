"""Comparación entre requisitos de un proyecto (módulo exploratorio, ADR 0012).

La comparación llama al LLM por cada par seleccionado: siempre pasa por la cola.
Al arrancar la API, el lifespan del router vuelve a encolar las comparaciones que
un reinicio dejó en cola o a medias; así el módulo se quita sin tocar el núcleo.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException

from app import comparacion
from app.comparacion import Comparacion, RequisitosInsuficientes, ResumenComparacion, SinComparador
from app.orchestration import Servicio

from ..dependencias import obtener_servicio
from .proyectos import ProyectoDep

log = logging.getLogger(__name__)


@asynccontextmanager
async def _recuperar_al_arrancar(app: FastAPI):
    # corre dentro del lifespan de la app, que ya armó el servicio y arrancó la cola
    srv = getattr(app.state, "servicio", None)
    if srv is not None:
        try:
            ids = comparacion.recuperar(srv)
            if ids:
                log.info("Comparaciones reencoladas tras el reinicio: %s", ", ".join(ids))
        except Exception:  # una comparación ilegible no debe impedir que arranque la API
            log.exception("No se pudieron recuperar las comparaciones pendientes")
    yield


router = APIRouter(tags=["comparaciones"], lifespan=_recuperar_al_arrancar)
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


@router.post("/proyectos/{proyecto_id}/comparaciones", status_code=202)
def solicitar(p: ProyectoDep, srv: ServicioDep) -> dict:
    """Crea la comparación `en_cola` y la encola. 422 si hay menos de dos requisitos
    comparables; 503 si el servicio no tiene cliente LLM para el comparador."""
    try:
        c = comparacion.solicitar(srv, p.proyecto_id)
    except RequisitosInsuficientes as e:
        raise HTTPException(422, str(e)) from e
    except SinComparador as e:
        raise HTTPException(503, str(e)) from e
    return {"comparacion_id": c.comparacion_id, "estado": c.estado}


@router.get("/proyectos/{proyecto_id}/comparaciones", response_model=list[ResumenComparacion])
def listar(p: ProyectoDep, srv: ServicioDep) -> list[ResumenComparacion]:
    """Resúmenes de las comparaciones del proyecto, la más reciente primero."""
    return comparacion.listar(srv, p.proyecto_id)


@router.get("/comparaciones/{comparacion_id}", response_model=Comparacion)
def obtener(comparacion_id: str, srv: ServicioDep) -> Comparacion:
    c = comparacion.obtener(srv, comparacion_id)
    if c is None:
        raise HTTPException(404, f"No existe la comparación {comparacion_id}")
    return c
