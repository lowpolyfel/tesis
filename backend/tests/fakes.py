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


# ---------------------------------------------------------------- cuentas

def _usuario_prueba():
    from app.auth import Usuario

    # U00: los ids que asigna el repositorio empiezan en U01, así no choca con una cuenta real
    return Usuario(usuario_id="U00", nombre="Prueba", correo="prueba@ejemplo.mx", contrasena="-", verificado=True)


USUARIO_PRUEBA = _usuario_prueba()


def como_usuario(app, usuario=USUARIO_PRUEBA):
    """La app responde como si `usuario` tuviera sesión (sin cookie). Los proyectos que las
    pruebas crean con el servicio quedan a su nombre (`conftest.py`). Las pruebas de
    cuentas (`tests/auth`) no lo usan: prueban la sesión de verdad."""
    from app.api.dependencias import usuario_actual

    app.dependency_overrides[usuario_actual] = lambda: usuario
    return app


class CorreoFalso:
    """Guarda los códigos en vez de enviarlos: `ultimo(correo)` da el último de esa dirección."""

    configurado = True

    def __init__(self):
        self.enviados: list[dict] = []

    def enviar_codigo(self, destino, nombre, codigo, proposito, minutos):
        self.enviados.append({"destino": destino, "codigo": codigo, "proposito": proposito})

    def ultimo(self, destino: str) -> str:
        return next(e["codigo"] for e in reversed(self.enviados) if e["destino"] == destino)
