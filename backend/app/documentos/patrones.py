"""Patrones de superficie para separar requisitos: marcas de numeración, verbos de
obligación o capacidad y fin de oración. Solo expresiones regulares: la
separación no usa LLM ni spaCy, para que sea reproducible y explicable (ADR 0009).

Todo lo que compara palabras lo hace sin acentos (`normalizar`).
"""
from __future__ import annotations

import re

from app.nlp import normalizar

# Verbos y perífrasis que convierten una oración en requisito candidato.
# El presente descriptivo («el sistema registra») no entra: se reporta como descartado.
_OBLIGACION = re.compile(
    r"\b(?:deb(?:e|en|era|eran|eria|erian)"
    r"|podr(?:a|an)|pued(?:e|en)"
    r"|permitir(?:a|an)"
    r"|(?:tiene|tienen|tendra|tendran)\s+que"
    r"|(?:ha|han|habra|habran)\s+de"
    r"|se\s+requier(?:e|en)"
    r"|es\s+(?:necesari|obligatori)[oa])\b"
)
# Primera palabra de una oración sin sujeto explícito («Debe registrar…», «Además, podrá…»)
_VERBOS_INICIALES = {"debe", "deben", "debera", "deberan", "deberia", "deberian", "podra", "podran",
                     "puede", "pueden", "permitira", "permitiran", "tiene", "tienen", "tendra", "tendran",
                     "ha", "han", "habra", "habran"}
_ANTES_DEL_VERBO = {"ademas", "tambien", "asimismo", "adicionalmente", "igualmente", "y", "e", "o", "u",
                    "pero", "no", "se", "solo", "unicamente", "siempre", "nunca"}

# Marcas al inicio del renglón, en orden de prueba. El grupo `m` es lo que se guarda.
_SEP = r"(?:\s*[:.)\-–—]+\s*|\s+|$)"
_MARCAS: list[tuple[str, re.Pattern]] = [
    # RF-01:  RF01  RNF-3  R1.  REQ-12  [RF-02]  CU-4  HU-7
    ("id", re.compile(r"[\[(]?(?P<m>(?:R[A-Z]{0,3}|CU|HU|US|N?FR)[-_]?\d+(?:\.\d+)*)[\])]?" + _SEP)),
    # 3.2  3.2.1  3.2.1.
    ("jerarquica", re.compile(r"(?P<m>\d{1,3}(?:\.\d{1,3})+)\.?(?:\s*[:)\-–—]\s*|\s+|$)")),
    # 1.  1)  1.-  1-   (sin espacio solo ante letra: «1.El», no «10-15»)
    ("numero", re.compile(r"(?P<m>\d{1,3})(?:\.-|[.)]|\s*[-–])(?:\s+|(?=[^\W\d_]))")),
    # a)
    ("letra", re.compile(r"(?P<m>[a-z])\)\s+")),
    # viñetas: las ASCII piden espacio («-5 grados» no es viñeta); las de Word suelen
    # extraerse pegadas al texto o como caracteres de uso privado (U+F0B7…)
    ("vineta", re.compile(r"(?P<m>[-*–—](?=\s)|[•·▪■●◦‣])\s*|(?P<pua>[\ue000-\uf8ff])\s*")),
]
TIPOS_DE_LISTA = {"vineta", "numero", "letra"}

_FIN_ORACION = re.compile(r"[.!?…]+[\"'»”)\]]*\s+")
_TERMINA_ORACION = re.compile(r"[.!?…:;][\"'»”)\]]*$")
_ABREVIATURAS = {"p", "pp", "ej", "pag", "num", "no", "art", "fig", "sr", "sra", "srta", "dr", "dra", "lic",
                 "ing", "mtro", "mtra", "aprox", "max", "min", "vs", "cf", "av", "tel", "ext", "depto", "dpto",
                 "cia", "obs", "op", "cap", "sec", "vol", "ed"}
