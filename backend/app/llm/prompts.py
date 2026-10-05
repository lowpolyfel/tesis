"""Prompts versionados en archivos (`app/prompts/<agente>_v<N>.txt`).

Formato de cada archivo: una sección `### SISTEMA` y otra `### USUARIO`. Las
variables se escriben `${nombre}`. La versión registrada en la traza es el
nombre del archivo sin extensión.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template

DIRECTORIO = Path(__file__).resolve().parent.parent / "prompts"
_SECCION = re.compile(r"^###\s*(SISTEMA|USUARIO)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PromptRenderizado:
    version: str
    sistema: str
    usuario: str


@dataclass(frozen=True)
class Prompt:
    version: str
    sistema: str
    usuario: str

    def renderizar(self, **variables) -> PromptRenderizado:
        return PromptRenderizado(
            version=self.version,
            sistema=Template(self.sistema).substitute(**variables) if "$" in self.sistema else self.sistema,
            usuario=Template(self.usuario).substitute(**variables),
        )


@lru_cache
def cargar_prompt(version: str) -> Prompt:
    ruta = DIRECTORIO / f"{version}.txt"
    texto = ruta.read_text(encoding="utf-8")
    partes = _SECCION.split(texto)
    secciones = {partes[i]: partes[i + 1].strip() for i in range(1, len(partes) - 1, 2)}
    if set(secciones) != {"SISTEMA", "USUARIO"}:
        raise ValueError(f"{ruta.name} debe tener las secciones ### SISTEMA y ### USUARIO")
    return Prompt(version=version, sistema=secciones["SISTEMA"], usuario=secciones["USUARIO"])
