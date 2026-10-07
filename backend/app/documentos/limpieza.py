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
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property

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
# Primera palabra (con mayúscula inicial) que abre oración: «El», «La»… a media oración van en minúscula,
# así que tras un renglón sin punto final abren un párrafo nuevo (requisitos uno por renglón y sin punto).
_ABREN_ORACION = {"el", "la", "los", "las", "lo", "un", "una", "unos", "unas", "cada", "todo", "toda", "todos",
                  "todas", "ningun", "ninguna", "este", "esta", "estos", "estas", "dicho", "dicha", "dichos",
                  "dichas", "se", "si", "cuando", "solo", "ademas", "tambien", "asimismo", "debe", "deben",
                  "debera", "deberan", "deberia", "deberian", "podra", "podran", "puede", "pueden", "permitira",
                  "permitiran", "es"}
_GUION_SUAVE_FINAL = re.compile(r"\u00ad[ \t]*(?=\r?\n|\r|\Z)")


@dataclass
class Parrafo:
    texto: str  # renglones unidos, sin la marca
    pagina: int | None
    pagina_fin: int | None
    marca: str | None = None
    tipo_marca: str | None = None
    renglones: list[str] = field(default_factory=list)  # como venían, con la marca
    paginas: list[int | None] = field(default_factory=list)  # la de cada renglón
    # por renglón: dónde empieza dentro de `texto` y dentro de `original`
    inicios: list[tuple[int, int]] = field(default_factory=list)

    @cached_property
    def original(self) -> str:
        return "\n".join(self.renglones)

    @cached_property
    def _arranques(self) -> list[int]:
        return [t for t, _ in self.inicios]

    def fragmento(self, inicio: int, fin: int) -> tuple[str, int | None, int | None]:
        """Para `texto[inicio:fin]` (una oración): el pedazo de `original` de donde
        salió (con la marca si es la primera, sus saltos de renglón y sus guiones de
        corte) y las páginas donde empieza y termina."""
        a = bisect_right(self._arranques, inicio) - 1
        b = bisect_right(self._arranques, fin - 1) - 1
        desde = 0 if inicio == 0 else self.inicios[a][1] + inicio - self.inicios[a][0]
        hasta = self.inicios[b][1] + fin - self.inicios[b][0]
        return self.original[desde:hasta], self.paginas[a], self.paginas[b]


@dataclass
class Limpieza:
    parrafos: list[Parrafo]
    advertencias: list[str]


def normalizar_caracteres(texto: str) -> str:
    """NFKC (ligaduras como «fi» en un solo carácter, espacios duros), sin guiones suaves ni caracteres de
    formato; los de control se vuelven espacio. Conserva los de uso privado: así
    se extraen las viñetas de Word."""
    # Guion suave al final del renglón: así marcan algunos PDF el corte de palabra («autenti\u00ad / cación»)
    texto = _GUION_SUAVE_FINAL.sub("-", texto)
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
    # «RF-01» solo en su renglón es la celda de una tabla, no un pie; y con los dígitos
    # como comodín, «RF-01 Registro de usuarios» y «RF-02 Registro de usuarios» al inicio
    # de dos páginas parecerían el mismo encabezado: un identificador nunca lo es.
    marca, tipo, resto = detectar_marca(renglon)
    return not (marca and (not resto or tipo == "id"))


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
    quitados: Counter[str] = Counter()  # páginas, no renglones: encabezado y pie pueden ser el mismo texto
    for renglones in paginas:
        quitar = set()
        for i in _bordes(renglones):
            clave = _clave_repeticion(renglones[i])
            if clave in repetidos and _puede_ser_encabezado(renglones[i]):
                quitar.add(i)
                ejemplos.setdefault(clave, renglones[i])
        quitados.update({_clave_repeticion(renglones[i]) for i in quitar})
        renglones[:] = [r for i, r in enumerate(renglones) if i not in quitar]
    return [f"Encabezado o pie de página quitado ({quitados[c]} de {total} páginas): «{ejemplos[c]}»."
            for c in ejemplos]


def _empieza_en_mayuscula(renglon: str) -> bool:
    primero = renglon.lstrip("¿¡\"'«“(")[:1]
    return primero.isupper() or primero.isdigit()


def _termina_en_enlace(renglon: str) -> bool:
    palabras = normalizar(renglon[-40:]).split()
    return bool(palabras) and palabras[-1] in _PALABRAS_DE_ENLACE


def _queda_abierto(renglon: str) -> bool:
    """El renglón no puede cerrar un párrafo: termina en coma, guion o palabra de enlace."""
    return renglon.endswith((",", "-", "/")) or _termina_en_enlace(renglon)


