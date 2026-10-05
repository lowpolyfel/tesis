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


class Traza(BaseModel):
    """Documento por requisito: con esto se reconstruye todo el proceso."""

    model_config = ConfigDict(extra="forbid")

    req_id: str
    texto: str
    estado: Estado
    config: dict[str, Any]
    creado: datetime = Field(default_factory=ahora)
    actualizado: datetime = Field(default_factory=ahora)
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
