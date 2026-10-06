"""Calibración del umbral como análisis de sensibilidad (ADR 0013). Solo lectura:
muestra qué habría decidido el mecanismo con otros umbrales; nunca cambia la
configuración (el umbral se cambia en `.env` y cada traza guarda el suyo)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.calibracion import COLECCION_EVALUACIONES, formas, informe_calibracion
from app.orchestration import Servicio

from ..dependencias import obtener_servicio
from .proyectos import ProyectoDep

router = APIRouter(tags=["calibracion"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]

# Resolución mínima, solo protege el tamaño de la respuesta: con umbrales en [0, 1] da a lo
# más 1001 filas y, como el coseno está en [-1, 1] y el histograma usa el paso como ancho,
# a lo más 2001 bins. No cambia ningún resultado.
PASO_MINIMO = 0.001


def parametros_rejilla(
    srv: ServicioDep,
    desde: Annotated[float | None, Query(ge=0.0, le=1.0, description="omitido: CALIBRACION_DESDE")] = None,
    hasta: Annotated[float | None, Query(ge=0.0, le=1.0, description="omitido: CALIBRACION_HASTA")] = None,
    paso: Annotated[float | None, Query(gt=0.0, le=1.0, description="omitido: CALIBRACION_PASO")] = None,
) -> dict:
    s = srv.deps.settings
    desde = s.calibracion_desde if desde is None else desde
    hasta = s.calibracion_hasta if hasta is None else hasta
    paso = s.calibracion_paso if paso is None else paso
    if desde >= hasta:
        raise HTTPException(422, f"desde ({desde}) debe ser menor que hasta ({hasta})")
    if paso < PASO_MINIMO:
        raise HTTPException(422, f"el paso ({paso}) debe ser al menos {PASO_MINIMO}")
    return {"desde": desde, "hasta": hasta, "paso": paso}


ParametrosDep = Annotated[dict, Depends(parametros_rejilla)]


def _informe(srv: Servicio, trazas, docs, parametros: dict, proyecto_id: str | None) -> dict:
    s = srv.deps.settings
    return informe_calibracion(trazas, docs, umbral_configurado=s.similarity_threshold,
                               max_rondas=s.max_debate_rounds, proyecto_id=proyecto_id, **parametros)


@router.get("/proyectos/{proyecto_id}/calibracion", response_model=formas.Calibracion)
def calibracion_proyecto(p: ProyectoDep, srv: ServicioDep, parametros: ParametrosDep) -> dict:
    """Sensibilidad del umbral sobre las similitudes iniciales del proyecto y, si la
    evaluación dejó etiquetas para él, su contraste con el ground truth."""
    docs = srv.repo.listar_docs(COLECCION_EVALUACIONES, proyecto_id=p.proyecto_id)
    return _informe(srv, srv.repo.trazas_completas(p.proyecto_id), docs, parametros, p.proyecto_id)


@router.get("/calibracion", response_model=formas.Calibracion)
def calibracion_general(srv: ServicioDep, parametros: ParametrosDep) -> dict:
    """Lo mismo con todos los proyectos que no son de evaluación juntos (`proyecto_id: null`)."""
    proyectos = srv.proyectos.listar()
    de_evaluacion = {p.proyecto_id for p in proyectos if p.tipo == "evaluacion"}
    trazas = [t for t in srv.repo.trazas_completas() if t.proyecto_id not in de_evaluacion]
    incluidos = {p.proyecto_id for p in proyectos if p.tipo != "evaluacion"} | {t.proyecto_id for t in trazas}
    docs = [d for d in srv.repo.listar_docs(COLECCION_EVALUACIONES) if d.get("proyecto_id") in incluidos]
    return _informe(srv, trazas, docs, parametros, None)