def _numero_que_sigue(previo: str, tipo: str | None, resto: str) -> bool:
    """La «marca» es un número dentro de la oración: tras palabra de enlace («un máximo
    de / 2.5 segundos», «lo indica el / RF-01») o, si es jerárquico, ante minúscula
    («la versión / 2.1 o superior»). «1.» «2)» siempre abren: son listas, también en
    minúscula y tras «…, y»."""
    if tipo not in ("jerarquica", "id"):
        return False
    return _termina_en_enlace(previo) or (tipo == "jerarquica" and resto[:1].islower())


def _abre_oracion(renglon: str) -> bool:
    primera = renglon.split(" ", 1)[0].lstrip("¿¡\"'«“(")
    return primera[:1].isupper() and normalizar(primera).strip(",;:") in _ABREN_ORACION


class _Armado:
    """Párrafo en construcción. Las partes se unen al final y solo se mira la cola:
    un párrafo enorme (texto sin puntos ni renglones vacíos) no debe costar tiempo cuadrático."""

    def __init__(self, renglon: str, pagina: int | None, marca: str | None, tipo: str | None, resto: str):
        self.parrafo = Parrafo(texto="", pagina=pagina, pagina_fin=pagina, marca=marca, tipo_marca=tipo,
                               renglones=[renglon], paginas=[pagina], inicios=[(0, len(renglon) - len(resto))])
        self.partes = [resto] if resto else []
        self.largo = len(resto)
        self.largo_original = len(renglon)

    def cola(self, n: int = 80) -> str:
        salida = ""
        for parte in reversed(self.partes):
            salida = parte[-n:] + salida
            if len(salida) >= n:
                break
        return salida[-n:]

    def titulo_aislado(self) -> bool:
        if len(self.parrafo.renglones) != 1:
            return False
        texto = "".join(self.partes)
        return not tiene_obligacion(texto) and len(texto.split()) <= MAX_PALABRAS_TITULO

    def agregar(self, renglon: str, pagina: int | None) -> None:
        if re.search(r"[^\W\d_]-$", self.cola(2)) and renglon[:1].islower():
            self.partes[-1] = self.partes[-1][:-1]  # «autenti-» + «cación»
            self.largo -= 1
        elif self.largo:
            self.partes.append(" ")
            self.largo += 1
        p = self.parrafo
        p.inicios.append((self.largo, self.largo_original + 1))
        p.renglones.append(renglon)
        p.paginas.append(pagina)
        p.pagina_fin = pagina
        self.partes.append(renglon)
        self.largo += len(renglon)
        self.largo_original += 1 + len(renglon)

    def cerrar(self) -> Parrafo:
        self.parrafo.texto = "".join(self.partes)
        return self.parrafo


def _empieza_parrafo(actual: _Armado | None, previo: str, renglon: str, marca: str | None, tipo: str | None,
                     resto: str, llena: bool, maquetado: bool) -> bool:
    if actual is None:
        return True
    if marca:
        return not (_numero_que_sigue(previo, tipo, resto) and not termina_oracion(actual.cola()))
    if not actual.largo:  # la marca venía sola en su renglón (celda de tabla): el texto sigue
        return False
    if not _empieza_en_mayuscula(renglon) or _queda_abierto(previo):
        return False
    if termina_oracion(previo) or _abre_oracion(renglon):
        return True
    # Sin punto final: en un PDF los renglones se cortan por ancho, así que uno
    # corto cierra el párrafo (título o párrafo sin punto) y uno lleno sigue.
    # En texto plano no hay ancho de referencia: solo cierra un título aislado.
    return not llena if maquetado else actual.titulo_aislado()


def reconstruir(renglones: list[tuple[str, int | None]], maquetado: bool) -> list[Parrafo]:
    """Une renglones en párrafos. Un renglón vacío siempre cierra el párrafo; una
    marca de numeración abre uno nuevo (salvo un número que sigue la oración)."""
    largos = sorted(len(r) for r, _ in renglones if r)
    ancho = largos[math.ceil(0.9 * (len(largos) - 1))] if largos else 0  # percentil 90: ignora renglones atípicos
    armados: list[_Armado] = []
    actual: _Armado | None = None
    previo = ""
    for renglon, pagina in renglones:
        if not renglon:
            actual, previo = None, ""
            continue
        marca, tipo, resto = detectar_marca(renglon)
        llena = len(previo) >= FRACCION_LINEA_LLENA * ancho
        if _empieza_parrafo(actual, previo, renglon, marca, tipo, resto, llena, maquetado):
            actual = _Armado(renglon, pagina, marca, tipo, resto if marca else renglon)
            armados.append(actual)
        else:
            actual.agregar(renglon, pagina)
        previo = renglon
    return [a.cerrar() for a in armados]


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
