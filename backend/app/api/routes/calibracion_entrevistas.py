"""Calibración sobre las entrevistas de la versión 2 (ADR 0026).

- `GET /proyectos/{id}/calibracion/entrevistas`: el informe en vivo (solo lectura, ADR 0013).
- `GET|PUT /entrevistas/{id}/etiquetas`: el ground truth de una entrevista. El GET da los
  términos que encontró el Extractor; la similitud y la decisión del sistema solo con
  `?sistema=true`, para poder etiquetar a ciegas.
- Corridas guardadas: `POST|GET /proyectos/{id}/calibraciones`, `GET|DELETE /calibraciones/{id}`
  y `GET /calibraciones/{id}/overleaf.zip` (el paquete para LaTeX).

Nada de esto cambia el umbral: se cambia a mano en `.env`.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.calibracion.entrevistas import (
    COLECCION_ETIQUETAS,
    EtiquetadoEntrevista,
    similitudes_de_entrevista,
    terminos_de_entrevista,
)
from app.calibracion.informe_entrevistas import (
    COLECCION_CORRIDAS,
    informe_entrevistas,
    nueva_corrida,
    resumen_corrida,
)
from app.calibracion.latex import paquete_overleaf
from app.entrevistas.almacen import TERMINALES
from app.nlp import normalizar

from ..dependencias import UsuarioDep, es_suyo
from .calibracion import ParametrosDep, ServicioDep
from .entrevistas import EntrevistaDep
from .proyectos import ProyectoDep

router = APIRouter(tags=["calibracion"])


def _informe(srv, proyecto_id: str, parametros: dict) -> tuple[dict, list[dict]]:
    """El informe del proyecto con sus entrevistas terminadas, y las etiquetas que usó."""
    s = srv.deps.settings
    almacen = srv.entrevistas.almacen
    entrevistas = [(e, almacen.bitacora(e["entrevista_id"])) for e in almacen.listar(proyecto_id)
                   if e.get("estado") in TERMINALES and not srv.entrevistas.ocupada(e["entrevista_id"])]
    docs = srv.repo.listar_docs(COLECCION_ETIQUETAS, proyecto_id=proyecto_id)
    informe = informe_entrevistas(entrevistas, docs, umbral_configurado=s.similarity_threshold,
                                  max_rondas=s.max_debate_rounds, remuestreos=s.calibracion_bootstrap,
                                  semilla=s.calibracion_semilla, proyecto_id=proyecto_id, **parametros)
    return informe, docs


@router.get("/proyectos/{proyecto_id}/calibracion/entrevistas")
def calibracion_entrevistas(p: ProyectoDep, srv: ServicioDep, parametros: ParametrosDep) -> dict:
    """Sensibilidad del umbral sobre las similitudes iniciales de las entrevistas del proyecto y su
    contraste con el ground truth (ROC, AUC, intervalos bootstrap, por tipo)."""
    return _informe(srv, p.proyecto_id, parametros)[0]


# ---------------------------------------------------------------- ground truth

@router.get("/entrevistas/{entrevista_id}/etiquetas")
def etiquetas(e: EntrevistaDep, srv: ServicioDep,
              sistema: Annotated[bool, Query(description="incluir la similitud y la decisión del sistema")] = False) -> dict:
    """{entrevista_id, titulo, terminos: [{termino, decision_filtro, (similitud, decision, tipo_sistema)}],
    etiquetado: {anotador, a_ciegas, etiquetas, actualizada} | null}"""
    b = srv.entrevistas.almacen.bitacora(e["entrevista_id"])
    terminos = terminos_de_entrevista(b)
    if sistema:
        por_clave = {normalizar(v["termino"]): v for v in similitudes_de_entrevista(e, b)}
        terminos = [{**t, **({"similitud": v["similitud"], "decision": v["decision_real"], "tipo_sistema": v["tipo_ambiguedad"]}
                             if (v := por_clave.get(normalizar(t["termino"]))) else {})} for t in terminos]
    return {"entrevista_id": e["entrevista_id"], "titulo": e.get("titulo"), "estado": e.get("estado"),
            "terminos": terminos, "etiquetado": srv.repo.obtener_doc(COLECCION_ETIQUETAS, e["entrevista_id"])}


@router.put("/entrevistas/{entrevista_id}/etiquetas")
def guardar_etiquetas(entrada: EtiquetadoEntrevista, e: EntrevistaDep, srv: ServicioDep) -> dict:
    """Reemplaza el ground truth de la entrevista. Un término repetido cuenta una vez (el último)."""
    unicas = {normalizar(x.termino): x.model_dump(mode="json") for x in entrada.etiquetas}
    for x in unicas.values():
        if not x["ambiguo"]:
            x["tipo"] = None
    doc = {"entrevista_id": e["entrevista_id"], "proyecto_id": e["proyecto_id"], "anotador": entrada.anotador,
           "a_ciegas": entrada.a_ciegas, "etiquetas": list(unicas.values()),
           "actualizada": datetime.now(UTC).isoformat(timespec="seconds")}
    srv.repo.guardar_doc(COLECCION_ETIQUETAS, e["entrevista_id"], doc)
    return doc


# ---------------------------------------------------------------- corridas guardadas

class EntradaCorrida(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nota: str | None = Field(None, max_length=500)


def corrida_existente(calibracion_id: str, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    c = srv.repo.obtener_doc(COLECCION_CORRIDAS, calibracion_id)
    if c is None or not es_suyo(srv, usuario, c.get("proyecto_id")):
        raise HTTPException(404, f"No existe la corrida {calibracion_id}")
    return c


CorridaDep = Annotated[dict, Depends(corrida_existente)]


@router.post("/proyectos/{proyecto_id}/calibraciones", status_code=201)
def guardar_corrida(entrada: EntradaCorrida, p: ProyectoDep, srv: ServicioDep, request: Request,
                    parametros: ParametrosDep) -> dict:
    """Congela el informe de ahora como una corrida citable (id, fecha, configuración, huellas)."""
    s = srv.deps.settings
    informe, docs = _informe(srv, p.proyecto_id, parametros)
    if not informe["n_valores"]:
        raise HTTPException(422, "No hay similitudes que guardar: procesa al menos una entrevista con términos ambiguos.")
    configuracion = {"umbral": s.similarity_threshold, "max_rondas": s.max_debate_rounds, **parametros,
                     "bootstrap": s.calibracion_bootstrap, "semilla": s.calibracion_semilla,
                     "modelo_embeddings_configurado": s.embedding_model}
    c = srv.repo.crear_doc(COLECCION_CORRIDAS, "C", lambda cid: nueva_corrida(
        cid, informe, nota=entrada.nota, version=request.app.version, configuracion=configuracion,
        docs_etiquetas=docs))
    return resumen_corrida(c)


@router.get("/proyectos/{proyecto_id}/calibraciones")
def listar_corridas(p: ProyectoDep, srv: ServicioDep) -> list[dict]:
    corridas = srv.repo.listar_docs(COLECCION_CORRIDAS, proyecto_id=p.proyecto_id)
    return [resumen_corrida(c) for c in sorted(corridas, key=lambda c: c["fecha"], reverse=True)]


@router.get("/calibraciones/{calibracion_id}")
def obtener_corrida(c: CorridaDep) -> dict:
    return c


@router.delete("/calibraciones/{calibracion_id}", status_code=204)
def borrar_corrida(c: CorridaDep, srv: ServicioDep) -> Response:
    srv.repo.borrar_doc(COLECCION_CORRIDAS, c["calibracion_id"])
    return Response(status_code=204)


@router.get("/calibraciones/{calibracion_id}/overleaf.zip")
def exportar_corrida(c: CorridaDep) -> Response:
    """Figuras pgfplots, tablas booktabs, datos CSV y la corrida en JSON, listos para Overleaf."""
    nombre = f"dudamel-calibracion-{c['calibracion_id']}.zip"
    return Response(paquete_overleaf(c), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
