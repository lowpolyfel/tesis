"""Comparación entre requisitos de un mismo proyecto (módulo exploratorio, ADR 0012).

Fuera del núcleo: no toca el grafo ni el debate. Busca contradicciones,
redundancias, casi duplicados e inconsistencias de vocabulario entre requisitos.
"""
from .bases import SignificadoValidado, bases_de_comparacion, significados_validados  # noqa: F401
from .ejecucion import (  # noqa: F401
    COLECCION,
    RequisitosInsuficientes,
    comparar,
    ejecutar,
    listar,
    obtener,
    preparar,
    recuperar,
    resumen,
    solicitar,
)
from .juez import PROMPT, Juez, cita_literal  # noqa: F401
from .modelos import Comparacion, ResumenComparacion, SalidaComparadorLLM  # noqa: F401
from .pares import Perfil, casi_duplicados, matriz_similitud, perfil, seleccionar_pares  # noqa: F401
from .vocabulario import inconsistencias_vocabulario  # noqa: F401
