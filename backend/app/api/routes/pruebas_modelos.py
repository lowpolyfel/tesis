"""Prueba de modelos con el banco de términos ambiguos (ADR 0027, 0028 y 0029).

- `GET /bancos/ambiguedad?version=`: un banco (el más nuevo si no se pide versión).
- `GET /rubricas/revision`: la rúbrica de la revisión humana (la misma del apéndice).
- `GET /pruebas-modelos/modelos`: los modelos que esta cuenta puede probar.
- `POST /pruebas-modelos`: crea una prueba (o una serie de `repeticiones` corridas idénticas) y
  la corre en segundo plano.
- `GET /pruebas-modelos`, `GET|DELETE /pruebas-modelos/{id}`: listar, ver y borrar (borrar deja
  una lápida: el número no se reutiliza).
- `POST /pruebas-modelos/{id}/cancelar`, `/reanudar` y `/repetir` (más corridas de la serie).
- `GET /pruebas-modelos/series/{serie}`: la estabilidad entre las corridas de una serie.
- Revisión de calidad: `GET|POST|DELETE /pruebas-modelos/{id}/revision-calidad` y
  `PUT|DELETE /pruebas-modelos/{id}/revision-calidad/marca`.
- Revisión fuera del sistema (ADR 0030): `GET /pruebas-modelos/{id}/revision-calidad/exportar`
  (Markdown o JSON a ciegas, para que lo conteste una persona o una IA) y
  `POST /pruebas-modelos/{id}/revision-calidad/importar` (las respuestas, con su origen).
- `PUT /pruebas-modelos/{id}/modos`: el modo de falla de un falso negativo.
- `GET /pruebas-modelos/{id}/overleaf.zip`: el paquete para LaTeX.

La revisión ✓/✗ de la v2.3 (`revisiones_modelos`) ya no se escribe: se lee y se reporta aparte,
con su criterio viejo. Cada prueba es de la cuenta que la creó.
"""
from __future__ import annotations

import copy
import json
import threading
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.calibracion import calidad as cal
from app.calibracion import intercambio
from app.calibracion.estabilidad import estabilidad
from app.calibracion.latex_modelos import paquete_overleaf
from app.calibracion.pruebas_modelos import (
    COLECCION_PRUEBAS,
    COLECCION_REVISIONES,
    EJECUTOR,
    PREFIJO,
    TERMINALES,
    al_dia,
    banco,
    banco_de,
    codigo_de,
    es_ambiguo,
    lapida,
    nueva_prueba,
    resolver,
    resumen,
    resumen_corto,
)
from app.calibracion.rubrica import CLAVES, publica
from app.llm.proveedores import CATALOGO, FalloProveedor, listar_modelos

from ..dependencias import UsuarioDep
from .calibracion import ServicioDep

router = APIRouter(tags=["calibracion"])
_CANDADO = threading.Lock()  # las marcas llegan de una en una y se guardan sobre el mismo documento