_RARO = re.compile(r"[\ufffd\ue000-\uf8ff]")
_NUMERO = re.compile(r"\d+(?:\.\d+)*")  # 5, 2026, 2.1, 3.2.1
_COLA = 80  # caracteres que bastan para ver el final de un párrafo o la palabra antes de un punto


def detectar_marca(linea: str) -> tuple[str | None, str | None, str]:
    """(marca, tipo de marca, resto del renglón). Sin marca: (None, None, renglón)."""
    for tipo, patron in _MARCAS:
        m = patron.match(linea)
        if m:
            marca = m.group("m") if m.group("m") is not None else "•"
            return marca, tipo, linea[m.end():].strip()
    return None, None, linea


def tiene_obligacion(texto: str) -> bool:
    return bool(_OBLIGACION.search(normalizar(texto)))


def empieza_con_verbo(texto: str) -> bool:
    """La oración empieza (tras conectores como «además» o «se») con el verbo de obligación."""
    for palabra in re.findall(r"[a-z]+", normalizar(texto[:120])[:80]):
        if palabra not in _ANTES_DEL_VERBO:
            return palabra in _VERBOS_INICIALES
    return False


def termina_oracion(texto: str) -> bool:
    """Cierra con . ! ? … : o ; (también antes de comillas o paréntesis de cierre).
    Solo mira la cola: se llama con párrafos que pueden ser muy largos."""
    return bool(_TERMINA_ORACION.search(texto[-_COLA:].rstrip()))


def tiene_letras(texto: str) -> bool:
    return any(c.isalpha() for c in texto)


def tiene_caracteres_raros(texto: str) -> bool:
    """Caracteres que delatan una fuente del PDF sin mapa a Unicode."""
    return bool(_RARO.search(texto))


def _es_abreviatura(previo: str, siguiente: str, completo: bool) -> bool:
    """El punto al final de `previo` no cierra la oración. `previo` es solo la cola
    del texto (acota el costo); `completo` dice si empieza donde empieza la oración."""
    tokens = previo.split()
    token = (tokens or [""])[-1].lstrip("([«\"'¿¡")
    clave = normalizar(token)
    if _NUMERO.fullmatch(clave):
        # «1. Ingresar» o «Los pasos son: 1. Ingresar» numeran; «… de 5. El sistema» cierra la oración
        return (len(tokens) == 1 and completo) or (len(tokens) > 1 and tokens[-2].endswith((":", ";")))
    if clave == "no":  # «No. 5» es «número»; «… si acepta o no. El sistema» cierra la oración
        return siguiente.isdigit()
    return clave in _ABREVIATURAS or "." in clave or (len(clave) == 1 and clave.isalpha())


def posiciones_de_oraciones(texto: str) -> list[tuple[int, int]]:
    """(inicio, fin) de cada oración en `texto`, sin los espacios de los bordes.
    Parte por . ! ? seguidos de mayúscula, dígito o signo de apertura. No parte tras
    abreviaturas («p. ej.», «Sr.»), iniciales, siglas con punto ni números que
    numeran («1. Ingresar»): es preferible una oración larga a dos mitades sin sentido."""
    cortes, inicio = [], 0
    for m in _FIN_ORACION.finditer(texto):
        siguiente = texto[m.end():m.end() + 1]
        if not siguiente or not (siguiente.isupper() or siguiente.isdigit() or siguiente in "¿¡\"«“("):
            continue
        desde = max(inicio, m.start() - _COLA)
        if texto[m.start()] == "." and _es_abreviatura(texto[desde:m.start()], siguiente, desde == inicio):
            continue
        cortes.append((inicio, m.end()))
        inicio = m.end()
    cortes.append((inicio, len(texto)))
    salida = []
    for a, b in cortes:
        while a < b and texto[a].isspace():
            a += 1
        while b > a and texto[b - 1].isspace():
            b -= 1
        if a < b:
            salida.append((a, b))
    return salida


def dividir_oraciones(texto: str) -> list[str]:
    return [texto[a:b] for a, b in posiciones_de_oraciones(texto)]
