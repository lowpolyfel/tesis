"""Agente Modelador: formaliza la interpretación validada como entrada del LEL. No valida."""
from __future__ import annotations

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.models import Interpretacion, SalidaModelador, SalidaModeladorLLM

from ..base import a_json


class Modelador:
    def __init__(self, cliente: ClienteLLM, prompt: str = "modelador_v1"):
        self.cliente = cliente
        self.prompt = cargar_prompt(prompt)

    def modelar(self, texto: str, termino: str, interpretacion: Interpretacion) -> Respuesta[SalidaModelador]:
        prompt = self.prompt.renderizar(texto=texto, termino=termino, interpretacion=a_json(interpretacion))
        r = generar(self.cliente, prompt, SalidaModeladorLLM)
        # Metas y Big Picture: stub en esta fase (se generan en código, no por el LLM)
        salida = SalidaModelador(
            entrada_lel=r.valor.entrada_lel,
            metas={"estado": "stub", "fase": "pendiente", "termino": termino},
            big_picture={"estado": "stub", "fase": "pendiente", "requisito": texto, "termino": termino,
                         "interpretacion": interpretacion.id},
        )
        return Respuesta(salida, r.modelo, r.prompt_version, r.intentos)
