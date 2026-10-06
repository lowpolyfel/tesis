"""Contratos de entrada y salida de cada agente (ADR 0001).

Ningún agente devuelve texto libre: la salida del LLM se valida contra estos
modelos. Los modelos `*LLM` son lo que se le pide al modelo de lenguaje; el
resto lo completa el código de forma determinista.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from .comunes import Categoria, DecisionFiltro, Regla, Via


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------- LEL

class EntradaLEL(Contrato):
    """Entrada del Léxico Extendido del Lenguaje (Leite)."""

    simbolo: str = Field(min_length=1)
    tipo: Categoria
    nocion: list[str] = Field(min_length=1)
    impacto: list[str] = Field(min_length=1)


# ---------------------------------------------------------------- Extractor

class Posicion(Contrato):
    inicio: int = Field(ge=0)
    fin: int

    @model_validator(mode="after")
    def _orden(self) -> "Posicion":
        if self.fin <= self.inicio:
            raise ValueError("fin debe ser mayor que inicio")
        return self


class EntradaExtractor(Contrato):
    texto: str = Field(min_length=1)


class TerminoExtraidoLLM(Contrato):
    """Lo que devuelve el LLM: la posición la calcula el código (ADR 0001)."""

    termino: str = Field(min_length=1)
    categoria_tentativa: Categoria


class SalidaExtractorLLM(Contrato):
    terminos: list[TerminoExtraidoLLM]


class TerminoExtraido(Contrato):
    termino: str = Field(min_length=1)
    posicion: Posicion
    categoria_tentativa: Categoria


class SalidaExtractor(Contrato):
    terminos: list[TerminoExtraido]


# ---------------------------------------------------------------- Filtros

class TerminoFiltrado(TerminoExtraido):
    decision_filtro: DecisionFiltro
    detalle: str | None = None


# ---------------------------------------------------------------- Clasificador

class TerminoCandidato(Contrato):
    termino: str = Field(min_length=1)
    categoria_tentativa: Categoria
    origen: Literal["extractor", "regional"]


class EntradaClasificador(Contrato):
    texto: str = Field(min_length=1)
    terminos: list[TerminoCandidato]
    lel_actual: list[EntradaLEL] = []


class Interpretacion(Contrato):
    """Una interpretación candidata de un término ambiguo.

    `significado` es el sentido que esta interpretación le da al término; su
    longitud máxima viene de la configuración (SIGNIFICADO_MAX_PALABRAS) y se
    pasa como contexto de validación.
    """

    id: str = Field(pattern=r"^I\d+$")
    significado: str = Field(min_length=1)
    parafrasis_del_requisito: str = Field(min_length=1)

    @field_validator("significado")
    @classmethod
    def _limite_palabras(cls, v: str, info: ValidationInfo) -> str:
        limite = (info.context or {}).get("significado_max_palabras")
        if limite is not None and len(v.split()) > limite:
            raise ValueError(f"significado tiene {len(v.split())} palabras; el máximo es {limite}")
        return v


def _ids_unicos(interpretaciones: list[Interpretacion]) -> None:
    ids = [i.id for i in interpretaciones]
    if len(ids) != len(set(ids)):
        raise ValueError(f"ids de interpretación repetidos: {ids}")


class ResultadoTermino(Contrato):
    termino: str = Field(min_length=1)
    univoco: bool = False
    interpretaciones: list[Interpretacion] = []

    @model_validator(mode="after")
    def _coherencia(self) -> "ResultadoTermino":
        if self.univoco and self.interpretaciones:
            raise ValueError(f"'{self.termino}': un término unívoco no lleva interpretaciones")
        if not self.univoco and len(self.interpretaciones) < 2:
            raise ValueError(f"'{self.termino}': si no es unívoco necesita 2 o más interpretaciones")
        _ids_unicos(self.interpretaciones)
        return self


class SalidaClasificador(Contrato):
    resultados: list[ResultadoTermino]


# Refinamiento (el Clasificador responde a las objeciones del Crítico)

class Objecion(Contrato):
    interpretacion_id: str
    regla: Regla
    texto: str = Field(min_length=1)


class EntradaRefinamiento(Contrato):
    texto: str
    termino: str
    interpretaciones: list[Interpretacion]
    objeciones: list[Objecion]


class Retiro(Contrato):
    interpretacion_id: str
    motivo: str = Field(min_length=1)


class SalidaRefinamiento(Contrato):
    interpretaciones: list[Interpretacion] = Field(min_length=1)
    retiradas: list[Retiro] = []

    @model_validator(mode="after")
    def _sin_repetidos(self) -> "SalidaRefinamiento":
        _ids_unicos(self.interpretaciones)
        vivas = {i.id for i in self.interpretaciones}
        for r in self.retiradas:
            if r.interpretacion_id in vivas:
                raise ValueError(f"{r.interpretacion_id} aparece como retirada y como vigente")
        return self


# ---------------------------------------------------------------- Crítico

class ResultadoRegla(Contrato):
    regla: Regla
    cumple: bool
    evidencia: str
    detalle: dict = {}


class EvaluacionInterpretacion(Contrato):
    interpretacion_id: str
    reglas: list[ResultadoRegla]
    # Versión literal de R1 y R2 (solo requisito + LEL): se registra, no decide (ADR 0004)
    r1_estricta: ResultadoRegla
    r2_estricta: ResultadoRegla

    @model_validator(mode="after")
    def _tres_reglas(self) -> "EvaluacionInterpretacion":
        if sorted(r.regla for r in self.reglas) != [Regla.R1, Regla.R2, Regla.R3]:
            raise ValueError("cada evaluación debe traer exactamente R1, R2 y R3")
        return self


class EntradaCriticoEvaluacion(Contrato):
    texto: str
    termino: str
    interpretaciones: list[Interpretacion]
    lel_actual: list[EntradaLEL] = []


class SalidaCriticoEvaluacion(Contrato):
    evaluaciones: list[EvaluacionInterpretacion]
    objeciones: list[Objecion]


class EvaluacionR3LLM(Contrato):
    interpretacion_id: str
    cumple: bool
    evidencia: str = Field(min_length=1, description="Cita textual de la paráfrasis que sostiene el juicio")
    objecion: str | None = None


class SalidaR3LLM(Contrato):
    """Lo único que juzga el LLM del Crítico en la evaluación: la regla R3."""

    evaluaciones: list[EvaluacionR3LLM]


class RondaDebate(Contrato):
    ronda: int
    interpretaciones: list[Interpretacion]
    objeciones: list[Objecion]
    retiradas: list[Retiro] = []
    similitud: float | None = None


class EntradaArbitraje(Contrato):
    texto: str
    termino: str
    interpretaciones: list[Interpretacion]
    lel_actual: list[EntradaLEL] = []
    historial: list[RondaDebate]


class JustificacionRegla(Contrato):
    regla: Regla
    argumento: str = Field(min_length=1)


class SalidaArbitraje(Contrato):
    interpretacion_elegida: str
    justificacion_por_regla: list[JustificacionRegla]

    @model_validator(mode="after")
    def _tres_reglas(self) -> "SalidaArbitraje":
        if sorted(j.regla for j in self.justificacion_por_regla) != [Regla.R1, Regla.R2, Regla.R3]:
            raise ValueError("la justificación debe cubrir exactamente R1, R2 y R3")
        return self


# ---------------------------------------------------------------- Modelador

class EntradaModelador(Contrato):
    texto: str
    termino: str
    interpretacion_validada: Interpretacion


class SalidaModeladorLLM(Contrato):
    entrada_lel: EntradaLEL


class SalidaModelador(Contrato):
    entrada_lel: EntradaLEL
    metas: dict  # stub en esta fase
    big_picture: dict  # stub en esta fase


class EntradaLELFormalizada(EntradaLEL):
    """Entrada del LEL ya validada por un humano y guardada como memoria."""

    proyecto_id: str = "P00"
    req_id: str
    termino: str
    via: Via
    interpretacion: Interpretacion
    editada_por_humano: bool = False
    fecha: str
