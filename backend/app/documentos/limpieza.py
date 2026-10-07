"""Limpieza del texto extraído y reconstrucción de párrafos (ADR 0009).

De las páginas crudas a párrafos con su página y su marca de numeración:
caracteres normalizados, sin números de página sueltos ni encabezados o pies
repetidos, renglones partidos unidos y palabras cortadas con guion reunidas.
Lo que se quita queda en `advertencias`: nada se descarta en silencio.

Las constantes son heurísticas de maquetación, no parámetros del experimento:
el humano confirma cada requisito antes de que entre al sistema.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from app.nlp import normalizar

from .patrones import detectar_marca, termina_oracion, tiene_obligacion

LINEAS_BORDE = 3  # renglones de arriba y de abajo de cada página donde se buscan encabezados, pies y números
FRACCION_LINEA_LLENA = 0.75  # en un PDF, un renglón más corto que esto (frente al ancho típico) cierra párrafo
MAX_PALABRAS_TITULO = 12

_NUMERO_PAGINA = re.compile(r"(?:[-–—]\s*)?(?:p[aá]g(?:ina)?\.?\s*)?\d{1,4}(?:\s*(?:de|/)\s*\d{1,4})?(?:\s*[-–—])?",
                            re.IGNORECASE)
_PALABRAS_DE_ENLACE = {"de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "e", "o", "u", "a",
                       "al", "en", "con", "por", "para", "que", "se", "su", "sus", "sin", "como", "cuando", "si",
                       "lo", "le", "les", "sobre", "entre", "hacia", "desde", "hasta", "mediante", "cada"}
_TIPOS_NUMERICOS = {"numero", "jerarquica"}


@dataclass
class Parrafo:
    texto: str  # renglones unidos, sin la marca
    pagina: int | None
    pagina_fin: int | None
    marca: str | None = None
    tipo_marca: str | None = None
    renglones: list[str] = field(default_factory=list)  # como venían, con la marca

    @property
    def original(self) -> str:
        return "\n".join(self.renglones)


@dataclass
class Limpieza:
    parrafos: list[Parrafo]
    advertencias: list[str]


def normalizar_caracteres(texto: str) -> str:
    """NFKC (ligaduras como «fi» en un solo carácter, espacios duros), sin guiones suaves ni caracteres de
    formato; los de control se vuelven espacio. Conserva los de uso privado: así
    se extraen las viñetas de Word."""
    texto = unicodedata.normalize("NFKC", texto).replace("\r\n", "\n").replace("\r", "\n")
    salida = []
    for c in texto:
        categoria = unicodedata.category(c)
        if c == "\n" or categoria[0] != "C" or categoria == "Co":
            salida.append(c)
        elif categoria == "Cc":
            salida.append(" ")
    return "".join(salida)


def _renglones(pagina: str) -> list[str]:
    return [re.sub(r"\s+", " ", r).strip() for r in normalizar_caracteres(pagina).split("\n")]


def _bordes(renglones: list[str]) -> list[int]:
    """Índices de los primeros y últimos LINEAS_BORDE renglones con texto."""
    con_texto = [i for i, r in enumerate(renglones) if r]
    return sorted(set(con_texto[:LINEAS_BORDE] + con_texto[-LINEAS_BORDE:]))


def _quitar_numeros_de_pagina(paginas: list[list[str]]) -> list[int]:
    """Quita (no deja en blanco: el párrafo puede seguir en la página siguiente)
    los números de página sueltos en los bordes. Devuelve las páginas afectadas."""
    afectadas = []
    for n, renglones in enumerate(paginas, 1):
        quitar = {i for i in _bordes(renglones) if _NUMERO_PAGINA.fullmatch(renglones[i])}
        if quitar:
            afectadas.append(n)
            renglones[:] = [r for i, r in enumerate(renglones) if i not in quitar]
    return afectadas


def _clave_repeticion(renglon: str) -> str:
    return re.sub(r"\d+", "#", normalizar(renglon))  # «Página 2 de 9» y «Página 3 de 9» son el mismo pie


def _puede_ser_encabezado(renglon: str) -> bool:
    if not renglon or tiene_obligacion(renglon):
        return False
    marca, _, resto = detectar_marca(renglon)
    return not (marca and not resto)  # «RF-01» solo en su renglón es la celda de una tabla, no un pie


def _quitar_repetidos(paginas: list[list[str]]) -> list[str]:
    """Encabezados y pies: renglones de los bordes que se repiten (salvo números)
    en al menos la mitad de las páginas con texto, y en dos como mínimo."""
    total = sum(1 for p in paginas if any(p))
    if total < 2:
        return []
    minimo = max(2, math.ceil(total / 2))
    conteo: Counter[str] = Counter()
    for renglones in paginas:
        conteo.update({_clave_repeticion(renglones[i]) for i in _bordes(renglones)
                       if _puede_ser_encabezado(renglones[i])})
    repetidos = {c for c, k in conteo.items() if k >= minimo}
    if not repetidos:
        return []
    ejemplos: dict[str, str] = {}
    quitados: Counter[str] = Counter()
    for renglones in paginas:
        quitar = set()
        for i in _bordes(renglones):
            clave = _clave_repeticion(renglones[i])
            if clave in repetidos and _puede_ser_encabezado(renglones[i]):
                quitar.add(i)
                ejemplos.setdefault(clave, renglones[i])
                quitados[clave] += 1
        renglones[:] = [r for i, r in enumerate(renglones) if i not in quitar]
    return [f"Encabezado o pie de página quitado ({quitados[c]} de {total} páginas): «{ejemplos[c]}»."
            for c in ejemplos]


def _empieza_en_mayuscula(renglon: str) -> bool:
    primero = renglon.lstrip("¿¡\"'«“(")[:1]
    return primero.isupper() or primero.isdigit()


def _queda_abierto(renglon: str) -> bool:
    """El renglón no puede cerrar un párrafo: termina en coma, guion o palabra de enlace."""
    if renglon.endswith((",", "-", "/")):
        return True
    palabras = normalizar(renglon).split()
    return bool(palabras) and palabras[-1] in _PALABRAS_DE_ENLACE


def _es_titulo_aislado(actual: Parrafo) -> bool:
    return (len(actual.renglones) == 1 and not tiene_obligacion(actual.texto)
            and len(actual.texto.split()) <= MAX_PALABRAS_TITULO)


def _empieza_parrafo(actual: Parrafo | None, previo: str, renglon: str, marca: str | None, tipo: str | None,
                     resto: str, llena: bool, maquetado: bool) -> bool:
    if actual is None:
        return True
    if marca:
        # «… compatible con la versión\n2.1 o superior»: número seguido de minúscula continúa la oración
        return not (tipo in _TIPOS_NUMERICOS and resto[:1].islower() and not termina_oracion(actual.texto))
    if not actual.texto:  # la marca venía sola en su renglón (celda de tabla): el texto sigue
        return False
    if not _empieza_en_mayuscula(renglon) or _queda_abierto(previo):
        return False
    if termina_oracion(previo):
        return True
    # Sin punto final: en un PDF los renglones se cortan por ancho, así que uno
    # corto cierra el párrafo (título o párrafo sin punto) y uno lleno sigue.
    # En texto plano no hay ancho de referencia: solo cierra un título aislado.
    return not llena if maquetado else _es_titulo_aislado(actual)


def _agregar(actual: Parrafo, renglon: str, pagina: int | None) -> None:
    if re.search(r"[^\W\d_]-$", actual.texto) and renglon[:1].islower():
        actual.texto = actual.texto[:-1] + renglon  # «autenti-» + «cación»
    else:
        actual.texto = f"{actual.texto} {renglon}".strip()
    actual.renglones.append(renglon)
    actual.pagina_fin = pagina


def reconstruir(renglones: list[tuple[str, int | None]], maquetado: bool) -> list[Parrafo]:
    """Une renglones en párrafos. Un renglón vacío siempre cierra el párrafo; una
    marca de numeración siempre abre uno nuevo (salvo número + minúscula)."""
    largos = sorted(len(r) for r, _ in renglones if r)
    ancho = largos[math.ceil(0.9 * (len(largos) - 1))] if largos else 0  # percentil 90: ignora renglones atípicos
    parrafos: list[Parrafo] = []
    actual: Parrafo | None = None
    previo = ""
    for renglon, pagina in renglones:
        if not renglon:
            actual, previo = None, ""
            continue
        marca, tipo, resto = detectar_marca(renglon)
        llena = len(previo) >= FRACCION_LINEA_LLENA * ancho
        if _empieza_parrafo(actual, previo, renglon, marca, tipo, resto, llena, maquetado):
            texto = resto if marca else renglon
            actual = Parrafo(texto=texto, pagina=pagina, pagina_fin=pagina, marca=marca, tipo_marca=tipo,
                             renglones=[renglon])
            parrafos.append(actual)
        else:
            _agregar(actual, renglon, pagina)
        previo = renglon
    return parrafos


def limpiar(paginas: list[str], con_paginas: bool, maquetado: bool) -> Limpieza:
    """`con_paginas`: las páginas son reales (PDF, o texto con saltos de página) y se
    numeran; solo entonces se buscan números de página, encabezados y pies.
    `maquetado`: el texto viene de un PDF, con renglones cortados por ancho."""
    por_pagina = [_renglones(p) for p in paginas]
    advertencias = []
    if con_paginas:
        afectadas = _quitar_numeros_de_pagina(por_pagina)
        if afectadas:
            advertencias.append(f"Números de página sueltos quitados en {len(afectadas)} páginas.")
        advertencias += _quitar_repetidos(por_pagina)
    renglones = [(r, n if con_paginas else None) for n, rs in enumerate(por_pagina, 1) for r in _sin_bordes_vacios(rs)]
    return Limpieza(reconstruir(renglones, maquetado), advertencias)


def _sin_bordes_vacios(renglones: list[str]) -> list[str]:
    """Los renglones vacíos al inicio o al final de una página no cierran párrafo:
    un párrafo puede seguir en la página siguiente."""
    con_texto = [i for i, r in enumerate(renglones) if r]
    return renglones[con_texto[0]:con_texto[-1] + 1] if con_texto else []
