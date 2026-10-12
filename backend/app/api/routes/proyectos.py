"""Proyectos de la cuenta con sesión: crear, listar, editar, borrar y cargar varios
requisitos a la cola. Un proyecto de otra cuenta responde 404."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.documentos.almacen import COLECCION as COLECCION_DOCUMENTOS
from app.models import Origen, Proyecto
from app.orchestration import ConflictoDeEstado, Servicio

from ..dependencias import UsuarioDep, obtener_servicio

router = APIRouter(tags=["proyectos"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


CONTEXTO_MAX = 4000  # caracteres: cabe en el prompt de cada agente junto con el requisito y el LEL


class EntradaProyecto(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = Field(None, max_length=2000)
    contexto: str | None = Field(None, max_length=CONTEXTO_MAX)


class CambiosProyecto(BaseModel):
    """Solo cambia lo que viene; `contexto: ""` lo borra."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nombre: str | None = Field(None, min_length=1, max_length=120)
    descripcion: str | None = Field(None, max_length=2000)
    contexto: str | None = Field(None, max_length=CONTEXTO_MAX)


class TriajeEntrada(BaseModel):
    """El veredicto del triaje que vio la persona (ADR 0022). `ambiguo` o `incompleto` obligan a
    revisar el requisito antes de formalizarlo; `forzado`: se mandó incompleto a propósito."""
    model_config = ConfigDict(extra="forbid")
    veredicto: Literal["claro", "ambiguo", "incompleto"] | None = None
    motivo: str | None = Field(None, max_length=400)
    faltantes: list[str] = Field(default=[], max_length=6)
    preguntas: list[str] = Field(default=[], max_length=4)
    terminos_ambiguos: list[str] = Field(default=[], max_length=8)
    precisado: bool = False  # la persona lo reescribió tras el triaje
    forzado: bool = False


class RequisitoNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    texto: str = Field(min_length=1, max_length=2000)
    origen: Origen | None = None
    triaje: TriajeEntrada | None = None


class EntradaRequisitos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requisitos: list[RequisitoNuevo] = Field(min_length=1, max_length=200)


def proyecto_existente(proyecto_id: str, srv: ServicioDep, usuario: UsuarioDep) -> Proyecto:
    p = srv.proyectos.obtener(proyecto_id)
    if p is None or p.propietario != usuario.usuario_id:
        raise HTTPException(404, f"No existe el proyecto {proyecto_id}")
    return p


ProyectoDep = Annotated[Proyecto, Depends(proyecto_existente)]


@router.get("/proyectos", response_model=list[Proyecto])
def listar(srv: ServicioDep, usuario: UsuarioDep) -> list[Proyecto]:
    return srv.proyectos.listar(usuario.usuario_id)


@router.post("/proyectos", status_code=201, response_model=Proyecto)
def crear(entrada: EntradaProyecto, srv: ServicioDep, usuario: UsuarioDep) -> Proyecto:
    return srv.proyectos.crear(entrada.nombre, entrada.descripcion, contexto=entrada.contexto or None,
                               propietario=usuario.usuario_id)


@router.get("/proyectos/{proyecto_id}", response_model=Proyecto)
def obtener(p: ProyectoDep) -> Proyecto:
    return p


@router.patch("/proyectos/{proyecto_id}", response_model=Proyecto)
def actualizar(p: ProyectoDep, cambios: CambiosProyecto, srv: ServicioDep) -> Proyecto:
    return srv.proyectos.actualizar(p.proyecto_id, **cambios.model_dump())


@router.delete("/proyectos/{proyecto_id}", status_code=204)
def borrar(p: ProyectoDep, srv: ServicioDep) -> None:
    """Borra el proyecto con sus requisitos, su léxico, documentos, comparaciones y
    evaluaciones. 409 si algo del proyecto se está analizando o espera turno."""
    try:
        srv.borrar_proyecto(p.proyecto_id)
    except ConflictoDeEstado as e:
        raise HTTPException(409, str(e)) from e


@router.get("/proyectos/{proyecto_id}/requisitos")
def requisitos(p: ProyectoDep, srv: ServicioDep) -> list[dict]:
    return srv.trazas(p.proyecto_id)


@router.post("/proyectos/{proyecto_id}/requisitos", status_code=202)
def cargar(p: ProyectoDep, entrada: EntradaRequisitos, srv: ServicioDep) -> dict:
    """Registra los requisitos confirmados por el humano en un ciclo nuevo y los encola en orden.
    422 si un origen apunta a un documento o a un requisito reprocesado de otro proyecto."""
    for i, r in enumerate(entrada.requisitos, 1):
        o = r.origen
        doc = srv.repo.obtener_doc(COLECCION_DOCUMENTOS, o.documento_id) if o and o.documento_id else None
        if doc and doc.get("proyecto_id") != p.proyecto_id:
            raise HTTPException(422, f"requisito {i}: el documento {o.documento_id} es del proyecto "
                                     f"{doc.get('proyecto_id')}, no de {p.proyecto_id}")
        previo = srv.repo.obtener_traza(o.reproceso_de) if o and o.reproceso_de else None
        if previo and previo.proyecto_id != p.proyecto_id:
            raise HTTPException(422, f"requisito {i}: {o.reproceso_de} es del proyecto {previo.proyecto_id}, "
                                     f"no de {p.proyecto_id}")
    ciclo, ids = srv.solicitar_lote([(r.texto, r.origen, r.triaje.model_dump() if r.triaje else None)
                                     for r in entrada.requisitos], p.proyecto_id)
    return {"proyecto_id": p.proyecto_id, "ciclo": ciclo, "req_ids": ids}


class EntradaReanalizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    req_ids: list[str] = Field(min_length=1, max_length=200)


@router.post("/proyectos/{proyecto_id}/reanalizar", status_code=202)
def reanalizar(p: ProyectoDep, entrada: EntradaReanalizar, srv: ServicioDep) -> dict:
    """Vuelve a analizar requisitos que terminaron en error (p. ej. la clave no daba acceso al
    modelo). Crea una versión nueva de cada uno (`origen.reproceso_de`) en un ciclo nuevo.
    422 si alguno no es del proyecto, no está en error o ya se volvió a analizar."""
    try:
        ciclo, ids = srv.reanalizar(p.proyecto_id, entrada.req_ids)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"proyecto_id": p.proyecto_id, "ciclo": ciclo, "req_ids": ids}


class EntradaCancelar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    req_ids: list[str] = Field(min_length=1, max_length=500)


@router.post("/proyectos/{proyecto_id}/cancelar")
def cancelar(p: ProyectoDep, entrada: EntradaCancelar, srv: ServicioDep) -> dict:
    """Cancela el análisis de esos requisitos y los descarta por completo (traza, LEL,
    formalización, checkpoint). {descartados, deteniendo}: los de `deteniendo` se estaban
    analizando y se borran al terminar el paso en curso. 422 si alguno no es del proyecto."""
    try:
        return srv.cancelar(p.proyecto_id, entrada.req_ids)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
