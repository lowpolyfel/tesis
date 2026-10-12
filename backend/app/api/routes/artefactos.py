"""Artefactos de salida (ADR 0011): modelo de metas y Big Picture del proyecto, y
los artefactos de un requisito. No escriben nada ni llaman a un LLM: se recalculan en cada
petición a partir de `formalizados` y del LEL del proyecto.

El mapa conceptual (ADR 0020) es la excepción: lo organiza el Modelador, así que se
guarda y solo se vuelve a generar cuando cambia lo validado o se pide."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.artefactos import (
    artefactos_requisito,
    big_picture_proyecto,
    especificacion_proyecto,
    formas,
    metas_proyecto,
)
from app.artefactos import mapa_conceptual as mc
from app.llm.perfiles import con_perfil
from app.models import Proyecto, Traza
from app.orchestration import Servicio
from app.orchestration.grafo import COLECCION_FORMALIZADOS

from ..dependencias import obtener_servicio, traza_existente
from .proyectos import ProyectoDep

router = APIRouter(tags=["artefactos"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


def _insumos(proyecto_id: str, srv: Servicio) -> tuple[list[dict], list, list[dict]]:
    # las trazas primero: el Modelador guarda el LEL y el documento antes de pasar
    # la traza a `formalizado`, así que lo que se lee después ya los incluye
    repo = srv.repo
    trazas = repo.listar_trazas(proyecto_id)
    return repo.listar_docs(COLECCION_FORMALIZADOS, proyecto_id=proyecto_id), repo.listar_lel(proyecto_id), trazas


def _seleccion(req_ids: str | None) -> set[str] | None:
    """`?req_ids=R01,R03`: solo esos requisitos (ADR 0017); vacío o ausente, todos."""
    ids = {r.strip() for r in (req_ids or "").split(",") if r.strip()}
    return ids or None


@router.get("/proyectos/{proyecto_id}/metas", response_model=formas.MetasProyecto)
def metas(p: ProyectoDep, srv: ServicioDep, req_ids: str | None = None) -> dict:
    """Metas de los requisitos formalizados con id global, actores normalizados
    (más los sujetos del LEL), conteo por tipo y expresiones vagas candidatas a metas blandas."""
    formalizados, lel, trazas = _insumos(p.proyecto_id, srv)
    return metas_proyecto(formalizados, lel, trazas, srv.deps.analizador, _seleccion(req_ids))


@router.get("/proyectos/{proyecto_id}/big-picture", response_model=formas.BigPicture)
def big_picture(p: ProyectoDep, srv: ServicioDep, req_ids: str | None = None) -> dict:
    """Grafo de conocimiento (nodos y aristas), panorama para la interfaz y su
    exportación a Mermaid y PlantUML. Con `req_ids`, el de esos requisitos."""
    formalizados, lel, trazas = _insumos(p.proyecto_id, srv)
    return big_picture_proyecto(formalizados, lel, trazas, srv.deps.analizador, _seleccion(req_ids))


@router.get("/proyectos/{proyecto_id}/especificacion", response_model=formas.Especificacion)
def especificacion(p: ProyectoDep, srv: ServicioDep, req_ids: str | None = None) -> dict:
    """Requisitos funcionales y no funcionales reescritos, con sus supuestos, y el glosario (LEL)."""
    formalizados, lel, trazas = _insumos(p.proyecto_id, srv)
    return especificacion_proyecto(formalizados, lel, trazas, _seleccion(req_ids))


@router.get("/requisitos/{req_id}/artefactos", response_model=formas.ArtefactosRequisito)
def requisito(t: Annotated[Traza, Depends(traza_existente)], srv: ServicioDep) -> dict:
    """Documento formalizado (o null), entradas del LEL que salieron del requisito y sus
    metas, con los actores nombrados como en el modelo de metas del proyecto."""
    formalizados, lel, trazas = _insumos(t.proyecto_id, srv)
    return artefactos_requisito(t.req_id, t.proyecto_id, t.estado.value,
                                srv.repo.obtener_doc(COLECCION_FORMALIZADOS, t.req_id), lel, srv.deps.analizador,
                                formalizados, trazas)


# ---------------------------------------------------------------- mapa conceptual (ADR 0020)

class EntradaMapa(BaseModel):
    model_config = ConfigDict(extra="forbid")
    req_ids: list[str] = Field(default=[], max_length=500)
    nuevo: bool = False  # volver a generarlo aunque haya uno guardado


def _mapa_guardado(p: Proyecto, srv: Servicio, solo: set[str] | None) -> tuple[dict, str, dict | None]:
    """(Big Picture, huella, mapa guardado si sigue al día)."""
    formalizados, lel, trazas = _insumos(p.proyecto_id, srv)
    bp = big_picture_proyecto(formalizados, lel, trazas, srv.deps.analizador, solo)
    with con_perfil(srv.perfil(p.proyecto_id)):  # el modelo que eligió la cuenta (ADR 0021)
        modelo = srv.deps.modelador.cliente.modelo
    h = mc.huella(bp, p.nombre, p.contexto, modelo, solo)
    doc = srv.repo.obtener_doc(mc.COLECCION, mc.id_guardado(p.proyecto_id, solo))
    return bp, h, (doc["mapa"] if doc and doc.get("huella") == h else None)


@router.get("/proyectos/{proyecto_id}/mapa-conceptual")
def mapa_guardado(p: ProyectoDep, srv: ServicioDep, req_ids: str | None = None) -> dict:
    """{mapa, requisitos}: el mapa guardado si lo validado no cambió desde que se generó
    (si no, null) y cuántos requisitos listos entran."""
    bp, _, mapa = _mapa_guardado(p, srv, _seleccion(req_ids))
    return {"mapa": mapa, "requisitos": sum(n["tipo"] == "requisito" for n in bp["nodos"])}


@router.post("/proyectos/{proyecto_id}/mapa-conceptual")
def generar_mapa(entrada: EntradaMapa, p: ProyectoDep, srv: ServicioDep) -> StreamingResponse:
    """Genera el mapa y va diciendo qué hace: una línea JSON por evento (NDJSON).
    {"tipo": "paso", id, texto, estado: curso|ok|aviso, detalle} · {"tipo": "mapa", mapa} ·
    {"tipo": "error", mensaje}. Con un mapa al día guardado y sin `nuevo`, solo ese."""
    solo = {r.strip() for r in entrada.req_ids if r.strip()} or None

    def eventos():
        bp, h, guardado = _mapa_guardado(p, srv, solo)
        if guardado is not None and not entrada.nuevo:
            yield {"tipo": "mapa", "mapa": guardado}
            return
        if not any(n["tipo"] == "requisito" for n in bp["nodos"]):
            yield {"tipo": "error", "mensaje": "El mapa se arma con los requisitos listos. Todavía no hay ninguno."}
            return
        for e in mc.generar_mapa(bp, p.nombre, p.contexto, srv.deps.modelador, srv.perfil(p.proyecto_id)):
            if e["tipo"] == "mapa":
                e["mapa"]["creado"] = datetime.now(UTC).isoformat(timespec="seconds")
                srv.repo.guardar_doc(mc.COLECCION, mc.id_guardado(p.proyecto_id, solo), {
                    "proyecto_id": p.proyecto_id, "seleccion": sorted(solo or []), "huella": h, "mapa": e["mapa"]})
            yield e

    lineas = (json.dumps(e, ensure_ascii=False) + "\n" for e in eventos())
    return StreamingResponse(lineas, media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})
