"""Proyectos: agrupan requisitos de un mismo dominio y separan su LEL (ADR 0008)."""
from __future__ import annotations

from app.models import PROYECTO_GENERAL, Proyecto

from .repositorio import Repositorio

COLECCION = "proyectos"


class Proyectos:
    def __init__(self, repo: Repositorio):
        self.repo = repo

    def asegurar_general(self) -> Proyecto:
        """`P00 General` existe siempre: ahí quedan los requisitos sin proyecto
        (incluidos los procesados antes de que hubiera proyectos)."""
        actual = self.obtener(PROYECTO_GENERAL)
        if actual:
            return actual
        p = Proyecto(proyecto_id=PROYECTO_GENERAL, nombre="General",
                     descripcion="Requisitos sin proyecto asignado.")
        self.repo.guardar_doc(COLECCION, PROYECTO_GENERAL, p.model_dump(mode="json"))
        return p

    def crear(self, nombre: str, descripcion: str | None = None, tipo: str = "normal",
              contexto: str | None = None) -> Proyecto:
        datos = self.repo.crear_doc(COLECCION, "P", lambda pid: Proyecto(
            proyecto_id=pid, nombre=nombre, descripcion=descripcion, tipo=tipo,
            contexto=contexto).model_dump(mode="json"))
        return Proyecto.model_validate(datos)

    def obtener(self, proyecto_id: str) -> Proyecto | None:
        d = self.repo.obtener_doc(COLECCION, proyecto_id)
        return Proyecto.model_validate(d) if d else None

    def listar(self) -> list[Proyecto]:
        return [Proyecto.model_validate(d) for d in self.repo.listar_docs(COLECCION)]

    def actualizar(self, proyecto_id: str, **cambios) -> Proyecto:
        p = self.obtener(proyecto_id)
        if p is None:
            raise KeyError(proyecto_id)
        nuevo = p.model_copy(update={k: v for k, v in cambios.items() if v is not None})
        nuevo = Proyecto.model_validate(nuevo.model_dump())
        self.repo.guardar_doc(COLECCION, proyecto_id, nuevo.model_dump(mode="json"))
        return nuevo
