"""Similitud coseno y decisión del umbral. Funciones puras (ADR 0002).

Este módulo no es un agente: es el mecanismo que decide si hay debate y debe
quedar a la vista. No llama a ningún modelo; recibe vectores ya calculados.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

import numpy as np

from app.models import Estado


def coseno(a: Sequence[float], b: Sequence[float]) -> float:
    """cos(a, b) = (a · b) / (‖a‖ ‖b‖), calculado a mano con numpy."""
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    if va.shape != vb.shape or va.ndim != 1:
        raise ValueError(f"los vectores deben tener la misma dimensión: {va.shape} vs {vb.shape}")
    na = float(np.sqrt(np.sum(va * va)))
    nb = float(np.sqrt(np.sum(vb * vb)))
    if na == 0.0 or nb == 0.0:
        raise ValueError("la similitud coseno no está definida para un vector nulo")
    return float(np.sum(va * vb) / (na * nb))


@dataclass(frozen=True)
class SimilitudMinima:
    """Similitud mínima entre pares, con el par que la produce y la matriz completa."""

    valor: float
    par: tuple[int, int]
    pares: dict[tuple[int, int], float] = field(default_factory=dict)


def similitud_minima_entre_pares(vectores: Sequence[Sequence[float]]) -> SimilitudMinima:
    """Con 2 interpretaciones es su coseno; con más, el mínimo entre todos los pares.

    El mínimo representa el peor desacuerdo: basta un par divergente para que el
    término no pueda aceptarse sin debate.
    """
    if len(vectores) < 2:
        raise ValueError("se necesitan al menos dos interpretaciones para comparar")
    pares = {(i, j): coseno(vectores[i], vectores[j]) for i, j in combinations(range(len(vectores)), 2)}
    par = min(pares, key=pares.get)
    return SimilitudMinima(valor=pares[par], par=par, pares=pares)


def decidir(similitud: float, umbral: float) -> Estado:
    """similitud >= umbral → aceptado_directo; si no → en_debate."""
    return Estado.ACEPTADO_DIRECTO if similitud >= umbral else Estado.EN_DEBATE
