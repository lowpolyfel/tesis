"""Juez LLM de un par de requisitos (prompt `comparador_v1`).

El modelo clasifica la relación y cita un fragmento de cada requisito. El código
verifica que cada cita sea texto literal de su requisito (comparación sin
mayúsculas, acentos ni espacios repetidos) y lo registra; no descarta el juicio.
"""
from __future__ import annotations

import re

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.nlp import normalizar

from .modelos import EXPLICACION_MAX_PALABRAS, RequisitoBase, SalidaComparadorLLM

PROMPT = "comparador_v1"
_BORDES = "\"'«»“”‘’.,;:¡!¿? "


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", normalizar(texto)).strip(_BORDES)


def cita_literal(cita: str, texto: str) -> bool:
    """La cita aparece tal cual en el texto, salvo mayúsculas, acentos, espacios
    repetidos y comillas o puntuación en los extremos de la cita."""
    c = _plano(cita)
    return bool(c) and c in _plano(texto)


class Juez:
    def __init__(self, cliente: ClienteLLM, prompt: str = PROMPT):
        self.cliente = cliente
        self.prompt = cargar_prompt(prompt)

    def juzgar(self, a: RequisitoBase, b: RequisitoBase) -> Respuesta[SalidaComparadorLLM]:
        prompt = self.prompt.renderizar(req_a=a.req_id, texto_a=a.texto, req_b=b.req_id, texto_b=b.texto,
                                        explicacion_max_palabras=EXPLICACION_MAX_PALABRAS)
        return generar(self.cliente, prompt, SalidaComparadorLLM,
                       contexto={"explicacion_max_palabras": EXPLICACION_MAX_PALABRAS})
