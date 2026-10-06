"""Agente Modelador: formaliza lo que el humano validó. No valida (ADR 0010).

- `modelar`: entrada del LEL de un término con ambigüedad léxica.
- `modelar_requisito`: el requisito reescrito con todas las interpretaciones
  validadas y sus metas para el modelo de metas estratégicas.
"""
from __future__ import annotations

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.models import Interpretacion, SalidaModelador, SalidaModeladorLLM, SalidaModeladorRequisito

from ..base import a_json


class Modelador:
    def __init__(self, cliente: ClienteLLM, prompt: str = "modelador_v1",
                 prompt_requisito: str = "modelador_requisito_v1"):
        self.cliente = cliente
        self.prompt = cargar_prompt(prompt)
        self.prompt_requisito = cargar_prompt(prompt_requisito)

    def modelar(self, texto: str, termino: str, interpretacion: Interpretacion) -> Respuesta[SalidaModelador]:
        prompt = self.prompt.renderizar(texto=texto, termino=termino, interpretacion=a_json(interpretacion))
        r = generar(self.cliente, prompt, SalidaModeladorLLM)
        return Respuesta(SalidaModelador(entrada_lel=r.valor.entrada_lel), r.modelo, r.prompt_version, r.intentos)

    def modelar_requisito(self, texto: str, resoluciones: list[dict], vaguedad: list[str],
                          simbolos: list[str]) -> Respuesta[SalidaModeladorRequisito]:
        """`resoluciones`: [{termino, tipo_ambiguedad, interpretacion}] validadas por el humano."""
        prompt = self.prompt_requisito.renderizar(
            texto=texto, resoluciones=a_json(resoluciones) if resoluciones else "(ninguna: el requisito no tenía ambigüedad)",
            vaguedad=", ".join(vaguedad) or "(ninguna)", simbolos=", ".join(simbolos) or "(el LEL está vacío)")
        return generar(self.cliente, prompt, SalidaModeladorRequisito)
