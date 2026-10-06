"""Comparación entre requisitos de un proyecto (módulo exploratorio, ADR 0012).

La comparación llama al LLM por cada par seleccionado: siempre pasa por la cola.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app import comparacion
from app.comparacion import Comparacion, RequisitosInsuficientes, ResumenComparacion
from app.orchestration import Servicio

from ..dependencias import obtener_servicio
from .proyectos import ProyectoDep

router = APIRouter(tags=["comparaciones"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


@router.post("/proyectos/{proyecto_id}/comparaciones", status_code=202)
def solicitar(p: ProyectoDep, srv: ServicioDep) -> dict:
    """Crea la comparación `en_cola` y la encola. 422 si hay menos de dos requisitos comparables."""
    try:
        c = comparacion.solicitar(srv, p.proyecto_id)
    except RequisitosInsuficientes as e:
        raise HTTPException(422, str(e)) from e
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
