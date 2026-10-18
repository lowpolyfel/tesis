"""Prueba de modelos con el banco de términos ambiguos (ADR 0027).

- `GET /bancos/ambiguedad?version=`: un banco (el más nuevo si no se pide versión), con su cita,
  dominio y lecturas esperadas por término; `versiones` dice cuáles hay.
- `GET /pruebas-modelos/modelos`: los modelos que esta cuenta puede probar (proveedores con
  clave guardada, y Ollama).
- `POST /pruebas-modelos`: crea una prueba y la corre en segundo plano.
- `GET /pruebas-modelos`, `GET|DELETE /pruebas-modelos/{id}`: listar, ver (con resumen y
  revisiones) y borrar.
- `POST /pruebas-modelos/{id}/cancelar` y `/reanudar`.
- `PUT /pruebas-modelos/{id}/revision`: la marca ✓/✗ de la persona en un término de un modelo;
  `DELETE` la borra entera, para rehacerla (por ejemplo, a ciegas).
- `GET /pruebas-modelos/{id}/overleaf.zip`: el paquete para LaTeX.

Cada prueba es de la cuenta que la creó.
"""
from __future__ import annotations

import copy
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.calibracion.latex_modelos import paquete_overleaf
from app.calibracion.pruebas_modelos import (
    COLECCION_PRUEBAS,
    COLECCION_REVISIONES,
    EJECUTOR,
    PREFIJO,
    TERMINALES,
    ahora,
    al_dia,
    banco,
    nueva_prueba,
    resolver,
    resumen,
    resumen_corto,
)
from app.llm.proveedores import CATALOGO, FalloProveedor, listar_modelos

from ..dependencias import UsuarioDep
from .calibracion import ServicioDep

router = APIRouter(tags=["calibracion"])
_REVISIONES = threading.Lock()  # las marcas llegan de una en una y se guardan sobre el mismo documento


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


class Marca(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    modelo: str = Field(pattern=r"^M\d+$")
    item: str = Field(pattern=r"^B\d+$")
    bueno: bool | None  # null quita la marca
    nota: str | None = Field(None, max_length=500)
    revisor: str = Field(min_length=1, max_length=120)
    a_ciegas: bool = True


@router.get("/bancos/ambiguedad")
def ver_banco(version: str | None = None) -> dict:
    try:
        return banco(version)
    except KeyError as e:
        raise HTTPException(404, f"No existe el banco {version}") from e


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
    if p is None or p.get("usuario_id") != usuario.usuario_id:
        raise HTTPException(404, f"No existe la prueba {prueba_id}")
    return al_dia(p)


PruebaDep = Annotated[dict, Depends(prueba_existente)]


def _revisiones(srv, prueba_id: str) -> dict | None:
    return srv.repo.obtener_doc(COLECCION_REVISIONES, prueba_id)


def _elecciones(srv, usuario_id: str, prueba: dict) -> dict[str, dict]:
    try:
        return {m["id"]: resolver(srv, usuario_id, m) for m in prueba["modelos"]}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/pruebas-modelos", status_code=201)
def crear(entrada: EntradaPrueba, srv: ServicioDep, usuario: UsuarioDep, request: Request) -> dict:
    """Crea la prueba y la corre en segundo plano (fuera de la cola de análisis). 422 si un
    proveedor necesita clave y la cuenta no la tiene, o si un término no está en el banco."""
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
    borrador = nueva_prueba("P0", usuario_id=usuario.usuario_id, modelos=modelos, items=items, nota=entrada.nota,
                            version=request.app.version, settings=srv.deps.settings, banco_version=b["version"])
    elecciones = _elecciones(srv, usuario.usuario_id, borrador)
    prueba = srv.repo.crear_doc(COLECCION_PRUEBAS, PREFIJO, lambda pid: {**borrador, "prueba_id": pid})
    respuesta = copy.deepcopy(prueba)  # el hilo de la prueba sigue escribiendo en `prueba`
    EJECUTOR.lanzar(srv, prueba, elecciones)
    return respuesta


@router.get("/pruebas-modelos")
def listar(srv: ServicioDep, usuario: UsuarioDep) -> list[dict]:
    pruebas = [al_dia(p) for p in srv.repo.listar_docs(COLECCION_PRUEBAS, usuario_id=usuario.usuario_id)]
    return [resumen_corto(p, _revisiones(srv, p["prueba_id"])) for p in sorted(pruebas, key=lambda p: p["creado"], reverse=True)]


@router.get("/pruebas-modelos/{prueba_id}")
def ver(p: PruebaDep, srv: ServicioDep) -> dict:
    """La prueba con cada respuesta, sus revisiones y el resumen por modelo."""
    rev = _revisiones(srv, p["prueba_id"])
    return {**p, "revisiones": rev, "resumen": resumen(p, rev)}


@router.delete("/pruebas-modelos/{prueba_id}", status_code=204)
def borrar(p: PruebaDep, srv: ServicioDep) -> Response:
    if EJECUTOR.activa(p["prueba_id"]):
        raise HTTPException(409, "La prueba sigue corriendo: cancélala primero.")
    srv.repo.borrar_doc(COLECCION_PRUEBAS, p["prueba_id"])
    srv.repo.borrar_doc(COLECCION_REVISIONES, p["prueba_id"])
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


@router.put("/pruebas-modelos/{prueba_id}/revision")
def revisar(marca: Marca, p: PruebaDep, srv: ServicioDep) -> dict:
    """Guarda (o quita, con `bueno: null`) la marca de un término de un modelo."""
    if marca.modelo not in {m["id"] for m in p["modelos"]} or marca.item not in p["items"]:
        raise HTTPException(422, "Ese modelo o ese término no son de esta prueba.")
    with _REVISIONES:
        doc = _revisiones(srv, p["prueba_id"]) or {"prueba_id": p["prueba_id"], "usuario_id": p["usuario_id"], "marcas": {}}
        marcas = doc["marcas"].setdefault(marca.modelo, {})
        if marca.bueno is None:
            marcas.pop(marca.item, None)
        else:
            marcas[marca.item] = {"bueno": marca.bueno, "nota": marca.nota or None, "fecha": ahora()}
        # una sola marca vista cuenta: la revisión entera deja de ser a ciegas
        doc.update(revisor=marca.revisor, a_ciegas=doc.get("a_ciegas", True) and marca.a_ciegas, actualizada=ahora())
        srv.repo.guardar_doc(COLECCION_REVISIONES, p["prueba_id"], doc)
    return {"revisiones": doc, "resumen": resumen(p, doc)}


@router.delete("/pruebas-modelos/{prueba_id}/revision", status_code=204)
def rehacer_revision(p: PruebaDep, srv: ServicioDep) -> Response:
    """Borra todas las marcas de la prueba para revisarla de nuevo (las respuestas se conservan)."""
    with _REVISIONES:
        srv.repo.borrar_doc(COLECCION_REVISIONES, p["prueba_id"])
    return Response(status_code=204)


@router.get("/pruebas-modelos/{prueba_id}/overleaf.zip")
def exportar(p: PruebaDep, srv: ServicioDep) -> Response:
    rev = _revisiones(srv, p["prueba_id"])
    nombre = f"dudamel-modelos-{p['prueba_id']}.zip"
    return Response(paquete_overleaf(p, resumen(p, rev), rev), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
