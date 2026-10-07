"""Vistas derivadas de las trazas para el frontend (ADR 0015). Solo lectura: el
frontend no reconstruye la traza a mano; aquí se arma la vista por término."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.analisis import (
    CatalogoInvalido,
    ambiguedades_proyecto,
    configuracion_vigente,
    flujo_proyecto,
    formas,
    leer_catalogos,
    resumen_proyecto,
    vista_requisito,
)
from app.models import Traza
from app.orchestration import Servicio
from app.orchestration.grafo import COLECCION_FORMALIZADOS

from ..dependencias import obtener_servicio, traza_existente
from .proyectos import ProyectoDep

router = APIRouter(tags=["analisis"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


@router.get("/requisitos/{req_id}", response_model=formas.VistaRequisito)
def requisito(t: Annotated[Traza, Depends(traza_existente)], srv: ServicioDep) -> dict:
    """Vista completa del requisito por término: marcados, interpretaciones I1..In,
    divergencia, rondas, resolución, validación y formalización."""
    return vista_requisito(t, srv.repo.obtener_doc(COLECCION_FORMALIZADOS, t.req_id))


@router.get("/proyectos/{proyecto_id}/resumen", response_model=formas.ResumenProyecto)
def resumen(p: ProyectoDep, srv: ServicioDep) -> dict:
    """Contadores, estados por ciclo y el resumen ligero de cada requisito."""
    return resumen_proyecto(p, srv.repo.trazas_completas(p.proyecto_id), srv.repo.listar_lel(p.proyecto_id))


@router.get("/proyectos/{proyecto_id}/ambiguedades", response_model=formas.AmbiguedadesProyecto)
def ambiguedades(p: ProyectoDep, srv: ServicioDep) -> dict:
    """Ambigüedades agrupadas por término, con inconsistencias entre requisitos y en el LEL."""
    return ambiguedades_proyecto(srv.repo.trazas_completas(p.proyecto_id), srv.repo.listar_lel(p.proyecto_id))


@router.get("/proyectos/{proyecto_id}/flujo", response_model=formas.FlujoProyecto)
def flujo(p: ProyectoDep, srv: ServicioDep) -> dict:
    """Métricas del ciclo KMoS-SSA por ciclo y del proyecto."""
    return flujo_proyecto(srv.repo.trazas_completas(p.proyecto_id), srv.repo.listar_lel(p.proyecto_id))


@router.get("/configuracion", response_model=formas.Configuracion)
def configuracion(srv: ServicioDep) -> dict:
    """Configuración vigente (solo lectura): se cambia en `.env` y cada traza guarda la suya."""
    return configuracion_vigente(srv.deps.settings, srv.deps.config_traza())


@router.get("/catalogos", response_model=formas.Catalogos)
def catalogos(srv: ServicioDep) -> dict:
    """Catálogos de términos regionales y de vaguedad, tal cual están en disco."""
    s = srv.deps.settings
    try:
        return leer_catalogos(s.ruta(s.catalogos_dir))
    except CatalogoInvalido as e:  # editado a mano en disco: que el error diga cuál y por qué
        raise HTTPException(500, f"catálogo mal formado: {e}") from e
