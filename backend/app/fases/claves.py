"""Cómo se reconoce un mismo término en el LEL, en la memoria y en las entrevistas (ADR 0024).

La clave de un término es su forma sin acentos, en minúsculas, sin artículo inicial y con
cada palabra en singular por reglas simples del español («Las consultas» → «consulta»,
«doctores» → «doctor»). No es un lematizador: es una llave estable para guardar y comparar.
Dentro del grafo, además, se compara con spaCy (`Comparador`, como en la versión 1).
"""
from __future__ import annotations

import re

from app.artefactos.terminos import sin_articulo
from app.nlp import normalizar

_PALABRA = re.compile(r"[a-zñü0-9]+")
_INVARIABLES = {"mes", "gas", "tos", "dos", "tres", "seis", "lunes", "martes", "miercoles", "jueves", "viernes",
                "pais", "pies", "anis"}


def singular(palabra: str) -> str:
    w = palabra
    if len(w) <= 3 or w in _INVARIABLES or w.endswith(("is", "us", "ss")):
        return w
    if w.endswith("ces") and len(w) > 4:  # luces → luz, veces → vez
        return w[:-3] + "z"
    if w.endswith("es") and len(w) > 4 and w[-3] in "lrndjy":  # doctores, papeles, ciudades, relojes, leyes
        return w[:-2]
    if w.endswith("s"):
        return w[:-1]
    return w


def clave(termino: str) -> str:
    """«Las Consultas» → «consulta»; «dar de alta» → «dar de alta»."""
    palabras = _PALABRA.findall(normalizar(sin_articulo(termino or "")))
    return " ".join(singular(p) for p in palabras)


def fragmento(texto: str, termino: str, radio: int = 160) -> str:
    """El pedazo de `texto` alrededor de la primera aparición de `termino` (sin distinguir
    acentos ni mayúsculas), con «…» si se recorta. Si no aparece, el principio del texto."""
    base, aguja = normalizar(texto), normalizar(termino)
    i = base.find(aguja) if aguja else -1
    if i == -1:  # en plural u otra forma: se busca la raíz de la primera palabra
        raiz = clave(termino).split(" ")[0][:5]
        i = base.find(raiz) if raiz else -1
    if i == -1 or len(texto) <= 2 * radio:
        return texto if len(texto) <= 2 * radio else texto[: 2 * radio].rstrip() + "…"
    inicio, fin = max(0, i - radio), min(len(texto), i + len(aguja) + radio)
    return ("…" if inicio else "") + texto[inicio:fin].strip() + ("…" if fin < len(texto) else "")
