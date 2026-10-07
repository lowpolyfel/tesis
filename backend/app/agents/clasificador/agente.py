"""Agente Clasificador: genera interpretaciones candidatas. No decide cuál es la correcta."""
from __future__ import annotations

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.models import (
    EntradaLEL,
    Interpretacion,
    Objecion,
    SalidaClasificador,
    SalidaRefinamiento,
    TerminoCandidato,
)
from app.nlp.spacy_es import normalizar

from ..base import a_json, texto_contexto


class Clasificador:
    def __init__(self, cliente: ClienteLLM, significado_max_palabras: int,
                 prompt: str = "clasificador_v3", prompt_refinamiento: str = "clasificador_refinamiento_v1"):
        self.cliente = cliente
        self.max_palabras = significado_max_palabras
        self.prompt = cargar_prompt(prompt)
        self.prompt_refinamiento = cargar_prompt(prompt_refinamiento)

    @property
    def _contexto(self) -> dict:
        return {"significado_max_palabras": self.max_palabras}

    def clasificar(self, texto: str, candidatos: list[TerminoCandidato], lel: list[EntradaLEL],
                   contexto: str | None = None) -> Respuesta[SalidaClasificador]:
        esperados = {normalizar(c.termino) for c in candidatos}

        def verificar(s: SalidaClasificador) -> None:
            recibidos = [normalizar(r.termino) for r in s.resultados]
            faltan = esperados - set(recibidos)
            sobran = set(recibidos) - esperados
            if faltan or sobran or len(recibidos) != len(set(recibidos)):
                raise ValueError(f"debe haber exactamente un resultado por término candidato; faltan {sorted(faltan)}, sobran {sorted(sobran)}")

        variables = {"texto": texto, "terminos": a_json(candidatos), "lel": a_json(lel), "max_palabras": self.max_palabras}
        if "${contexto}" in self.prompt.usuario:  # las versiones anteriores a v3 no lo usan
            variables["contexto"] = texto_contexto(contexto)
        prompt = self.prompt.renderizar(**variables)
        return generar(self.cliente, prompt, SalidaClasificador, contexto=self._contexto, verificar=verificar)

    def refinar(self, texto: str, termino: str, interpretaciones: list[Interpretacion],
                objeciones: list[Objecion]) -> Respuesta[SalidaRefinamiento]:
        previos = {i.id for i in interpretaciones}

        def verificar(s: SalidaRefinamiento) -> None:
            vivas = {i.id for i in s.interpretaciones}
            retiradas = {r.interpretacion_id for r in s.retiradas}
            if not vivas <= previos or not retiradas <= previos:
                raise ValueError(f"solo puede refinar o retirar interpretaciones existentes {sorted(previos)}; no crear nuevas")
            if vivas | retiradas != previos:
                raise ValueError(f"cada interpretación {sorted(previos)} debe conservarse o retirarse")

        prompt = self.prompt_refinamiento.renderizar(texto=texto, termino=termino, interpretaciones=a_json(interpretaciones),
                                                    objeciones=a_json(objeciones), max_palabras=self.max_palabras)
        return generar(self.cliente, prompt, SalidaRefinamiento, contexto=self._contexto, verificar=verificar)
