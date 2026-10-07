"""Proyectos: crear, listar y cargar varios requisitos a la cola."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.documentos.almacen import COLECCION as COLECCION_DOCUMENTOS
from app.models import Origen, Proyecto
from app.orchestration import Servicio

from ..dependencias import obtener_servicio

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


class RequisitoNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    texto: str = Field(min_length=1, max_length=2000)
    origen: Origen | None = None


class EntradaRequisitos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requisitos: list[RequisitoNuevo] = Field(min_length=1, max_length=200)


def proyecto_existente(proyecto_id: str, srv: ServicioDep) -> Proyecto:
    p = srv.proyectos.obtener(proyecto_id)
    if p is None:
        raise HTTPException(404, f"No existe el proyecto {proyecto_id}")
    return p


ProyectoDep = Annotated[Proyecto, Depends(proyecto_existente)]


@router.get("/proyectos", response_model=list[Proyecto])
def listar(srv: ServicioDep) -> list[Proyecto]:
    return srv.proyectos.listar()


@router.post("/proyectos", status_code=201, response_model=Proyecto)
def crear(entrada: EntradaProyecto, srv: ServicioDep) -> Proyecto:
    return srv.proyectos.crear(entrada.nombre, entrada.descripcion, contexto=entrada.contexto or None)


@router.get("/proyectos/{proyecto_id}", response_model=Proyecto)
def obtener(p: ProyectoDep) -> Proyecto:
    return p


@router.patch("/proyectos/{proyecto_id}", response_model=Proyecto)
def actualizar(p: ProyectoDep, cambios: CambiosProyecto, srv: ServicioDep) -> Proyecto:
    return srv.proyectos.actualizar(p.proyecto_id, **cambios.model_dump())


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
    ciclo, ids = srv.solicitar_lote([(r.texto, r.origen) for r in entrada.requisitos], p.proyecto_id)
    return {"proyecto_id": p.proyecto_id, "ciclo": ciclo, "req_ids": ids}
