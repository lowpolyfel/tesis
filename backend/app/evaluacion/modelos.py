"""Documento de una evaluación en la colección `evaluaciones` (ADR 0014)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import TipoAmbiguedad, ahora

from .agente_unico import EntradaLineaBase
from .corpus import RequisitoGT

COLECCION = "evaluaciones"
PREFIJO = "E"

EstadoEvaluacion = Literal["en_proceso", "terminada"]


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Etiqueta(Modelo):
    """Contrato fijo con la calibración (ADR 0013): qué término de qué requisito es ambiguo
    según el ground truth."""

    req_id: str
    termino: str
    ambiguo: bool
    tipo_ambiguedad: TipoAmbiguedad | None = None


class ItemEvaluacion(Modelo):
    id_corpus: str
    req_id: str


class Evaluacion(Modelo):
    evaluacion_id: str = Field(pattern=r"^E\d+$")
    nombre: str = Field(min_length=1)
    proyecto_id: str
    corpus: str
    ejemplo: bool = False
    huella: str  # del corpus al crearla: dice si el corpus cambió después
    creado: datetime = Field(default_factory=ahora)
    terminado: datetime | None = None
    estado: EstadoEvaluacion = "en_proceso"
    config: dict[str, Any]
    # Copia del ground truth al crearla: la evaluación se mide siempre contra el mismo
    ground_truth: list[RequisitoGT]
    items: list[ItemEvaluacion]
    linea_base: dict[str, EntradaLineaBase] = {}  # por id_corpus
    etiquetas: list[Etiqueta] = []
