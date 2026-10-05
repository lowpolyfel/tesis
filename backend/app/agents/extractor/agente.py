"""Agente Extractor: separa el vocabulario del dominio. No interpreta."""
from __future__ import annotations

from dataclasses import dataclass

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.models import Posicion, SalidaExtractor, SalidaExtractorLLM, TerminoExtraido
from app.nlp.spacy_es import normalizar


@dataclass
class ResultadoExtraccion:
    salida: SalidaExtractor
    respuesta: Respuesta
    descartados: list[str]  # términos que el LLM devolvió y no aparecen en el texto


def ubicar_terminos(texto: str, salida_llm: SalidaExtractorLLM) -> tuple[list[TerminoExtraido], list[str]]:
    """La posición la calcula el código (ADR 0001): búsqueda sin mayúsculas ni acentos.

    Si un término se repite, cada aparición en la lista toma la siguiente ocurrencia.
    """
    base = normalizar(texto)
    usados: set[tuple[int, int]] = set()
    terminos, descartados = [], []
    for t in salida_llm.terminos:
        aguja = normalizar(t.termino)
        inicio = base.find(aguja)
        while inicio != -1 and (inicio, inicio + len(aguja)) in usados:
            inicio = base.find(aguja, inicio + 1)
        if inicio == -1 or not aguja:
            descartados.append(t.termino)
            continue
        fin = inicio + len(aguja)
        usados.add((inicio, fin))
        terminos.append(TerminoExtraido(termino=texto[inicio:fin], posicion=Posicion(inicio=inicio, fin=fin),
                                        categoria_tentativa=t.categoria_tentativa))
    return sorted(terminos, key=lambda x: x.posicion.inicio), descartados


class Extractor:
    def __init__(self, cliente: ClienteLLM, prompt: str = "extractor_v1"):
        self.cliente = cliente
        self.prompt = cargar_prompt(prompt)

    def extraer(self, texto: str) -> ResultadoExtraccion:
        respuesta = generar(self.cliente, self.prompt.renderizar(texto=texto), SalidaExtractorLLM)
        terminos, descartados = ubicar_terminos(texto, respuesta.valor)
        return ResultadoExtraccion(SalidaExtractor(terminos=terminos), respuesta, descartados)
