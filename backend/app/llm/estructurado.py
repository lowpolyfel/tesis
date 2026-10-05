"""Llamada con salida estructurada: validar, reintentar una vez, fallar con traza (ADR 0001).

El esquema se agrega al prompt y la salida cruda se valida con Pydantic. Si no
valida (o no pasa la verificación semántica del agente), se reintenta una vez
con el error en el prompt. Si vuelve a fallar se lanza `FalloEstructurado` con
ambas salidas crudas, para registrarlas en la traza.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .cliente import ClienteLLM
from .prompts import PromptRenderizado

T = TypeVar("T", bound=BaseModel)

INSTRUCCION_JSON = (
    "\n\nResponde únicamente con un objeto JSON válido que cumpla este esquema, "
    "sin texto antes ni después:\n{esquema}"
)
REINTENTO = (
    "\n\nTu respuesta anterior no fue válida.\nError:\n{error}\n\nRespuesta anterior:\n{anterior}\n\n"
    "Corrige el error y responde de nuevo solo con el JSON."
)


@dataclass
class Intento:
    salida_cruda: str
    error: str | None = None


@dataclass
class Respuesta(Generic[T]):
    valor: T
    modelo: str
    prompt_version: str
    intentos: list[Intento] = field(default_factory=list)

    @property
    def hubo_reintento(self) -> bool:
        return len(self.intentos) > 1


class FalloEstructurado(Exception):
    def __init__(self, prompt_version: str, modelo: str, intentos: list[Intento]):
        self.prompt_version = prompt_version
        self.modelo = modelo
        self.intentos = intentos
        super().__init__(f"{prompt_version} ({modelo}) no produjo una salida válida tras el reintento: {intentos[-1].error}")

    def payload(self) -> dict:
        return {
            "prompt_version": self.prompt_version,
            "modelo": self.modelo,
            "intentos": [{"salida_cruda": i.salida_cruda, "error": i.error} for i in self.intentos],
        }


def extraer_json(texto: str) -> str:
    """Tolera bloques ``` y texto alrededor: toma del primer '{' al último '}'."""
    inicio, fin = texto.find("{"), texto.rfind("}")
    return texto[inicio : fin + 1] if inicio != -1 and fin > inicio else texto


def generar(
    cliente: ClienteLLM,
    prompt: PromptRenderizado,
    esquema: type[T],
    *,
    contexto: dict | None = None,
    verificar: Callable[[T], None] | None = None,
) -> Respuesta[T]:
    esquema_json = esquema.model_json_schema()
    usuario = prompt.usuario + INSTRUCCION_JSON.format(esquema=json.dumps(esquema_json, ensure_ascii=False))
    actual = PromptRenderizado(prompt.version, prompt.sistema, usuario)
    intentos: list[Intento] = []
    for _ in range(2):
        crudo = cliente.completar(actual, esquema_json)
        try:
            valor = esquema.model_validate_json(extraer_json(crudo), context=contexto)
            if verificar:
                verificar(valor)
            intentos.append(Intento(crudo))
            return Respuesta(valor, cliente.modelo, prompt.version, intentos)
        except (ValidationError, ValueError) as e:
            intentos.append(Intento(crudo, str(e)))
            actual = PromptRenderizado(prompt.version, prompt.sistema, usuario + REINTENTO.format(error=e, anterior=crudo))
    raise FalloEstructurado(prompt.version, cliente.modelo, intentos)
