"""Selección de los pares que pasan al juez LLM y casi duplicados.

La similitud es el coseno entre los embeddings de los textos base, calculado a
mano (`app.divergence.similitud.coseno`). Un par es candidato si su similitud
alcanza `comparacion_relacion_umbral` o si comparten un símbolo del LEL o un lema
de contenido. Los candidatos se ordenan por similitud descendente y se cortan en
`comparacion_max_pares`; los que quedan fuera se reportan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

from app.divergence.similitud import coseno
from app.nlp import Analizador, normalizar


def clave_par(a: str, b: str) -> str:
    return f"{a}-{b}"


def matriz_similitud(ids: list[str], vectores: Sequence[Sequence[float]]) -> dict[str, float]:
    """{"R01-R02": coseno} para todos los pares, en el orden de `ids`."""
    if len(vectores) != len(ids):
        raise ValueError(f"se esperaban {len(ids)} vectores y llegaron {len(vectores)}")
    return {clave_par(ids[i], ids[j]): coseno(vectores[i], vectores[j]) for i, j in combinations(range(len(ids)), 2)}


@dataclass(frozen=True)
class Perfil:
    """Términos de un texto base: {clave normalizada: como aparece}."""

    lemas: dict[str, str] = field(default_factory=dict)
    simbolos: dict[str, str] = field(default_factory=dict)


def _secuencias(analizador: Analizador, texto: str) -> tuple[list[str], list[str]]:
    tokens = [t for t in analizador.doc(texto) if not (t.is_punct or t.is_space)]
    return [normalizar(t.text) for t in tokens], [normalizar(t.lemma_) for t in tokens]


def _contiene(secuencia: list[str], sub: list[str]) -> bool:
    n = len(sub)
    return n > 0 and any(secuencia[i:i + n] == sub for i in range(len(secuencia) - n + 1))


SimboloAnalizado = tuple[str, list[str], list[str]]  # (símbolo, formas, lemas)


def analizar_simbolos(analizador: Analizador, simbolos_lel: list[str]) -> list[SimboloAnalizado]:
    """Una sola pasada de spaCy por símbolo, para reusarla en todos los requisitos."""
    return [(s, *_secuencias(analizador, s)) for s in simbolos_lel]


def perfil(analizador: Analizador, texto: str, simbolos_lel: list[str] | list[SimboloAnalizado]) -> Perfil:
    """Lemas de contenido y símbolos del LEL que aparecen en el texto (por forma o por
    secuencia de lemas, para que «da de alta» encuentre «dar de alta»)."""
    lemas = {k: u.texto for k, u in analizador.lemas_contenido(texto).items()}
    formas, lemas_texto = _secuencias(analizador, texto)
    analizados = [s if isinstance(s, tuple) else (s, *_secuencias(analizador, s)) for s in simbolos_lel]
    simbolos = {}
    for s, f, lm in analizados:
        if _contiene(formas, f) or _contiene(lemas_texto, lm) or (len(f) == 1 and f[0] in lemas_texto):
            simbolos[" ".join(f)] = s
    return Perfil(lemas, simbolos)


def compartidos(a: Perfil, b: Perfil) -> tuple[list[str], list[str]]:
    """(símbolos del LEL, lemas de contenido) que aparecen en los dos, como aparecen en `a`."""
    simbolos = sorted((a.simbolos[k] for k in a.simbolos.keys() & b.simbolos.keys()), key=normalizar)
    lemas = sorted((a.lemas[k] for k in a.lemas.keys() & b.lemas.keys()), key=normalizar)
    return simbolos, lemas


@dataclass(frozen=True)
class Par:
    a: str
    b: str
    similitud: float
    motivos: tuple[str, ...]
    compartidos: tuple[str, ...]

    @property
    def clave(self) -> str:
        return clave_par(self.a, self.b)


@dataclass(frozen=True)
class Seleccion:
    evaluar: list[Par]
    fuera: list[Par]

    @property
    def candidatos(self) -> int:
        return len(self.evaluar) + len(self.fuera)


def seleccionar_pares(ids: list[str], matriz: dict[str, float], perfiles: dict[str, Perfil],
                      umbral_relacion: float, max_pares: int) -> Seleccion:
    pares = []
    for a, b in combinations(ids, 2):
        x = matriz[clave_par(a, b)]
        simbolos, lemas = compartidos(perfiles[a], perfiles[b])
        motivos = tuple(m for m, cumple in (("similitud", x >= umbral_relacion), ("simbolo_lel", bool(simbolos)),
                                            ("lema", bool(lemas))) if cumple)
        if motivos:
            pares.append(Par(a, b, x, motivos, tuple(dict.fromkeys(simbolos + lemas))))
    pares.sort(key=lambda p: -p.similitud)  # estable: en empate, el orden de los requisitos
    return Seleccion(pares[:max_pares], pares[max_pares:])


def casi_duplicados(ids: list[str], matriz: dict[str, float], umbral_duplicado: float) -> list[tuple[str, str, float]]:
    """Todos los pares con coseno >= umbral, sin importar el corte de pares del juez."""
    return [(a, b, matriz[clave_par(a, b)]) for a, b in combinations(ids, 2) if matriz[clave_par(a, b)] >= umbral_duplicado]
