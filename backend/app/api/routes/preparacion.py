"""Preparación antes de analizar: base de datos, Ollama y modelos (app/preparacion.py)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.orchestration import Servicio
from app.preparacion import PreparacionFallida, cargar_modelo, preparacion

from ..dependencias import UsuarioDep, obtener_servicio

router = APIRouter(tags=["preparacion"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


class EntradaCarga(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    modelo: str = Field(min_length=1, max_length=200)


@router.get("/preparacion")
def estado(srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """¿Responde la base? ¿Responde Ollama? ¿Está cada modelo del análisis descargado y en
    memoria (o, si es de un servicio externo, tiene su clave)? Con los proveedores que eligió
    la cuenta (ADR 0021). `listo` dice si se puede empezar."""
    u = usuario.usuario_id
    return preparacion(srv.repo, srv.deps.settings, elecciones=srv.perfiles.elecciones(u),
                       ollama_url=srv.perfiles.url_ollama(u))


@router.post("/preparacion/cargar")
def cargar(entrada: EntradaCarga, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """Precarga en memoria un modelo de Ollama del análisis. 422 si no es uno de ellos;
    502 si Ollama no responde o no lo puede cargar."""
    try:
        u = usuario.usuario_id
        return cargar_modelo(srv.deps.settings, entrada.modelo, elecciones=srv.perfiles.elecciones(u),
                             ollama_url=srv.perfiles.url_ollama(u))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except PreparacionFallida as e:
        raise HTTPException(502, str(e)) from e
