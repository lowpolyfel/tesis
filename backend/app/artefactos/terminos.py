"""Comparación de términos contra textos, sin LLM (ADR 0011).

Cada palabra se compara por su forma normalizada (minúsculas, sin acentos) y,
si hay spaCy, también por su lema: las dos claves, como en la memoria del LEL
(ADR 0003, 0004), porque el lema de es_core_news_sm depende del contexto.
Un término «aparece» en un texto si su secuencia de palabras está contigua en
él; dos términos son «el mismo» si sus secuencias coinciden palabra por palabra.
"""
from __future__ import annotations

import re

from app.nlp import Analizador, normalizar

Palabras = tuple[frozenset[str], ...]

_ARTICULO = re.compile(r"^(el|la|los|las|lo|un|una|unos|unas)\s+", re.IGNORECASE)
_INFINITIVO = re.compile(r"^[a-z]*(ar|er|ir)(se|lo|la|los|las|le|les)?$")
_BORDES = ".,;:¡!¿?«»\"'()[]{} "


class Comparador:
    def __init__(self, analizador: Analizador | None = None):
        self.analizador = analizador
        self._cache: dict[str, Palabras] = {}

    def palabras(self, texto: str) -> Palabras:
        if texto not in self._cache:
            if self.analizador is None:
                self._cache[texto] = tuple(frozenset({p}) for p in re.findall(r"\w+", normalizar(texto)))
            else:
                self._cache[texto] = tuple(frozenset({normalizar(t.lemma_), normalizar(t.text)})
                                           for t in self.analizador.doc(texto) if not (t.is_punct or t.is_space))
        return self._cache[texto]

    def aparece(self, termino: str, texto: str) -> bool:
        aguja, pajar = self.palabras(termino), self.palabras(texto)
        n = len(aguja)
        return n > 0 and any(all(aguja[k] & pajar[i + k] for k in range(n)) for i in range(len(pajar) - n + 1))

    def mismo(self, a: str, b: str) -> bool:
        pa, pb = self.palabras(a), self.palabras(b)
        return len(pa) == len(pb) > 0 and all(x & y for x, y in zip(pa, pb))


def sin_articulo(texto: str) -> str:
    """«El sistema» → «sistema». Espacios colapsados."""
    return _ARTICULO.sub("", " ".join(texto.split()), count=1)


def nombre_actor(texto: str) -> str:
    """Nombre normalizado de un actor: sin artículo inicial y con minúscula
    inicial salvo siglas («El Usuario» → «usuario», «SAT» → «SAT»)."""
    limpio = sin_articulo(texto)
    primera = limpio.split(" ", 1)[0]
    if primera[1:] == primera[1:].lower():
        return limpio[:1].lower() + limpio[1:]
    return limpio


def separar_accion(enunciado: str) -> tuple[str | None, str]:
    """Primera palabra = verbo en infinitivo, resto = objeto. Si la primera
    palabra no tiene forma de infinitivo, no se inventa un verbo."""
    limpio = " ".join(enunciado.split()).strip(_BORDES)
    primera, _, resto = limpio.partition(" ")
    if _INFINITIVO.match(normalizar(primera)):
        return primera.lower(), resto.strip(_BORDES)
    return None, limpio


def numero_req(req_id: str) -> int:
    return int(req_id[1:]) if req_id[1:].isdigit() else 0


def numero_meta(meta_id: str) -> int:
    return int(meta_id[1:]) if meta_id[1:].isdigit() else 0
