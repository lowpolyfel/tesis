"""Calibración del umbral como análisis de sensibilidad (ADR 0013). Funciones puras,
sin LLM ni embeddings: nunca cambian la configuración."""
from .ground_truth import COLECCION_EVALUACIONES, Etiqueta, contrastar, metricas, seleccionar_etiquetas  # noqa: F401
from .informe import NOTA, informe_calibracion  # noqa: F401
from .sensibilidad import (  # noqa: F401
    distribucion,
    extraer_similitudes,
    puntos_rejilla,
    rejilla,
    reprocesados,
    sensibilidad,
)
