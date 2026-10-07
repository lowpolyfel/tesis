"""Contratos del módulo de documentos (ADR 0009)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Origen, ahora

# titulo: encabezado corto sin verbo; sin_verbo_obligacion: oración sin verbo de
# obligación o capacidad; sin_texto: solo marca, números o símbolos.
MotivoDescarte = Literal["titulo", "sin_verbo_obligacion", "sin_texto"]


class RequisitoPropuesto(BaseModel):
    """Candidato a requisito; el humano lo confirma o lo edita antes de procesarlo."""

    model_config = ConfigDict(extra="forbid")

    indice: int = Field(ge=1)  # 1..n en orden de aparición
    texto: str = Field(min_length=1)  # la oración, sin la marca
    pagina: int | None = Field(None, ge=1)  # donde empieza; None si el texto no tiene páginas
    marca: str | None = None  # numeración original: RF-01, 3.2.1, 1, •…
    texto_original: str  # el párrafo como venía (renglones y marca incluidos)
    advertencias: list[str] = []


class FragmentoDescartado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str
    pagina: int | None = Field(None, ge=1)
    marca: str | None = None
    motivo: MotivoDescarte


class Separacion(BaseModel):
    """Resultado de separar un texto: lo propuesto, lo que se dejó fuera y por qué."""

    model_config = ConfigDict(extra="forbid")

    requisitos_propuestos: list[RequisitoPropuesto] = []
    fragmentos_descartados: list[FragmentoDescartado] = []  # los primeros; el total va aparte
    total_descartados: int = Field(0, ge=0)
    advertencias: list[str] = []  # lo que la limpieza quitó o no pudo leer


class ResumenDocumento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documento_id: str
    proyecto_id: str
    archivo: str
    tipo: Literal["pdf", "txt"]
    paginas: int = Field(ge=1)
    caracteres: int = Field(ge=0)
    creado: datetime
    total_requisitos: int = Field(ge=0)
    total_descartados: int = Field(ge=0)


class Documento(BaseModel):
    """Documento cargado a un proyecto. `texto_por_pagina` es el texto tal como se
    extrajo, para rastrear cada requisito hasta su página; queda en None si excede
    el límite de almacenamiento (ver `almacen.MAX_CARACTERES_GUARDADOS`)."""

    model_config = ConfigDict(extra="forbid")

    documento_id: str
    proyecto_id: str
    archivo: str
    tipo: Literal["pdf", "txt"]
    paginas: int = Field(ge=1)
    caracteres: int = Field(ge=0)
    creado: datetime = Field(default_factory=ahora)
    requisitos_propuestos: list[RequisitoPropuesto] = []
    fragmentos_descartados: list[FragmentoDescartado] = []
    total_descartados: int = Field(0, ge=0)
    advertencias: list[str] = []
    texto_por_pagina: list[str] | None = None

    def resumen(self) -> ResumenDocumento:
        return ResumenDocumento(
            documento_id=self.documento_id, proyecto_id=self.proyecto_id, archivo=self.archivo, tipo=self.tipo,
            paginas=self.paginas, caracteres=self.caracteres, creado=self.creado,
            total_requisitos=len(self.requisitos_propuestos), total_descartados=self.total_descartados)

    def origen(self, requisito: RequisitoPropuesto) -> Origen:
        """El `origen` con el que se registra el requisito confirmado (POST /proyectos/{id}/requisitos)."""
        return Origen(documento_id=self.documento_id, archivo=self.archivo, pagina=requisito.pagina,
                      indice=requisito.indice, marca=requisito.marca, texto_original=requisito.texto_original)
