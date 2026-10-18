"""Calibración sobre las entrevistas de la versión 2 (ADR 0026).

- `GET /proyectos/{id}/calibracion/entrevistas`: el informe en vivo (solo lectura, ADR 0013).
- `GET|PUT /entrevistas/{id}/etiquetas`: el ground truth de una entrevista. El GET da los
  términos que encontró el Extractor; la similitud y la decisión del sistema solo con
  `?sistema=true`, para poder etiquetar a ciegas.
- Etiquetado por persona (ADR 0029): `GET|POST /entrevistas/{id}/anotaciones`,
  `GET|DELETE /anotaciones/{id}` y `PUT /anotaciones/{id}/respuesta`. A ciegas: los términos se
  entregan sin similitud ni decisión, en el orden barajado que se guardó con su semilla.
- Corridas guardadas: `POST|GET /proyectos/{id}/calibraciones`, `GET|DELETE /calibraciones/{id}`
  y `GET /calibraciones/{id}/overleaf.zip` (el paquete para LaTeX). Borrar deja una lápida: el id
  no se reutiliza.

Nada de esto cambia el umbral: se cambia a mano en `.env`.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.calibracion.anotaciones import (
    COLECCION_ANOTACIONES,
    RESPUESTAS,
    acuerdo,
    completar_orden,
    desde_legado,
    nueva_anotacion,
    responder,
    terminos_para_etiquetar,
)
from app.calibracion.anotaciones import PREFIJO as PREFIJO_ANOTACION
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


def _informe(srv, proyecto_id: str, parametros: dict) -> tuple[dict, list[dict], list[dict]]:
    """El informe del proyecto con sus entrevistas terminadas, y las etiquetas que usó (las de la
    v2.2 y las de cada persona anotadora)."""
    s = srv.deps.settings
    almacen = srv.entrevistas.almacen
    entrevistas = [(e, almacen.bitacora(e["entrevista_id"])) for e in almacen.listar(proyecto_id)
                   if e.get("estado") in TERMINALES and not srv.entrevistas.ocupada(e["entrevista_id"])]
    docs = srv.repo.listar_docs(COLECCION_ETIQUETAS, proyecto_id=proyecto_id)
    anotaciones = srv.repo.listar_docs(COLECCION_ANOTACIONES, proyecto_id=proyecto_id)
    informe = informe_entrevistas(entrevistas, docs, umbral_configurado=s.similarity_threshold,
                                  max_rondas=s.max_debate_rounds, remuestreos=s.calibracion_bootstrap,
                                  semilla=s.calibracion_semilla, proyecto_id=proyecto_id, anotaciones=anotaciones,
                                  **parametros)
    return informe, docs, anotaciones


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
    if c is None or c.get("borrada") or not es_suyo(srv, usuario, c.get("proyecto_id")):
        raise HTTPException(404, f"No existe la corrida {calibracion_id}")
    return c


CorridaDep = Annotated[dict, Depends(corrida_existente)]


@router.post("/proyectos/{proyecto_id}/calibraciones", status_code=201)
def guardar_corrida(entrada: EntradaCorrida, p: ProyectoDep, srv: ServicioDep, request: Request,
                    parametros: ParametrosDep) -> dict:
    """Congela el informe de ahora como una corrida citable (id, fecha, configuración, huellas)."""
    s = srv.deps.settings
    informe, docs, anotaciones = _informe(srv, p.proyecto_id, parametros)
    if not informe["n_valores"]:
        raise HTTPException(422, "No hay similitudes que guardar: procesa al menos una entrevista con términos ambiguos.")
    configuracion = {"umbral": s.similarity_threshold, "max_rondas": s.max_debate_rounds, **parametros,
                     "bootstrap": s.calibracion_bootstrap, "semilla": s.calibracion_semilla,
                     "modelo_embeddings_configurado": s.embedding_model}
    c = srv.repo.crear_doc(COLECCION_CORRIDAS, "C", lambda cid: nueva_corrida(
        cid, informe, nota=entrada.nota, version=request.app.version, configuracion=configuracion,
        docs_etiquetas=docs, anotaciones=anotaciones))
    return resumen_corrida(c)


@router.get("/proyectos/{proyecto_id}/calibraciones")
def listar_corridas(p: ProyectoDep, srv: ServicioDep) -> list[dict]:
    corridas = [c for c in srv.repo.listar_docs(COLECCION_CORRIDAS, proyecto_id=p.proyecto_id) if not c.get("borrada")]
    return [resumen_corrida(c) for c in sorted(corridas, key=lambda c: c["fecha"], reverse=True)]


@router.get("/calibraciones/{calibracion_id}")
def obtener_corrida(c: CorridaDep) -> dict:
    return c


@router.delete("/calibraciones/{calibracion_id}", status_code=204)
def borrar_corrida(c: CorridaDep, srv: ServicioDep) -> Response:
    """Deja una lápida: el id no se reutiliza, así una cita a «C03» siempre es la misma corrida."""
    srv.repo.guardar_doc(COLECCION_CORRIDAS, c["calibracion_id"], {
        "calibracion_id": c["calibracion_id"], "proyecto_id": c["proyecto_id"], "borrada": True,
        "borrada_en": datetime.now(UTC).isoformat(timespec="seconds"), "fecha": c.get("fecha")})
    return Response(status_code=204)


@router.get("/calibraciones/{calibracion_id}/overleaf.zip")
def exportar_corrida(c: CorridaDep) -> Response:
    """Figuras pgfplots, tablas booktabs, datos CSV y la corrida en JSON, listos para Overleaf."""
    nombre = f"dudamel-calibracion-{c['calibracion_id']}.zip"
    return Response(paquete_overleaf(c), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# ---------------------------------------------------------------- etiquetado por persona (ADR 0029)

class NuevaAnotacion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    anotador: str = Field(min_length=1, max_length=120)
    a_ciegas: bool = True


class Respuesta(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    termino: str = Field(min_length=1, max_length=120)
    respuesta: str | None = Field(None, description="si | no | no_se; null la quita")


def _terminos(srv, e: dict) -> list[dict]:
    return terminos_para_etiquetar(e, srv.entrevistas.almacen.bitacora(e["entrevista_id"]))


def _resumen_anotacion(a: dict, terminos: list[dict]) -> dict:
    claves = {t["clave"] for t in terminos}
    return {"anotacion_id": a["anotacion_id"], "anotador": a["anotador"], "a_ciegas": a["a_ciegas"],
            "hechas": sum(1 for k in a["respuestas"] if k in claves), "total": len(claves),
            "por_respuesta": {r: sum(1 for x in a["respuestas"].values() if x["respuesta"] == r) for r in RESPUESTAS},
            "actualizada": a["actualizada"]}


@router.get("/entrevistas/{entrevista_id}/anotaciones")
def anotaciones_de(e: EntrevistaDep, srv: ServicioDep) -> dict:
    """Quién etiquetó esta entrevista, cuánto lleva cada quien y el acuerdo (kappa) entre cada par.
    Incluye el documento de la v2.2, si lo hay, como una persona más."""
    terminos = _terminos(srv, e)
    docs = srv.repo.listar_docs(COLECCION_ANOTACIONES, entrevista_id=e["entrevista_id"])
    legado = srv.repo.obtener_doc(COLECCION_ETIQUETAS, e["entrevista_id"])
    todos = docs + ([desde_legado(legado)] if legado else [])
    return {"entrevista_id": e["entrevista_id"], "titulo": e.get("titulo"), "n_terminos": len(terminos),
            "anotaciones": [_resumen_anotacion(a, terminos) for a in docs],
            "legado": {"anotador": legado.get("anotador"), "n_etiquetas": len(legado.get("etiquetas", []))} if legado else None,
            "acuerdo": acuerdo(todos)}


@router.post("/entrevistas/{entrevista_id}/anotaciones", status_code=201)
def empezar_anotacion(entrada: NuevaAnotacion, e: EntrevistaDep, srv: ServicioDep) -> dict:
    """Empieza (o retoma, si ya existe para esa persona) el etiquetado de una entrevista."""
    if e.get("estado") not in TERMINALES or srv.entrevistas.ocupada(e["entrevista_id"]):
        raise HTTPException(409, "La entrevista no ha terminado de procesarse.")
    existente = next((a for a in srv.repo.listar_docs(COLECCION_ANOTACIONES, entrevista_id=e["entrevista_id"])
                      if normalizar(a["anotador"]) == normalizar(entrada.anotador)), None)
    if existente:
        return existente
    terminos = _terminos(srv, e)
    if not terminos:
        raise HTTPException(422, "Esta entrevista no tiene términos que hayan llegado al mecanismo de divergencia.")
    return srv.repo.crear_doc(COLECCION_ANOTACIONES, PREFIJO_ANOTACION, lambda aid: nueva_anotacion(
        aid, e, terminos, anotador=entrada.anotador, a_ciegas=entrada.a_ciegas))


def anotacion_existente(anotacion_id: str, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    a = srv.repo.obtener_doc(COLECCION_ANOTACIONES, anotacion_id)
    if a is None or not es_suyo(srv, usuario, a.get("proyecto_id")):
        raise HTTPException(404, f"No existe la anotación {anotacion_id}")
    return a


AnotacionDep = Annotated[dict, Depends(anotacion_existente)]


@router.get("/anotaciones/{anotacion_id}")
def ver_anotacion(a: AnotacionDep, srv: ServicioDep) -> dict:
    """El etiquetado de una persona: los términos en su orden barajado, con sus citas y SIN la
    similitud ni la decisión del sistema, y lo que ya contestó (se retoma donde quedó)."""
    e = srv.entrevistas.almacen.obtener(a["entrevista_id"])
    terminos = _terminos(srv, e) if e else []
    if completar_orden(a, terminos):
        srv.repo.guardar_doc(COLECCION_ANOTACIONES, a["anotacion_id"], a)
    por_clave = {t["clave"]: t for t in terminos}
    proyecto = srv.proyectos.obtener(a["proyecto_id"]) if a.get("proyecto_id") else None
    return {**a, "contexto": proyecto.contexto if proyecto else None,
            "titulo": e.get("titulo") if e else None,
            "terminos": [por_clave[k] for k in a["orden"] if k in por_clave]}


@router.put("/anotaciones/{anotacion_id}/respuesta")
def responder_termino(entrada: Respuesta, a: AnotacionDep, srv: ServicioDep) -> dict:
    try:
        responder(a, termino=entrada.termino, respuesta=entrada.respuesta)
    except ValueError as err:
        raise HTTPException(422, str(err)) from err
    srv.repo.guardar_doc(COLECCION_ANOTACIONES, a["anotacion_id"], a)
    return {"respuestas": a["respuestas"], "actualizada": a["actualizada"]}


@router.delete("/anotaciones/{anotacion_id}", status_code=204)
def borrar_anotacion(a: AnotacionDep, srv: ServicioDep) -> Response:
    srv.repo.borrar_doc(COLECCION_ANOTACIONES, a["anotacion_id"])
    return Response(status_code=204)
