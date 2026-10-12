"""Agente Revisor del contexto (ADR 0022).

- `ficha`: ordena el contexto general del proyecto en una ficha (resumen, actores,
  conceptos, procesos, reglas, lo que queda fuera y lo que falta precisar).
- `triar`: compara requisitos con esa ficha y dice de cada uno si es claro, ambiguo
  o incompleto, con el motivo y las preguntas que haría a una persona.
- `separar`: reconoce los requisitos de un texto pegado o de un documento en cualquier
  redacción, no solo con «debe» o «podrá» (ADR 0023).
"""
from __future__ import annotations

from collections.abc import Callable

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.models import SalidaFichaContexto, SalidaSeparacion, SalidaTriaje


class Revisor:
    def __init__(self, cliente: ClienteLLM, prompt_ficha: str = "revisor_ficha_v1",
                 prompt_triaje: str = "revisor_triaje_v1", prompt_separacion: str = "revisor_separacion_v1"):
        self.cliente = cliente
        self.prompt_ficha = cargar_prompt(prompt_ficha)
        self.prompt_triaje = cargar_prompt(prompt_triaje)
        self.prompt_separacion = cargar_prompt(prompt_separacion)

    def ficha(self, proyecto: str, contexto: str) -> Respuesta[SalidaFichaContexto]:
        return generar(self.cliente, self.prompt_ficha.renderizar(proyecto=proyecto, contexto=contexto),
                       SalidaFichaContexto)

    def triar(self, ficha_md: str, requisitos: list[str]) -> Respuesta[SalidaTriaje]:
        """`requisitos` en orden; la salida trae uno por requisito con su `indice` (desde 1)."""
        numerados = "\n".join(f"{i}. {t}" for i, t in enumerate(requisitos, 1))

        def completo(s: SalidaTriaje) -> None:
            if sorted(r.indice for r in s.requisitos) != list(range(1, len(requisitos) + 1)):
                raise ValueError(f"se esperaba un resultado por requisito, con indice del 1 al {len(requisitos)}")

        prompt = self.prompt_triaje.renderizar(ficha=ficha_md, requisitos=numerados, total=len(requisitos))
        return generar(self.cliente, prompt, SalidaTriaje, verificar=completo)

    def separar(self, contexto: str, parrafos: str,
                verificar: Callable[[SalidaSeparacion], None] | None = None) -> Respuesta[SalidaSeparacion]:
        """`parrafos`: el texto numerado «P1 [p. 2] …». `verificar` revisa que cada requisito
        salga de verdad de sus párrafos (se reintenta una vez si no)."""
        prompt = self.prompt_separacion.renderizar(contexto=contexto, parrafos=parrafos)
        return generar(self.cliente, prompt, SalidaSeparacion, verificar=verificar)