class ModeloElegido(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    proveedor: str = Field(min_length=1, max_length=40)
    modelo: str = Field(min_length=1, max_length=200)


class EntradaPrueba(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    modelos: list[ModeloElegido] = Field(min_length=1, max_length=8)
    items: list[str] | None = Field(None, description="ids del banco (B01…); vacío o null = todos")
    banco: str | None = Field(None, pattern=r"^v\d+$", description="versión del banco; null = la más nueva")
    nota: str | None = Field(None, max_length=500)
    repeticiones: int = Field(1, ge=1, le=10, description="corridas idénticas (serie) para medir la estabilidad")


class Repetir(BaseModel):
    model_config = ConfigDict(extra="forbid")
    veces: int = Field(1, ge=1, le=10)


class NuevaRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revisor: str = Field(min_length=1, max_length=120)
    a_ciegas: bool = Field(True, description="ocultar proveedor y modelo; con nombres es una opción explícita")


class MarcaCalidad(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    modelo: str = Field(pattern=r"^M\d+$")
    item: str = Field(pattern=r"^B\d+$")
    fidelidad: bool
    delimitacion: bool
    intencion: bool
    cobertura: list[int] = Field(default_factory=list, max_length=10, description="índices de las lecturas esperadas cubiertas")
    nota: str | None = Field(None, max_length=500)


class Importacion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    contenido: str = Field(min_length=2, max_length=3_000_000, description="el archivo contestado (Markdown o JSON)")
    tipo: str = Field(pattern=r"^(persona|ia)$", description="quién lo contestó: una persona o una IA")
    quien: str = Field(min_length=1, max_length=120, description="nombre de la persona, o proveedor y modelo de la IA")
    sobrescribir: bool = Field(False, description="pisar lo ya marcado; por omisión se conserva y se mide el acuerdo")


class Modo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    modelo: str = Field(pattern=r"^M\d+$")
    item: str = Field(pattern=r"^B\d+$")
    modo: str | None = Field(None, max_length=40, description="clave del catálogo; null la quita")
    nota: str | None = Field(None, max_length=500)


@router.get("/bancos/ambiguedad")
def ver_banco(version: str | None = None) -> dict:
    try:
        return banco(version)
    except KeyError as e:
        raise HTTPException(404, f"No existe el banco {version}") from e


@router.get("/rubricas/revision")
def ver_rubrica() -> dict:
    """Criterios, cobertura, etiqueta de entrevista y modos de falla, con el Markdown del apéndice."""
    return publica()


@router.get("/pruebas-modelos/modelos")
def modelos_disponibles(srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """{proveedores: [{id, nombre, modelos: [{id, nombre}], error}]}: los proveedores con clave
    guardada en la cuenta y Ollama (con su URL o la del servidor). La lista la da cada proveedor."""
    publico = srv.perfiles.publico(usuario.usuario_id)["proveedores"]
    salida = []
    for p in CATALOGO:
        if p.id == "compatible" and not srv.perfiles.url_guardada(usuario.usuario_id, p.id):
            continue
        if p.pide_clave and not publico.get(p.id, {}).get("tiene_clave"):
            continue
        try:
            eleccion = resolver(srv, usuario.usuario_id, {"proveedor": p.id, "modelo": "-"})
            modelos, error = listar_modelos(eleccion), None
        except (FalloProveedor, ValueError) as e:
            modelos, error = [], str(e)
        salida.append({"id": p.id, "nombre": p.nombre, "modelos": modelos, "sugeridos": list(p.modelos), "error": error})
    return {"proveedores": salida}


def prueba_existente(prueba_id: str, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    p = srv.repo.obtener_doc(COLECCION_PRUEBAS, prueba_id)
    if p is None or p.get("borrada") or p.get("usuario_id") != usuario.usuario_id:
        raise HTTPException(404, f"No existe la prueba {prueba_id}")
    return al_dia(p)


PruebaDep = Annotated[dict, Depends(prueba_existente)]


def _docs(srv, prueba_id: str) -> tuple[dict | None, dict | None, dict | None]:
    """(revisión v2.3, revisión de calidad, modos de falla) de una prueba."""
    return (srv.repo.obtener_doc(COLECCION_REVISIONES, prueba_id), srv.repo.obtener_doc(cal.COLECCION_CALIDAD, prueba_id),
            srv.repo.obtener_doc(cal.COLECCION_MODOS, prueba_id))


def _elecciones(srv, usuario_id: str, prueba: dict) -> dict[str, dict]:
    try:
        return {m["id"]: resolver(srv, usuario_id, m) for m in prueba["modelos"]}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


def _crear_serie(srv, plantilla: dict, veces: int, *, serie: str | None, primera: int) -> list[dict]:
    """Crea `veces` pruebas iguales a `plantilla` (una serie) y devuelve los documentos."""
    creadas = []
    for k in range(veces):
        def fabricar(pid: str, k=k) -> dict:
            p = copy.deepcopy(plantilla)
            p.update(prueba_id=pid, uid=str(uuid.uuid4()), serie=serie or (creadas[0]["prueba_id"] if creadas else pid),
                     corrida=primera + k)
            p["codigo"] = codigo_de({**p, "codigo": None})
            return p
        creadas.append(srv.repo.crear_doc(COLECCION_PRUEBAS, PREFIJO, fabricar))
    return creadas


@router.post("/pruebas-modelos", status_code=201)
def crear(entrada: EntradaPrueba, srv: ServicioDep, usuario: UsuarioDep, request: Request) -> dict:
    """Crea la prueba (o la serie) y la corre en segundo plano, fuera de la cola de análisis. 422 si
    un proveedor necesita clave y la cuenta no la tiene, o si un término no está en el banco."""
    try:
        b = banco(entrada.banco)
    except KeyError as e:
        raise HTTPException(422, f"No existe el banco {entrada.banco}") from e
    todos = [t["id"] for t in b["terminos"]]
    items = list(dict.fromkeys(entrada.items or todos))
    if faltan := [i for i in items if i not in todos]:
        raise HTTPException(422, f"No están en el banco: {', '.join(faltan)}")
    items.sort(key=todos.index)
    modelos = list({(m.proveedor, m.modelo): m.model_dump() for m in entrada.modelos}.values())
    plantilla = nueva_prueba("P0", usuario_id=usuario.usuario_id, modelos=modelos, items=items, nota=entrada.nota,
                             version=request.app.version, settings=srv.deps.settings, banco_version=b["version"])
    elecciones = _elecciones(srv, usuario.usuario_id, plantilla)
    creadas = _crear_serie(srv, plantilla, entrada.repeticiones, serie=None, primera=1)
    respuesta = copy.deepcopy(creadas[0])  # el hilo de la prueba sigue escribiendo en el original
    EJECUTOR.lanzar_serie(srv, creadas, elecciones)
    return {**respuesta, "serie_creada": [p["prueba_id"] for p in creadas]}


@router.get("/pruebas-modelos")
def listar(srv: ServicioDep, usuario: UsuarioDep) -> list[dict]:
    pruebas = [al_dia(p) for p in srv.repo.listar_docs(COLECCION_PRUEBAS, usuario_id=usuario.usuario_id)
               if not p.get("borrada")]
    return [resumen_corto(p, *_docs(srv, p["prueba_id"])) for p in sorted(pruebas, key=lambda p: p["creado"], reverse=True)]


@router.get("/pruebas-modelos/series/{serie}")
def ver_serie(serie: str, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """La estabilidad entre las corridas de una serie: detección por corrida y su rango."""
    pruebas = [al_dia(p) for p in srv.repo.listar_docs(COLECCION_PRUEBAS, usuario_id=usuario.usuario_id)
               if not p.get("borrada") and (p.get("serie") or p["prueba_id"]) == serie]
    if not pruebas:
        raise HTTPException(404, f"No existe la serie {serie}")
    return estabilidad(pruebas)


@router.get("/pruebas-modelos/{prueba_id}")
def ver(p: PruebaDep, srv: ServicioDep) -> dict:
    """La prueba con cada respuesta, sus revisiones y el resumen por modelo."""
    legado, revision, modos = _docs(srv, p["prueba_id"])
    return {**p, "codigo": codigo_de(p), "revisiones": legado, "revision_calidad": revision, "modos_falla": modos,
            "resumen": resumen(p, legado, revision, modos)}


@router.delete("/pruebas-modelos/{prueba_id}", status_code=204)
def borrar(p: PruebaDep, srv: ServicioDep) -> Response:
    """Borra la prueba y sus revisiones, y deja una lápida con su id, uid, código y banco: el número
    no vuelve a usarse, así que una cita a «P03» siempre se refiere a la misma prueba."""
    if EJECUTOR.activa(p["prueba_id"]):
        raise HTTPException(409, "La prueba sigue corriendo: cancélala primero.")
    srv.repo.guardar_doc(COLECCION_PRUEBAS, p["prueba_id"], lapida(p))
    for coleccion in (COLECCION_REVISIONES, cal.COLECCION_CALIDAD, cal.COLECCION_MODOS):
        srv.repo.borrar_doc(coleccion, p["prueba_id"])
    return Response(status_code=204)


@router.post("/pruebas-modelos/{prueba_id}/cancelar")
def cancelar(p: PruebaDep) -> dict:
    """Se detiene al terminar el término en curso de cada proveedor; lo hecho se conserva."""
    return {"cancelando": EJECUTOR.cancelar(p["prueba_id"])}


@router.post("/pruebas-modelos/{prueba_id}/reanudar")
def reanudar(p: PruebaDep, srv: ServicioDep, usuario: UsuarioDep, errores: bool = False) -> dict:
    """Corre lo que falta de una prueba cancelada o interrumpida (o terminada, con `errores=true`
    para volver a intentar los términos que fallaron)."""
    if EJECUTOR.activa(p["prueba_id"]):
        raise HTTPException(409, "La prueba ya está corriendo.")
    if p["estado"] not in TERMINALES:
        raise HTTPException(409, f"No se puede reanudar una prueba {p['estado']}.")
    elecciones = _elecciones(srv, usuario.usuario_id, p)
    if errores:
        p["resultados"] = {m: {i: r for i, r in res.items() if r["ok"]} for m, res in p["resultados"].items()}
        p["avance"]["hechos"] = sum(len(res) for res in p["resultados"].values())
    p.update(estado="en_proceso", terminado=None, error=None)
    srv.repo.guardar_doc(COLECCION_PRUEBAS, p["prueba_id"], p)
    respuesta = copy.deepcopy(p)
    EJECUTOR.lanzar(srv, p, elecciones)
    return respuesta


@router.post("/pruebas-modelos/{prueba_id}/repetir", status_code=201)
def repetir(entrada: Repetir, p: PruebaDep, srv: ServicioDep, usuario: UsuarioDep, request: Request) -> dict:
    """Más corridas idénticas de la misma serie (mismos modelos, términos, banco y configuración),
    una tras otra, para medir la estabilidad."""
    serie = p.get("serie") or p["prueba_id"]
    hermanas = [d for d in srv.repo.listar_docs(COLECCION_PRUEBAS, usuario_id=usuario.usuario_id)
                if not d.get("borrada") and (d.get("serie") or d["prueba_id"]) == serie]
    plantilla = nueva_prueba("P0", usuario_id=p["usuario_id"], modelos=p["modelos"], items=p["items"], nota=p.get("nota"),
                             version=request.app.version, settings=srv.deps.settings, banco_version=banco_de(p)["version"])
    plantilla["configuracion"] = copy.deepcopy(p["configuracion"])  # la misma configuración, aunque cambie el .env
    elecciones = _elecciones(srv, usuario.usuario_id, plantilla)
    creadas = _crear_serie(srv, plantilla, entrada.veces, serie=serie,
                           primera=max(d.get("corrida", 1) for d in hermanas) + 1)
    respuestas = copy.deepcopy(creadas)
    EJECUTOR.lanzar_serie(srv, creadas, elecciones)
    return {"serie": serie, "creadas": [c["prueba_id"] for c in respuestas]}


# ---------------------------------------------------------------- revisión de calidad

def _revision_al_dia(srv, p: dict) -> dict | None:
    doc = srv.repo.obtener_doc(cal.COLECCION_CALIDAD, p["prueba_id"])
    if doc and cal.completar_orden(doc, p):
        srv.repo.guardar_doc(cal.COLECCION_CALIDAD, p["prueba_id"], doc)
    return doc


@router.get("/pruebas-modelos/{prueba_id}/revision-calidad")
def ver_revision(p: PruebaDep, srv: ServicioDep) -> dict | None:
    """La revisión en curso (o null), con el orden barajado y lo ya marcado: se retoma donde quedó."""
    with _CANDADO:
        return _revision_al_dia(srv, p)


@router.post("/pruebas-modelos/{prueba_id}/revision-calidad", status_code=201)
def empezar_revision(entrada: NuevaRevision, p: PruebaDep, srv: ServicioDep) -> dict:
    """Empieza la revisión: guarda revisor, si es a ciegas, la semilla y el orden barajado."""
    if p["estado"] == "en_proceso":
        raise HTTPException(409, "La prueba sigue corriendo: espera a que termine para revisar.")
    with _CANDADO:
        if srv.repo.obtener_doc(cal.COLECCION_CALIDAD, p["prueba_id"]):
            raise HTTPException(409, "Esta prueba ya tiene una revisión de calidad: retómala o rehazla.")
        doc = cal.nueva_revision(p, revisor=entrada.revisor, a_ciegas=entrada.a_ciegas)
        srv.repo.guardar_doc(cal.COLECCION_CALIDAD, p["prueba_id"], doc)
    return doc


@router.put("/pruebas-modelos/{prueba_id}/revision-calidad/marca")
def marcar(entrada: MarcaCalidad, p: PruebaDep, srv: ServicioDep) -> dict:
    """Guarda los tres criterios (y la cobertura, en los ambiguos) de una salida."""
    r = (p["resultados"].get(entrada.modelo) or {}).get(entrada.item)
    if entrada.item not in p["items"] or not r or not r.get("ok"):
        raise HTTPException(422, "Esa salida no existe o no es revisable (el modelo no respondió).")
    t = {x["id"]: x for x in banco_de(p)["terminos"]}[entrada.item]
    with _CANDADO:
        doc = _revision_al_dia(srv, p)
        if doc is None:
            raise HTTPException(409, "Primero empieza la revisión.")
        marca = cal.marcar(doc, modelo=entrada.modelo, item=entrada.item,
                           criterios={k: getattr(entrada, k) for k in CLAVES}, cobertura=entrada.cobertura,
                           n_lecturas=len(t["lecturas"]), ambiguo=es_ambiguo(t), nota=entrada.nota)
        srv.repo.guardar_doc(cal.COLECCION_CALIDAD, p["prueba_id"], doc)
    return {"marca": marca, "revisadas": sum(len(v) for v in doc["marcas"].values()), "total": len(doc["orden"])}


@router.delete("/pruebas-modelos/{prueba_id}/revision-calidad/marca", status_code=204)
def desmarcar(modelo: str, item: str, p: PruebaDep, srv: ServicioDep) -> Response:
    with _CANDADO:
        doc = _revision_al_dia(srv, p)
        if doc and doc["marcas"].get(modelo, {}).pop(item, None) is not None:
            srv.repo.guardar_doc(cal.COLECCION_CALIDAD, p["prueba_id"], doc)
    return Response(status_code=204)


@router.delete("/pruebas-modelos/{prueba_id}/revision-calidad", status_code=204)
def rehacer_revision(p: PruebaDep, srv: ServicioDep) -> Response:
    """Borra la revisión de calidad para empezarla de nuevo. La revisión ✓/✗ de la v2.3, si la
    hay, no se toca: es el registro del criterio viejo."""
    with _CANDADO:
        srv.repo.borrar_doc(cal.COLECCION_CALIDAD, p["prueba_id"])
    return Response(status_code=204)


def _terminos(p: dict) -> dict[str, dict]:
    return {t["id"]: t for t in banco_de(p)["terminos"]}


@router.get("/pruebas-modelos/{prueba_id}/revision-calidad/exportar")
def exportar_revision(p: PruebaDep, srv: ServicioDep, formato: str = "md", pendientes: bool = False) -> Response:
    """El archivo para revisar fuera del sistema, a ciegas: rúbrica, salidas con id opaco
    (S015 = salida 15 del orden de la revisión), falsos negativos y la plantilla de respuestas.
    No crea la revisión: si no hay, el orden sale de una semilla nueva que viaja en el archivo."""
    if formato not in ("md", "json"):
        raise HTTPException(422, "formato debe ser md o json")
    if p["estado"] == "en_proceso":
        raise HTTPException(409, "La prueba sigue corriendo: espera a que termine para exportar la revisión.")
    with _CANDADO:
        doc = _revision_al_dia(srv, p)
    contenido = intercambio.exportar(p, doc, srv.repo.obtener_doc(cal.COLECCION_MODOS, p["prueba_id"]), _terminos(p),
                                     es_ambiguo, codigo=codigo_de(p), solo_pendientes=pendientes)
    nombre = f"revision-{codigo_de(p)}{'-pendientes' if pendientes else ''}.{formato}"
    cuerpo = (intercambio.markdown(contenido) if formato == "md"
              else json.dumps(contenido, ensure_ascii=False, indent=1))
    return Response(cuerpo, media_type="text/markdown; charset=utf-8" if formato == "md" else "application/json",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/pruebas-modelos/{prueba_id}/revision-calidad/importar")
def importar_revision(entrada: Importacion, p: PruebaDep, srv: ServicioDep) -> dict:
    """Aplica un archivo contestado. Cada marca guarda su origen (persona o IA, y quién); por
    omisión no pisa lo ya marcado y mide el acuerdo con eso."""
    if p["estado"] == "en_proceso":
        raise HTTPException(409, "La prueba sigue corriendo: espera a que termine para importar.")
    try:
        datos = intercambio.leer(entrada.contenido)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    with _CANDADO:
        doc = _revision_al_dia(srv, p)
        modos = srv.repo.obtener_doc(cal.COLECCION_MODOS, p["prueba_id"])
        try:
            doc, modos, informe = intercambio.importar(p, doc, modos, _terminos(p), es_ambiguo, datos,
                                                       codigo=codigo_de(p), tipo=entrada.tipo, quien=entrada.quien,
                                                       sobrescribir=entrada.sobrescribir)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        if doc is not None:
            srv.repo.guardar_doc(cal.COLECCION_CALIDAD, p["prueba_id"], doc)
        if modos is not None:
            srv.repo.guardar_doc(cal.COLECCION_MODOS, p["prueba_id"], modos)
    return informe | {"revisadas": sum(len(v) for v in (doc or {}).get("marcas", {}).values()),
                      "total": len((doc or {}).get("orden", []))}


@router.put("/pruebas-modelos/{prueba_id}/modos")
def asignar_modo(entrada: Modo, p: PruebaDep, srv: ServicioDep) -> dict:
    """El modo de falla de un falso negativo (un ambiguo que el modelo no detectó)."""
    r = (p["resultados"].get(entrada.modelo) or {}).get(entrada.item)
    t = {x["id"]: x for x in banco_de(p)["terminos"]}.get(entrada.item)
    if not r or not t or not es_ambiguo(t) or (r.get("ok") and r.get("ambiguo")):
        raise HTTPException(422, "Solo se clasifican los falsos negativos: ambiguos que el modelo no detectó.")
    with _CANDADO:
        doc = srv.repo.obtener_doc(cal.COLECCION_MODOS, p["prueba_id"]) or {
            "prueba_id": p["prueba_id"], "usuario_id": p["usuario_id"], "modos": {}}
        try:
            cal.asignar_modo(doc, modelo=entrada.modelo, item=entrada.item, modo=entrada.modo, nota=entrada.nota)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        srv.repo.guardar_doc(cal.COLECCION_MODOS, p["prueba_id"], doc)
    return doc


@router.get("/pruebas-modelos/{prueba_id}/overleaf.zip")
def exportar(p: PruebaDep, srv: ServicioDep, usuario: UsuarioDep) -> Response:
    legado, revision, modos = _docs(srv, p["prueba_id"])
    serie = p.get("serie") or p["prueba_id"]
    hermanas = [d for d in srv.repo.listar_docs(COLECCION_PRUEBAS, usuario_id=usuario.usuario_id)
                if not d.get("borrada") and (d.get("serie") or d["prueba_id"]) == serie]
    estab = estabilidad([al_dia(d) for d in hermanas]) if len(hermanas) > 1 else None
    nombre = f"dudamel-modelos-{codigo_de(p)}.zip"
    return Response(paquete_overleaf(p, resumen(p, legado, revision, modos), legado, revision, estab),
                    media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
