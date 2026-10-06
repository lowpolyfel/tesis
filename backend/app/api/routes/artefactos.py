"""Artefactos de salida (ADR 0011): modelo de metas y Big Picture del proyecto, y
los artefactos de un requisito. Solo lectura y sin LLM: se recalculan en cada
petición a partir de `formalizados` y del LEL del proyecto."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.artefactos import (
    artefactos_requisito,
    big_picture_proyecto,
    formas,
    metas_proyecto,
)
from app.models import Traza
from app.orchestration import Servicio
from app.orchestration.grafo import COLECCION_FORMALIZADOS

from ..dependencias import obtener_servicio, traza_existente
from .proyectos import ProyectoDep

router = APIRouter(tags=["artefactos"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


def _insumos(proyecto_id: str, srv: Servicio) -> tuple[list[dict], list, list[dict]]:
    repo = srv.repo
    return (repo.listar_docs(COLECCION_FORMALIZADOS, proyecto_id=proyecto_id), repo.listar_lel(proyecto_id),
            repo.listar_trazas(proyecto_id))


@router.get("/proyectos/{proyecto_id}/metas", response_model=formas.MetasProyecto)
def metas(p: ProyectoDep, srv: ServicioDep) -> dict:
    """Metas de todos los requisitos formalizados con id global, actores normalizados
    (más los sujetos del LEL), conteo por tipo y expresiones vagas candidatas a metas blandas."""
    formalizados, lel, trazas = _insumos(p.proyecto_id, srv)
    return metas_proyecto(formalizados, lel, trazas, srv.deps.analizador)


@router.get("/proyectos/{proyecto_id}/big-picture", response_model=formas.BigPicture)
def big_picture(p: ProyectoDep, srv: ServicioDep) -> dict:
    """Grafo de conocimiento (nodos y aristas), panorama para la interfaz y su
    exportación a Mermaid y PlantUML."""
    formalizados, lel, trazas = _insumos(p.proyecto_id, srv)
    return big_picture_proyecto(formalizados, lel, trazas, srv.deps.analizador)


@router.get("/requisitos/{req_id}/artefactos", response_model=formas.ArtefactosRequisito)
def requisito(t: Annotated[Traza, Depends(traza_existente)], srv: ServicioDep) -> dict:
    """Documento formalizado (o null), entradas del LEL que salieron del requisito y sus metas."""
    return artefactos_requisito(t.req_id, t.proyecto_id, t.estado.value,
                                srv.repo.obtener_doc(COLECCION_FORMALIZADOS, t.req_id),
                                srv.repo.listar_lel(t.proyecto_id), srv.deps.analizador)
