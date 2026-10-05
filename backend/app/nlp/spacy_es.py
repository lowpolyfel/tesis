"""Acceso único a spaCy (es_core_news_sm) y utilidades de normalización."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Unidad:
    """Un término observado en un texto: cómo aparece y con qué claves se compara.

    Las claves son el lema y la forma superficial, ambos normalizados. Se usan las
    dos porque el lema de es_core_news_sm depende del contexto: «bitácora» sale
    como «bitácoro» (ADJ) sola, «bitácorar» (VERB) en una frase sin verbo y
    «bitácora» (NOUN) dentro de una oración (ADR 0004).
    """
    texto: str
    claves: frozenset[str]


class Analizador:
    """Envoltura delgada sobre spaCy con lo que necesitan filtros y reglas."""

    def __init__(self, modelo: str):
        self.modelo = modelo
        self.nlp = cargar_modelo(modelo)

    def doc(self, texto: str) -> Doc:
        return self.nlp(texto)

    def vocabulario(self, texto: str) -> set[str]:
        """Todas las claves (lema y forma, normalizados) de las palabras de un texto,
        sin filtrar por categoría: sirve para preguntar «¿esto ya aparece aquí?»."""
        d = self.doc(texto)
        claves = set()
        for t in d:
            if t.is_alpha:
                claves |= {normalizar(t.lemma_), normalizar(t.text)}
        claves |= {normalizar(e.text) for e in d.ents}
        return claves

    @staticmethod
    def _unidad(t) -> Unidad:
        return Unidad(t.text, frozenset({normalizar(t.lemma_), normalizar(t.text)}))

    def lemas_contenido(self, texto: str) -> dict[str, Unidad]:
        """{lema normalizado: unidad} de los términos de contenido."""
        return {
            normalizar(t.lemma_): self._unidad(t)
            for t in self.doc(texto)
            if t.pos_ in POS_CONTENIDO and not t.is_stop and t.is_alpha
        }

    def sustantivos_y_entidades(self, texto: str) -> dict[str, Unidad]:
        """{clave normalizada: unidad} de sustantivos y entidades nombradas."""
        d = self.doc(texto)
        salida = {
            normalizar(t.lemma_): self._unidad(t)
            for t in d
            if t.pos_ in POS_SUSTANTIVO and t.is_alpha and not t.is_stop
        }
        for e in d.ents:
            salida[normalizar(e.text)] = Unidad(e.text, frozenset({normalizar(e.text)}))
        return salida
