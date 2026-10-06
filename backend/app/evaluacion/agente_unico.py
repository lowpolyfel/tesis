"""Línea base de un solo agente (CONTEXTO §9, ADR 0014): una llamada, sin debate.

Recibe solo el texto del requisito (el ground truth nunca entra al prompt) y
devuelve si es ambiguo y, por término, el tipo de ambigüedad y la interpretación
que elige. Usa la misma taxonomía y el mismo límite de palabras que el
Clasificador, para que la diferencia con el sistema sea el debate y no el prompt.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.llm import ClienteLLM, FalloEstructurado, Respuesta, cargar_prompt, generar
from app.models import TipoAmbiguedad

from .emparejamiento import palabras

log = logging.getLogger(__name__)

PROMPT = "agente_unico_v1"


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TerminoAgenteUnico(Modelo):
    termino: str = Field(min_length=1)
    tipo_ambiguedad: TipoAmbiguedad
    interpretacion_elegida: str = Field(min_length=1)

    @field_validator("interpretacion_elegida")
    @classmethod
    def _limite_palabras(cls, v: str, info: ValidationInfo) -> str:
        limite = (info.context or {}).get("significado_max_palabras")
        if limite is not None and len(v.split()) > limite:
            raise ValueError(f"interpretacion_elegida tiene {len(v.split())} palabras; el máximo es {limite}")
        return v


class SalidaAgenteUnico(Modelo):
    ambiguo: bool
    terminos: list[TerminoAgenteUnico] = []

    @model_validator(mode="after")
    def _coherencia(self) -> "SalidaAgenteUnico":
        if self.ambiguo != bool(self.terminos):
            raise ValueError("si ambiguo es true, terminos lleva al menos un término; si es false, va vacía")
        vistos = [palabras(t.termino) for t in self.terminos]
        if len(vistos) != len(set(vistos)):
            raise ValueError("hay términos repetidos")
        return self


class ErrorLineaBase(Modelo):
    excepcion: str
    mensaje: str
    intentos: list[dict] = []  # salidas crudas del LLM si fue un FalloEstructurado


class EntradaLineaBase(Modelo):
    """Resultado de la línea base para un requisito del corpus: `resultado` o `error`."""

    resultado: SalidaAgenteUnico | None = None
    error: ErrorLineaBase | None = None
    modelo: str | None = None
    prompt_version: str = PROMPT
    intentos: int = 0

    @model_validator(mode="after")
    def _resultado_o_error(self) -> "EntradaLineaBase":
        if (self.resultado is None) == (self.error is None):
            raise ValueError("debe tener resultado o error, no ambos ni ninguno")
        return self


class AgenteUnico:
    def __init__(self, cliente: ClienteLLM, significado_max_palabras: int, prompt: str = PROMPT):
        self.cliente = cliente
        self.max_palabras = significado_max_palabras
        self.prompt = cargar_prompt(prompt)

    def analizar(self, texto: str) -> Respuesta[SalidaAgenteUnico]:
        prompt = self.prompt.renderizar(texto=texto, max_palabras=self.max_palabras)
        return generar(self.cliente, prompt, SalidaAgenteUnico,
                       contexto={"significado_max_palabras": self.max_palabras})


def linea_base(cliente: ClienteLLM, significado_max_palabras: int, texto: str) -> EntradaLineaBase:
    """Corre la línea base sobre un requisito. Una falla queda registrada, no se propaga:
    un requisito sin respuesta cuenta como «sin decisión» en las métricas."""
    try:
        r = AgenteUnico(cliente, significado_max_palabras).analizar(texto)
        return EntradaLineaBase(resultado=r.valor, modelo=r.modelo, prompt_version=r.prompt_version,
                                intentos=len(r.intentos))
    except FalloEstructurado as e:
        return EntradaLineaBase(error=ErrorLineaBase(excepcion=type(e).__name__, mensaje=str(e),
                                                     intentos=e.payload()["intentos"]),
                                modelo=e.modelo, prompt_version=e.prompt_version, intentos=len(e.intentos))
    except Exception as e:  # p. ej. el servidor del modelo no responde
        log.warning("La línea base falló: %s", e)
        return EntradaLineaBase(error=ErrorLineaBase(excepcion=type(e).__name__, mensaje=str(e)),
                                modelo=getattr(cliente, "modelo", None))
