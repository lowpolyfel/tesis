"""Configuración vigente y catálogos, de solo lectura, para el frontend (ADR 0015)."""
from __future__ import annotations

import json
from pathlib import Path

from app.calibracion import rejilla
from app.config import Settings

from .traza import normalizar_config

NOTA_CONFIGURACION = "se cambia en .env; cada traza guarda la suya"
NOTA_CATALOGOS = ("solo lectura: se editan en los JSON del directorio de catálogos; "
                  "la versión usada queda en cada traza")
CATALOGOS = ("regionales", "vaguedad")


class CatalogoInvalido(ValueError):
    """Un archivo de catálogo que no es un objeto JSON."""


def configuracion_vigente(s: Settings, config_traza: dict) -> dict:
    """Lo que copiaría una traza nueva (`Dependencias.config_traza()`), con los nombres
    de la vista, más lo que usan los módulos fuera del grafo. Forma: `formas.Configuracion`::

        {umbral, max_rondas, modelos{extractor, clasificador, critico, modelador},
         modelo_embeddings, temperatura, semilla, significado_max_palabras, spacy_model,
         catalogos, persistencia, otros, proveedor_critico,
         modelos_auxiliares{comparador, agente_unico},
         calibracion{desde, hasta, paso, umbrales}, comparacion{relacion_umbral,
         duplicado_umbral, max_pares}, nota}

    `calibracion.umbrales` es la rejilla de `app.calibracion` con los valores de `.env`.
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


def _leer(ruta: Path) -> dict | None:
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise CatalogoInvalido(f"{ruta.name} no es JSON válido: {e}") from e
    if not isinstance(datos, dict):
        raise CatalogoInvalido(f"{ruta.name} debe ser un objeto JSON, no {type(datos).__name__}")
    return datos


def leer_catalogos(directorio: Path) -> dict:
    """Los catálogos tal cual están en disco. Forma: `formas.Catalogos`::

        {regionales: {...} | null, vaguedad: {...} | null,
         versiones: {regionales, vaguedad}, nota}

    Lanza `CatalogoInvalido` si un archivo existe pero no es un objeto JSON.
    """
    salida: dict = {n: _leer(Path(directorio) / f"{n}.json") for n in CATALOGOS}
    salida["versiones"] = {n: (salida[n] or {}).get("version") for n in CATALOGOS}
    salida["nota"] = NOTA_CATALOGOS
    return salida
