"""Dobles deterministas para probar sin Ollama: LLM falso y embeddings falsos."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Callable


class LLMFalso:
    """Responde por versión de prompt. Cada guion es una lista (se consume en orden)
    o una función `prompt -> dict|str`. Registra todas las llamadas."""

    def __init__(self, guiones: dict[str, list | Callable], modelo: str = "llm-falso"):
        self.modelo = modelo
        self.guiones = {k: (list(v) if isinstance(v, list) else v) for k, v in guiones.items()}
        self.llamadas: dict[str, list] = defaultdict(list)

    def completar(self, prompt, esquema) -> str:
        self.llamadas[prompt.version].append(prompt)
        guion = self.guiones[prompt.version]
        r = guion(prompt) if callable(guion) else guion.pop(0)
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


class EmbeddingsFalsos:
    """Vector fijo por paráfrasis; lo no declarado cae en un vector por defecto."""

    modelo = "embeddings-falsos"

    def __init__(self, tabla: dict[str, list[float]], defecto: list[float] | None = None):
        self.tabla = tabla
        self.defecto = defecto or [1.0, 0.0, 0.0]

    def vectorizar(self, textos):
        return [self.tabla.get(t, self.defecto) for t in textos]


def interp(id_, significado, parafrasis):
    return {"id": id_, "significado": significado, "parafrasis_del_requisito": parafrasis}


def r3_todas(cumple=True):
    """Guion para critico_v1: evalúa R3 de todas las interpretaciones del prompt."""
    import re

    def responder(prompt):
        ids = sorted(set(re.findall(r'"id": "(I\d+)"', prompt.usuario.split("LEL acumulado")[0])))
        return {"evaluaciones": [{"interpretacion_id": i, "cumple": cumple, "evidencia": "cita de la paráfrasis",
                                  "objecion": None if cumple else "sigue siendo ambiguo"} for i in ids]}

    return responder
