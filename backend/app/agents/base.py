"""Utilidades comunes de los agentes."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def a_json(datos: Any) -> str:
    """Serializa modelos o listas de modelos para insertarlos en un prompt."""
    if isinstance(datos, BaseModel):
        datos = datos.model_dump(mode="json")
    elif isinstance(datos, list):
        datos = [d.model_dump(mode="json") if isinstance(d, BaseModel) else d for d in datos]
    return json.dumps(datos, ensure_ascii=False, indent=2)


SIN_CONTEXTO = "(el proyecto no tiene contexto general)"


def texto_contexto(contexto: str | None) -> str:
    """El contexto general del proyecto como va en los prompts (ADR 0017)."""
    return (contexto or "").strip() or SIN_CONTEXTO
