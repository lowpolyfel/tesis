"""Vistas derivadas de las trazas para el frontend (ADR 0015). Funciones puras, sin LLM."""
from .configuracion import configuracion_vigente, leer_catalogos, rejilla  # noqa: F401
from .proyecto import (  # noqa: F401
    ambiguedades_proyecto,
    flujo_proyecto,
    resumen_proyecto,
)
from .requisito import analizar, resumen_requisito, vista_requisito  # noqa: F401
from .traza import mensajes_efectivos, normalizar_config  # noqa: F401
