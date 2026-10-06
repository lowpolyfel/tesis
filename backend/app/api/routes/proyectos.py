"""Proyectos: crear, listar y cargar varios requisitos a la cola."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.models import Origen, Proyecto
from app.orchestration import Servicio

from ..dependencias import obtener_servicio

router = APIRouter(tags=["proyectos"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


class EntradaProyecto(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = Field(None, max_length=2000)


class CambiosProyecto(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nombre: str | None = Field(None, min_length=1, max_length=120)
    descripcion: str | None = Field(None, max_length=2000)


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
    return srv.proyectos.crear(entrada.nombre, entrada.descripcion)


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
    """Registra los requisitos confirmados por el humano y los encola en orden."""
    ids = [srv.solicitar(r.texto, p.proyecto_id, r.origen) for r in entrada.requisitos]
    return {"proyecto_id": p.proyecto_id, "req_ids": ids}
