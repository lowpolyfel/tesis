"""Acceso único a spaCy (es_core_news_sm) y utilidades de normalización."""
from __future__ import annotations

import unicodedata
from functools import lru_cache

import spacy
from spacy.language import Language
from spacy.tokens import Doc

# Categorías gramaticales que cuentan como "términos de contenido" (R1)
POS_CONTENIDO = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
# Sustantivos y nombres propios (R2)
POS_SUSTANTIVO = {"NOUN", "PROPN"}


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar sin depender de la ortografía."""
    sin_acentos = unicodedata.normalize("NFD", texto)
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return sin_acentos.lower().strip()


@lru_cache
def cargar_modelo(nombre: str) -> Language:
    try:
        return spacy.load(nombre)
    except OSError as e:  # el modelo no está instalado
        raise RuntimeError(
            f"No está instalado el modelo de spaCy '{nombre}'. Instálalo con: python -m spacy download {nombre}"
        ) from e


class Analizador:
    """Envoltura delgada sobre spaCy con lo que necesitan filtros y reglas."""

    def __init__(self, modelo: str):
        self.modelo = modelo
        self.nlp = cargar_modelo(modelo)

    def doc(self, texto: str) -> Doc:
        return self.nlp(texto)

    def lemas_contenido(self, texto: str) -> dict[str, str]:
        """{lema normalizado: forma en el texto} de los términos de contenido."""
        return {
            normalizar(t.lemma_): t.text
            for t in self.doc(texto)
            if t.pos_ in POS_CONTENIDO and not t.is_stop and t.is_alpha
        }

    def sustantivos_y_entidades(self, texto: str) -> dict[str, str]:
        """{clave normalizada: forma en el texto} de sustantivos y entidades nombradas."""
        d = self.doc(texto)
        salida = {normalizar(t.lemma_): t.text for t in d if t.pos_ in POS_SUSTANTIVO and t.is_alpha and not t.is_stop}
        for e in d.ents:
            salida[normalizar(e.text)] = e.text
        return salida
