"""Corpus y evaluación contra un solo agente (ADR 0014).

La evaluación llama a los LLM (grafo y línea base): siempre pasa por la cola.
Las métricas se calculan al vuelo desde las trazas, el ground truth guardado y la
línea base.

Al arrancar la API, el lifespan del router vuelve a encolar la línea base y el
cierre de las evaluaciones que un reinicio dejó a medias (como en comparaciones).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import evaluacion
from app.evaluacion import CorpusInvalido, CorpusNoEncontrado, SinAgenteUnico, formas
from app.evaluacion.corpus import PATRON_NOMBRE
from app.orchestration import Servicio

from ..dependencias import obtener_servicio

log = logging.getLogger(__name__)


@asynccontextmanager
async def _recuperar_al_arrancar(app: FastAPI):
    # corre dentro del lifespan de la app, que ya armó el servicio y arrancó la cola
    srv = getattr(app.state, "servicio", None)
    if srv is not None:
        try:
            ids = evaluacion.recuperar(srv)
            if ids:
                log.info("Evaluaciones reencoladas tras el reinicio: %s", ", ".join(ids))
        except Exception:  # una evaluación ilegible no debe impedir que arranque la API
            log.exception("No se pudieron recuperar las evaluaciones pendientes")
    yield


router = APIRouter(tags=["evaluaciones"], lifespan=_recuperar_al_arrancar)
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


class EntradaEvaluacion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    corpus: str = Field(pattern=PATRON_NOMBRE)
    nombre: str | None = Field(None, min_length=1, max_length=120)


def _invalido(e: CorpusInvalido) -> HTTPException:
    return HTTPException(422, {"mensaje": f"El corpus «{e.nombre}» no es válido", "errores": e.errores})


@router.post("/evaluaciones", status_code=202, response_model=formas.EvaluacionCreada)
def crear(entrada: EntradaEvaluacion, srv: ServicioDep) -> dict:
    """Crea el proyecto de evaluación, encola los requisitos del corpus y la línea base.
    404 si el corpus no existe, 422 si no es válido, 503 sin cliente para la línea base."""
    try:
        ev = evaluacion.solicitar(srv, entrada.corpus, entrada.nombre)
    except CorpusNoEncontrado as e:
        raise HTTPException(404, f"No existe el corpus {entrada.corpus}") from e
    except CorpusInvalido as e:
        raise _invalido(e) from e
    except SinAgenteUnico as e:
        raise HTTPException(503, str(e)) from e
    return {"evaluacion_id": ev.evaluacion_id, "proyecto_id": ev.proyecto_id, "total": len(ev.items)}


@router.get("/evaluaciones", response_model=list[formas.ResumenEvaluacion])
def listar(srv: ServicioDep) -> list[dict]:
    """Resúmenes con su progreso, la más reciente primero."""
    return evaluacion.listar(srv)


@router.get("/evaluaciones/{evaluacion_id}", response_model=formas.InformeEvaluacion)
def obtener(evaluacion_id: str, srv: ServicioDep) -> dict:
    r = evaluacion.informe(srv, evaluacion_id)
    if r is None:
        raise HTTPException(404, f"No existe la evaluación {evaluacion_id}")
    return r


@router.get("/corpus", response_model=list[formas.ResumenCorpus])
def listar_corpus(srv: ServicioDep) -> list[dict]:
    """Corpus disponibles con sus conteos; los inválidos aparecen con sus errores."""
    return evaluacion.listar_corpus(srv)


@router.get("/corpus/{nombre}", response_model=formas.DetalleCorpus)
def obtener_corpus(nombre: str, srv: ServicioDep) -> dict:
    """Requisitos con su ground truth (pantalla Corpus). 404 si no existe, 422 si no es válido."""
    try:
        return evaluacion.detalle_corpus(srv, nombre)
    except CorpusNoEncontrado as e:
        raise HTTPException(404, f"No existe el corpus {nombre}") from e
    except CorpusInvalido as e:
        raise _invalido(e) from e
