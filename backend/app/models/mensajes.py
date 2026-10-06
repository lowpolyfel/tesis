"""Sobre común de los mensajes entre nodos y traza de un requisito (ADR 0001).

Cada mensaje se agrega a la traza: es el NFR de trazabilidad.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .comunes import Estado, Nodo, TipoMensaje
from .contratos import Interpretacion


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Mensaje(BaseModel):
    model_config = ConfigDict(extra="forbid")

    req_id: str
    secuencia: int = Field(ge=1)
    ronda: int = Field(ge=0)
    emisor: Nodo
    receptor: Nodo
    tipo: TipoMensaje
    payload: dict[str, Any] = {}
    modelo: str | None = None
    prompt_version: str | None = None
    timestamp: datetime = Field(default_factory=ahora)


class Transicion(BaseModel):
    """Entrada a un estado de la máquina. `secuencia` es el último mensaje emitido
    antes de la transición (0 si aún no hay mensajes)."""

    model_config = ConfigDict(extra="forbid")

    estado: Estado
    secuencia: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=ahora)


PROYECTO_GENERAL = "P00"


class Proyecto(BaseModel):
    """Agrupa requisitos de un mismo dominio. Cada proyecto tiene su propio LEL
    (la memoria no se mezcla entre dominios, ADR 0008). `evaluacion` marca los
    proyectos que crea una corrida contra el corpus."""

    model_config = ConfigDict(extra="forbid")

    proyecto_id: str
    nombre: str = Field(min_length=1)
    descripcion: str | None = None
    tipo: Literal["normal", "evaluacion"] = "normal"
    creado: datetime = Field(default_factory=ahora)


class Origen(BaseModel):
    """De dónde salió el texto del requisito (trazabilidad hacia el documento)."""

    model_config = ConfigDict(extra="forbid")

    documento_id: str | None = None
    archivo: str | None = None
    pagina: int | None = None
    indice: int | None = None  # posición del requisito dentro del documento
    texto_original: str | None = None  # como venía en el documento, antes de que el humano lo editara


class Traza(BaseModel):
    """Documento por requisito: con esto se reconstruye todo el proceso."""

    model_config = ConfigDict(extra="forbid")

    req_id: str
    proyecto_id: str = PROYECTO_GENERAL
    texto: str
    origen: Origen | None = None
    estado: Estado
    config: dict[str, Any]
    creado: datetime = Field(default_factory=ahora)
    actualizado: datetime = Field(default_factory=ahora)
    transiciones: list[Transicion] = []
    mensajes: list[Mensaje] = []


class Validacion(BaseModel):
    """Respuesta del humano en `pendiente_validacion`.

    `interpretaciones_editadas` permite elegir otra interpretación o reescribir
    la propuesta, por término.
    """

    model_config = ConfigDict(extra="forbid")

    decision: Literal["aprobar", "rechazar"]
    interpretaciones_editadas: dict[str, Interpretacion] = {}
    comentario: str | None = None
