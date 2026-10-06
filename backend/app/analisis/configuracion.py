"""Configuración vigente y catálogos, de solo lectura, para el frontend (ADR 0015)."""
from __future__ import annotations

import json
import math
from pathlib import Path

from app.config import Settings

from .traza import normalizar_config

NOTA_CONFIGURACION = "se cambia en .env; cada traza guarda la suya"
NOTA_CATALOGOS = ("solo lectura: se editan en los JSON del directorio de catálogos; "
                  "la versión usada queda en cada traza")


def rejilla(desde: float, hasta: float, paso: float) -> list[float]:
    """Umbrales de la calibración, de `desde` a `hasta` inclusive."""
    if hasta < desde:
        return []
    n = math.floor((hasta - desde) / paso + 1e-9)
    return [round(desde + i * paso, 6) for i in range(n + 1)]


def configuracion_vigente(s: Settings, config_traza: dict) -> dict:
    """Lo que copiaría una traza nueva (`Dependencias.config_traza()`), con los nombres
    de la vista, más lo que usan los módulos fuera del grafo. Forma: `formas.Configuracion`::

        {umbral, max_rondas, modelos{extractor, clasificador, critico, modelador},
         modelo_embeddings, temperatura, semilla, significado_max_palabras, spacy_model,
         catalogos, persistencia, otros, proveedor_critico,
         modelos_auxiliares{comparador, agente_unico},
         calibracion{desde, hasta, paso, umbrales}, comparacion{relacion_umbral,
         duplicado_umbral, max_pares}, nota}
    """
    return {
        **normalizar_config(config_traza),
        "proveedor_critico": s.critico_provider,
        "modelos_auxiliares": {"comparador": s.comparador_model, "agente_unico": s.agente_unico_model},
        "calibracion": {"desde": s.calibracion_desde, "hasta": s.calibracion_hasta, "paso": s.calibracion_paso,
                        "umbrales": rejilla(s.calibracion_desde, s.calibracion_hasta, s.calibracion_paso)},
        "comparacion": {"relacion_umbral": s.comparacion_relacion_umbral,
                        "duplicado_umbral": s.comparacion_duplicado_umbral, "max_pares": s.comparacion_max_pares},
        "nota": NOTA_CONFIGURACION,
    }


def leer_catalogos(directorio: Path) -> dict:
    """Los catálogos tal cual están en disco. Forma: `formas.Catalogos`::

        {regionales: {...} | null, vaguedad: {...} | null,
         versiones: {regionales, vaguedad}, nota}
    """
    salida: dict = {}
    for nombre in ("regionales", "vaguedad"):
        ruta = Path(directorio) / f"{nombre}.json"
        salida[nombre] = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
    salida["versiones"] = {n: (salida[n] or {}).get("version") for n in ("regionales", "vaguedad")}
    salida["nota"] = NOTA_CATALOGOS
    return salida
