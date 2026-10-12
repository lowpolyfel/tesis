"""Agente Modelador: formaliza lo que el humano validó. No valida (ADR 0010).

- `modelar`: entrada del LEL de un término con ambigüedad léxica.
- `modelar_requisito`: el requisito reescrito completo con todas las
  interpretaciones validadas, su tipo (funcional o no funcional), los supuestos
  que tomó del contexto del proyecto y sus metas (ADR 0017).
- `mapear`: organiza el mapa conceptual del proyecto con los conceptos y las
  relaciones candidatas que preparó el código (ADR 0020).
"""
from __future__ import annotations

from collections.abc import Callable

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.models import (
    Interpretacion,
    SalidaMapaConceptual,
    SalidaModelador,
    SalidaModeladorLLM,
    SalidaModeladorRequisito,
)

from ..base import a_json, texto_contexto


class Modelador:
    def __init__(self, cliente: ClienteLLM, prompt: str = "modelador_v2",
                 prompt_requisito: str = "modelador_requisito_v2", prompt_mapa: str = "modelador_mapa_v1"):
        self.cliente = cliente
        self.prompt = cargar_prompt(prompt)
        self.prompt_requisito = cargar_prompt(prompt_requisito)
        self.prompt_mapa = cargar_prompt(prompt_mapa)

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

    def mapear(self, proyecto: str, contexto: str | None, requisitos: list[str], conceptos: list[dict],
               proposiciones: list[dict], max_conceptos: int, max_proposiciones: int,
               verificar: Callable[[SalidaMapaConceptual], None] | None = None) -> Respuesta[SalidaMapaConceptual]:
        """`conceptos`: [{id, etiqueta, tipo, peso}]; `proposiciones`: [{origen, enlace, destino}].
        `verificar` rechaza referencias a conceptos que no existen (se reintenta una vez)."""
        prompt = self.prompt_mapa.renderizar(
            proyecto=proyecto, contexto=texto_contexto(contexto),
            requisitos="\n".join(f"- {r}" for r in requisitos) or "(ninguno)",
            conceptos=a_json(conceptos), proposiciones=a_json(proposiciones) if proposiciones else "(ninguna)",
            max_conceptos=max_conceptos, max_proposiciones=max_proposiciones)
        return generar(self.cliente, prompt, SalidaMapaConceptual, verificar=verificar)
