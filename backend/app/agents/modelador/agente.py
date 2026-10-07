"""Agente Modelador: formaliza lo que el humano validó. No valida (ADR 0010).

- `modelar`: entrada del LEL de un término con ambigüedad léxica.
- `modelar_requisito`: el requisito reescrito completo con todas las
  interpretaciones validadas, su tipo (funcional o no funcional), los supuestos
  que tomó del contexto del proyecto y sus metas (ADR 0017).
"""
from __future__ import annotations

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.models import Interpretacion, SalidaModelador, SalidaModeladorLLM, SalidaModeladorRequisito

from ..base import a_json, texto_contexto


class Modelador:
    def __init__(self, cliente: ClienteLLM, prompt: str = "modelador_v2",
                 prompt_requisito: str = "modelador_requisito_v2"):
        self.cliente = cliente
        self.prompt = cargar_prompt(prompt)
        self.prompt_requisito = cargar_prompt(prompt_requisito)

    def modelar(self, texto: str, termino: str, interpretacion: Interpretacion,
                contexto: str | None = None) -> Respuesta[SalidaModelador]:
        variables = {"texto": texto, "termino": termino, "interpretacion": a_json(interpretacion)}
        if "${contexto}" in self.prompt.usuario:
            variables["contexto"] = texto_contexto(contexto)
        prompt = self.prompt.renderizar(**variables)
        r = generar(self.cliente, prompt, SalidaModeladorLLM)
        return Respuesta(SalidaModelador(entrada_lel=r.valor.entrada_lel), r.modelo, r.prompt_version, r.intentos)

    def modelar_requisito(self, texto: str, resoluciones: list[dict], vaguedad: list[str],
                          simbolos: list[str], contexto: str | None = None,
                          regionales: list[str] | None = None) -> Respuesta[SalidaModeladorRequisito]:
        """`resoluciones`: [{termino, tipo_ambiguedad, interpretacion}] ya validadas."""
        variables = {
            "texto": texto,
            "resoluciones": a_json(resoluciones) if resoluciones else "(ninguna: el requisito no tenía ambigüedad)",
            "vaguedad": ", ".join(vaguedad) or "(ninguna)", "simbolos": ", ".join(simbolos) or "(el LEL está vacío)",
        }
        if "${contexto}" in self.prompt_requisito.usuario:
            variables["contexto"] = texto_contexto(contexto)
            variables["regionales"] = ", ".join(regionales or []) or "(ninguna)"
        prompt = self.prompt_requisito.renderizar(**variables)
        return generar(self.cliente, prompt, SalidaModeladorRequisito)
