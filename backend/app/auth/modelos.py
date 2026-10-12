"""Documento de una cuenta (colección `usuarios`). Nunca guarda una contraseña, un
código ni un token en claro: solo sus hashes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ahora

Proposito = Literal["registro", "entrar", "restablecer"]


class Codigo(BaseModel):
    """El código de 6 dígitos enviado por correo que la cuenta tiene pendiente (uno a la vez)."""
    proposito: Proposito
    hash: str
    expira: datetime
    enviado: datetime = Field(default_factory=ahora)
    intentos: int = 0


class Sesion(BaseModel):
    hash: str  # sha256 del token que lleva la cookie
    creada: datetime = Field(default_factory=ahora)
    expira: datetime


class Usuario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario_id: str
    nombre: str
    correo: str  # normalizado: sin espacios y en minúsculas
    contrasena: str  # scrypt$N$r$p$sal$hash
    verificado: bool = False  # confirmó su correo con el código
    creado: datetime = Field(default_factory=ahora)
    codigo: Codigo | None = None
    sesiones: list[Sesion] = Field(default_factory=list)
    fallos: int = 0  # contraseñas incorrectas seguidas
    bloqueado_hasta: datetime | None = None


class UsuarioPublico(BaseModel):
    """Lo que la API devuelve de una cuenta."""
    usuario_id: str
    nombre: str
    correo: str
    creado: datetime


def publico(u: Usuario) -> UsuarioPublico:
    return UsuarioPublico(usuario_id=u.usuario_id, nombre=u.nombre, correo=u.correo, creado=u.creado)
