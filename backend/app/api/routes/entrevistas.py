"""Entrevistas de un proyecto (ADR 0024): la entrada de la versión 2.

Se pega el texto o se sube un PDF/.txt; la vista previa dice cómo se leyó (turnos y
hablantes) sin guardar nada; al confirmar, la entrevista entra a la cola y los agentes
proponen su LEL. La escena en vivo la sigue por SSE, como a un requisito en la versión 1.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from pathlib import PurePosixPath
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ConfigDict, Field

from app.documentos import DemasiadoGrande, ErrorDocumento, TipoNoSoportado, leer
from app.documentos.extraccion import nombre_de_archivo
from app.entrevistas import almacen as ea
from app.entrevistas.turnos import como_texto, leer_paginas, leer_texto
from app.orchestration import ConflictoDeEstado

from ..dependencias import UsuarioDep, apagando, es_suyo, obtener_servicio
from .proyectos import ProyectoDep, ServicioDep

router = APIRouter(tags=["entrevistas"])

_CODIGOS = {DemasiadoGrande: 413, TipoNoSoportado: 415}
_PESADOS = ("turnos",)


class EntradaTextoEntrevista(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=1)


class OrigenEntrevista(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["texto", "pdf", "txt"] = "texto"
    archivo: str | None = Field(None, max_length=200)
    paginas: int | None = Field(None, ge=1)


class EntradaEntrevista(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    titulo: str = Field(min_length=1, max_length=160)
    texto: str = Field(min_length=1)
    origen: OrigenEntrevista | None = None


class CambiosEntrevista(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    titulo: str = Field(min_length=1, max_length=160)


def _max(srv) -> int:
    return srv.deps.settings.entrevista_max_caracteres


def _leer(texto: str, srv):
    if len(texto) > _max(srv):
        raise HTTPException(413, f"La entrevista pasa de {_max(srv):,} caracteres (ENTREVISTA_MAX_CARACTERES).")
    leida = leer_texto(texto)
    if not leida.turnos:
        raise HTTPException(422, "No hay texto que leer en la entrevista.")
    return leida


def resumen(doc: dict, srv) -> dict:
    """La entrevista sin sus turnos (para listas), con cuántos son y si espera en la cola."""
    return {**{k: v for k, v in doc.items() if k not in _PESADOS}, "n_turnos": len(doc.get("turnos", [])),
            "ocupada": srv.entrevistas.ocupada(doc["entrevista_id"])}


def entrevista_existente(entrevista_id: str, request: Request, usuario: UsuarioDep) -> dict:
    srv = obtener_servicio(request)
    doc = srv.entrevistas.almacen.obtener(entrevista_id)
    if doc is None or not es_suyo(srv, usuario, doc["proyecto_id"]):
        raise HTTPException(404, f"No existe la entrevista {entrevista_id}")
    return doc


EntrevistaDep = Annotated[dict, Depends(entrevista_existente)]


@router.post("/proyectos/{proyecto_id}/entrevistas/vista-previa")
def vista_previa(entrada: EntradaTextoEntrevista, p: ProyectoDep, srv: ServicioDep) -> dict:
    """Cómo se lee el texto: {turnos: [{n, hablante, texto, pagina}], modo, hablantes, advertencias,
    caracteres}. No guarda nada."""
    return _leer(entrada.texto, srv).a_dict()


@router.post("/proyectos/{proyecto_id}/entrevistas/archivo")
def desde_archivo(p: ProyectoDep, srv: ServicioDep, archivo: Annotated[UploadFile, File()]) -> dict:
    """Lee un PDF con texto o un .txt: {titulo, texto, origen, vista}. `texto` son los turnos en texto
    («Hablante: …»), para que la persona lo revise o corrija antes de enviarlo. No guarda nada."""
    maximo = int(srv.deps.settings.documento_max_mb * 1024 * 1024)
    contenido = archivo.file.read(maximo + 1)
    try:
        extraido = leer(archivo.filename or "entrevista", contenido, maximo, archivo.content_type)
    except ErrorDocumento as e:
        raise HTTPException(_CODIGOS.get(type(e), 422), str(e)) from e
    leida = leer_paginas(extraido.paginas, extraido.con_paginas, maquetado=extraido.tipo == "pdf")
    leida.advertencias = [*extraido.advertencias, *leida.advertencias]
    if not leida.turnos:
        raise HTTPException(422, "El archivo no tiene texto que se pueda leer.")
    nombre = nombre_de_archivo(archivo.filename)
    return {"titulo": PurePosixPath(nombre).stem[:160] or "Entrevista", "texto": como_texto(leida.a_dict()["turnos"]),
            "origen": {"tipo": extraido.tipo, "archivo": nombre, "paginas": len(extraido.paginas)},
            "vista": leida.a_dict()}


@router.post("/proyectos/{proyecto_id}/entrevistas", status_code=202)
def crear(entrada: EntradaEntrevista, p: ProyectoDep, srv: ServicioDep) -> dict:
    """Guarda la entrevista y la encola: los agentes proponen su LEL. Se sigue en
    GET /entrevistas/{id}/eventos."""
    if p.tipo == "evaluacion":
        raise HTTPException(409, "Un proyecto de evaluación no procesa entrevistas.")
    leida = _leer(entrada.texto, srv)
    origen = (entrada.origen or OrigenEntrevista()).model_dump()
    return resumen(srv.entrevistas.solicitar(p.proyecto_id, entrada.titulo, leida, origen), srv)


@router.get("/proyectos/{proyecto_id}/entrevistas")
def listar(p: ProyectoDep, srv: ServicioDep) -> list[dict]:
    return [resumen(d, srv) for d in srv.entrevistas.almacen.listar(p.proyecto_id)]


@router.get("/entrevistas/{entrevista_id}")
def obtener(e: EntrevistaDep, srv: ServicioDep) -> dict:
    return {**e, "n_turnos": len(e["turnos"]), "ocupada": srv.entrevistas.ocupada(e["entrevista_id"])}


@router.patch("/entrevistas/{entrevista_id}")
def renombrar(cambios: CambiosEntrevista, e: EntrevistaDep, srv: ServicioDep) -> dict:
    return resumen(srv.entrevistas.almacen.actualizar(e["entrevista_id"], titulo=cambios.titulo), srv)


@router.get("/entrevistas/{entrevista_id}/bitacora")
def bitacora(e: EntrevistaDep, srv: ServicioDep) -> dict:
    """Todos los mensajes entre agentes de la última corrida, con sus transiciones."""
    return srv.entrevistas.almacen.bitacora(e["entrevista_id"])


@router.get("/entrevistas/{entrevista_id}/eventos", response_class=EventSourceResponse)
async def eventos(request: Request, srv: ServicioDep, e: EntrevistaDep, desde: int = 0,
                  last_event_id: Annotated[str | None, Header()] = None) -> AsyncIterable[ServerSentEvent]:
    """SSE como el de un requisito: `mensaje` (id = secuencia), `estado` y `fin` al terminar
    (lista, error o cancelada)."""
    enviados = desde
    if last_event_id and last_event_id.isdigit():
        enviados = max(enviados, int(last_event_id))
    eid, ultimo_estado = e["entrevista_id"], None
    almacen = srv.entrevistas.almacen
    while True:
        doc = await run_in_threadpool(almacen.obtener, eid)
        if doc is None:
            return
        b = await run_in_threadpool(almacen.bitacora, eid)
        for m in b["mensajes"]:
            if m["secuencia"] > enviados:
                yield ServerSentEvent(data=m, event="mensaje", id=str(m["secuencia"]))
                enviados = m["secuencia"]
        if doc["estado"] != ultimo_estado:
            ultimo_estado = doc["estado"]
            yield ServerSentEvent(data={"estado": doc["estado"], "secuencia": enviados}, event="estado")
        if doc["estado"] in ea.TERMINALES and not srv.entrevistas.ocupada(eid):
            yield ServerSentEvent(data={"estado": doc["estado"], "resumen": doc.get("resumen"),
                                        "error": doc.get("error")}, event="fin")
            return
        if await request.is_disconnected() or apagando(request):
            return
        await asyncio.sleep(srv.deps.settings.sse_intervalo_s)


@router.post("/entrevistas/{entrevista_id}/cancelar")
def cancelar(e: EntrevistaDep, srv: ServicioDep) -> dict:
    return srv.entrevistas.cancelar(e["entrevista_id"])


@router.post("/entrevistas/{entrevista_id}/reprocesar", status_code=202)
def reprocesar(e: EntrevistaDep, srv: ServicioDep) -> dict:
    try:
        return resumen(srv.entrevistas.reprocesar(e["entrevista_id"]), srv)
    except ConflictoDeEstado as x:
        raise HTTPException(409, str(x)) from x


@router.delete("/entrevistas/{entrevista_id}")
def borrar(e: EntrevistaDep, srv: ServicioDep) -> dict:
    """Borra la entrevista. Sus citas salen del LEL; lo que solo ella proponía y nadie validó, también."""
    try:
        return srv.entrevistas.borrar(e["entrevista_id"])
    except ConflictoDeEstado as x:
        raise HTTPException(409, str(x)) from x
