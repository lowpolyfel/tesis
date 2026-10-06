"""Contratos de la comparación entre requisitos (ADR 0012).

`SalidaComparadorLLM` es lo único que se le pide al modelo de lenguaje; el resto
lo completa el código. `Comparacion` es el documento que se guarda en la
colección `comparaciones` y que devuelve la API tal cual.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.models import ahora

# Límite de formato del contrato del juez (no se calibra: acota lo que se muestra al humano)
EXPLICACION_MAX_PALABRAS = 60

Relacion = Literal["contradiccion", "redundancia", "complementaria", "independiente"]
TipoHallazgo = Literal["contradiccion", "casi_duplicado", "redundancia", "inconsistencia_vocabulario"]
# llm: juicio del comparador; embeddings: coseno sobre el umbral de duplicado;
# lel: nociones distintas del mismo símbolo; validacion: significados validados distintos
FuenteHallazgo = Literal["llm", "embeddings", "lel", "validacion"]
EstadoComparacion = Literal["en_cola", "en_proceso", "terminada", "error"]
Motivo = Literal["similitud", "simbolo_lel", "lema"]

# Relaciones del juez que se reportan como hallazgo; las otras quedan solo en relaciones_por_par
HALLAZGO_POR_RELACION: dict[str, TipoHallazgo] = {"contradiccion": "contradiccion", "redundancia": "redundancia"}


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- juez LLM

class SalidaComparadorLLM(Contrato):
    relacion: Relacion
    explicacion: str = Field(min_length=1)
    cita_a: str = Field(min_length=1, description="Fragmento copiado literalmente del requisito A")
    cita_b: str = Field(min_length=1, description="Fragmento copiado literalmente del requisito B")

    @field_validator("explicacion", "cita_a", "cita_b")
    @classmethod
    def _sin_espacios(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("no puede estar vacío")
        return v

    @field_validator("explicacion")
    @classmethod
    def _limite_palabras(cls, v: str, info: ValidationInfo) -> str:
        limite = (info.context or {}).get("explicacion_max_palabras", EXPLICACION_MAX_PALABRAS)
        if len(v.split()) > limite:
            raise ValueError(f"explicacion tiene {len(v.split())} palabras; el máximo es {limite}")
        return v


# ---------------------------------------------------------------- documento

class RequisitoBase(Contrato):
    """Texto con el que se compara un requisito y de dónde salió."""

    req_id: str
    base: Literal["reescrito", "original"]
    texto: str = Field(min_length=1)


class Excluido(Contrato):
    req_id: str
    estado: str
    motivo: Literal["error", "rechazado", "reprocesado"]
    detalle: str | None = None  # p. ej. el req_id que lo vuelve a procesar


class ConfigComparacion(Contrato):
    umbral_relacion: float
    umbral_duplicado: float
    max_pares: int
    modelo: str | None
    prompt_version: str
    modelo_embeddings: str | None


class Evidencia(Contrato):
    """`verificada`: la cita aparece literal (normalizada) en su fuente. Las citas del
    LLM se comparan contra el texto base del requisito; las de los hallazgos
    deterministas las copia el código de su fuente y siempre son verdaderas."""

    req_id: str
    cita: str
    verificada: bool


class Hallazgo(Contrato):
    id: str = Field(pattern=r"^H\d+$")
    tipo: TipoHallazgo
    requisitos: list[str] = Field(min_length=2, max_length=2)
    terminos: list[str] = []
    similitud: float | None = None
    explicacion: str
    evidencia: list[Evidencia] = []
    fuente: FuenteHallazgo
    modelo: str | None = None
    prompt_version: str | None = None


class ErrorPar(Contrato):
    excepcion: str
    mensaje: str
    intentos: list[dict] = []  # salidas crudas del LLM si fue un FalloEstructurado


class RelacionPar(Contrato):
    """Un par que se le pasó al juez. Si el LLM falló, `relacion` es null y `error` dice por qué."""

    par: str
    requisitos: list[str] = Field(min_length=2, max_length=2)
    similitud: float
    motivos: list[Motivo]
    compartidos: list[str] = []
    relacion: Relacion | None = None
    explicacion: str | None = None
    error: ErrorPar | None = None

    @model_validator(mode="after")
    def _relacion_o_error(self) -> "RelacionPar":
        if (self.relacion is None) == (self.error is None):
            raise ValueError(f"{self.par}: debe tener relacion o error, no ambos ni ninguno")
        return self


class ParFuera(Contrato):
    """Par candidato que no se evaluó por el límite de pares."""

    par: str
    similitud: float
    motivos: list[Motivo]


class Avance(Contrato):
    hechos: int = 0
    total: int = 0


class ErrorComparacion(Contrato):
    excepcion: str
    mensaje: str


class Comparacion(Contrato):
    comparacion_id: str = Field(pattern=r"^C\d+$")
    proyecto_id: str
    estado: EstadoComparacion = "en_cola"
    creado: datetime = Field(default_factory=ahora)
    terminado: datetime | None = None
    config: ConfigComparacion
    requisitos: list[RequisitoBase] = []
    excluidos: list[Excluido] = []
    pares_totales: int = 0
    pares_candidatos: int = 0
    pares_evaluados: int = 0
    pares_fuera_por_limite: int = 0
    fuera_por_limite: list[ParFuera] = []
    pares_con_error: int = 0
    avance: Avance = Field(default_factory=Avance)
    matriz_similitud: dict[str, float] = {}
    hallazgos: list[Hallazgo] = []
    relaciones_por_par: list[RelacionPar] = []
    error: ErrorComparacion | None = None


class ResumenComparacion(Contrato):
    """Lo que devuelve el listado por proyecto (sin matriz ni hallazgos)."""

    comparacion_id: str
    proyecto_id: str
    estado: EstadoComparacion
    creado: datetime
    terminado: datetime | None
    config: ConfigComparacion
    n_requisitos: int
    pares_evaluados: int
    pares_fuera_por_limite: int
    pares_con_error: int
    hallazgos_por_tipo: dict[str, int]
    error: ErrorComparacion | None
