"""Emparejamiento de términos contra el ground truth (ADR 0014).

Un término del sistema (o de la línea base) y uno del ground truth se emparejan
con el primer criterio que cumplan, en este orden:

1. `exacto`: las mismas palabras tras normalizar (minúsculas, sin acentos ni
   puntuación): «Sesión» y «sesión».
2. `contencion`: las palabras de uno aparecen seguidas dentro del otro, palabra
   por palabra: «su historial» y «su», «usuarios» y «todos los usuarios». No por
   subcadena: «su» no está dentro de «usuario».
3. `lema`: el mismo conjunto, no vacío, de lemas de contenido según spaCy:
   «sesiones» y «sesión».

Cada término se empareja con a lo más uno del otro lado: primero se toman todos
los pares exactos, luego los de contención y al final los de lema, en orden de
aparición. Así un acierto no se cuenta dos veces.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal

from app.nlp import normalizar

Criterio = Literal["exacto", "contencion", "lema"]
CRITERIOS: tuple[Criterio, ...] = ("exacto", "contencion", "lema")
Lematizador = Callable[[str], frozenset[str]]


def palabras(texto: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\w+", normalizar(texto)))


def _contiene(larga: tuple[str, ...], corta: tuple[str, ...]) -> bool:
    n = len(corta)
    return 0 < n <= len(larga) and any(larga[i:i + n] == corta for i in range(len(larga) - n + 1))


def aparece_en(termino: str, texto: str) -> bool:
    """El término aparece palabra por palabra en el texto (sin mayúsculas ni acentos)."""
    return _contiene(palabras(texto), palabras(termino))


def sin_lemas(_texto: str) -> frozenset[str]:
    return frozenset()


def lematizador(analizador) -> Lematizador:
    """Lemas de contenido de un término, con caché. Sin analizador, el criterio `lema` no aplica."""
    if analizador is None:
        return sin_lemas
    cache: dict[str, frozenset[str]] = {}

    def lemas(texto: str) -> frozenset[str]:
        if texto not in cache:
            cache[texto] = frozenset(analizador.lemas_contenido(texto))
        return cache[texto]

    return lemas


def criterio(a: str, b: str, lemas: Lematizador = sin_lemas) -> Criterio | None:
    pa, pb = palabras(a), palabras(b)
    if not pa or not pb:
        return None
    if pa == pb:
        return "exacto"
    if _contiene(pa, pb) or _contiene(pb, pa):
        return "contencion"
    la = lemas(a)
    if la and la == lemas(b):
        return "lema"
    return None


@dataclass(frozen=True)
class Par:
    izquierda: int  # índice en la primera lista
    derecha: int  # índice en la segunda
    criterio: Criterio


def emparejar(izquierda: list[str], derecha: list[str], lemas: Lematizador = sin_lemas) -> list[Par]:
    """Pares uno a uno entre dos listas de términos, del criterio más fuerte al más débil."""
    fuerza = {(i, j): c for i, a in enumerate(izquierda) for j, b in enumerate(derecha)
              if (c := criterio(a, b, lemas)) is not None}
    usados_i: set[int] = set()
    usados_j: set[int] = set()
    pares: list[Par] = []
    for nivel in CRITERIOS:
        for i in range(len(izquierda)):
            if i in usados_i:
                continue
            for j in range(len(derecha)):
                if j not in usados_j and fuerza.get((i, j)) == nivel:
                    pares.append(Par(i, j, nivel))
                    usados_i.add(i)
                    usados_j.add(j)
                    break
    return sorted(pares, key=lambda p: (p.izquierda, p.derecha))
