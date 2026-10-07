"""Carga de documentos (PDF con texto extraíble o .txt) y separación en requisitos
candidatos que el humano confirma antes de procesarlos (ADR 0009)."""
from .almacen import COLECCION, Documentos
from .extraccion import (
    DemasiadoGrande,
    ErrorDocumento,
    Ilegible,
    SinTexto,
    TipoNoSoportado,
    leer,
)
from .modelos import (
    Documento,
    FragmentoDescartado,
    RequisitoPropuesto,
    ResumenDocumento,
    Separacion,
)
from .separacion import separar_paginas, separar_texto

__all__ = [
    "COLECCION",
    "DemasiadoGrande",
    "Documento",
    "Documentos",
    "ErrorDocumento",
    "FragmentoDescartado",
    "Ilegible",
    "RequisitoPropuesto",
    "ResumenDocumento",
    "Separacion",
    "SinTexto",
    "TipoNoSoportado",
    "leer",
    "separar_paginas",
    "separar_texto",
]
