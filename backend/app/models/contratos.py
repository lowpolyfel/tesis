"""Contratos de entrada y salida de cada agente (ADR 0001).

Ningún agente devuelve texto libre: la salida del LLM se valida contra estos
modelos. Los modelos `*LLM` son lo que se le pide al modelo de lenguaje; el
resto lo completa el código de forma determinista.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from .comunes import Categoria, CategoriaNoFuncional, DecisionFiltro, Regla, TipoAmbiguedad, TipoRequisito, Via


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
    origen: Literal["extractor", "regional", "alcance", "anafora"]
    detalle: str | None = None  # por qué es candidato (catálogo, antecedentes posibles, patrón de alcance)


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


NOTA_UNA_INTERPRETACION = "el Clasificador dio una sola interpretación: en este requisito y su contexto es unívoco"


class ResultadoTermino(Contrato):
    termino: str = Field(min_length=1)
    univoco: bool = False
    tipo_ambiguedad: TipoAmbiguedad | None = None
    interpretaciones: list[Interpretacion] = []
    # La escribe el código, no el LLM (no aparece en el esquema que se le pide al modelo)
    nota: SkipJsonSchema[str | None] = None

    @model_validator(mode="before")
    @classmethod
    def _una_sola_es_univoca(cls, datos: Any) -> Any:
        """Una sola interpretación es, por definición, un término unívoco: no hay otra con
        qué compararla (ADR 0017). Con el contexto del proyecto el Clasificador a veces deja
        una y no marca `univoco`; en lugar de rechazarlo, se registra como unívoco con una nota."""
        if isinstance(datos, dict) and len(datos.get("interpretaciones") or []) == 1:
            return {**datos, "univoco": True, "tipo_ambiguedad": None, "interpretaciones": [],
                    "nota": NOTA_UNA_INTERPRETACION}
        return datos

    @model_validator(mode="after")
    def _coherencia(self) -> "ResultadoTermino":
        if self.univoco and (self.interpretaciones or self.tipo_ambiguedad):
            raise ValueError(f"'{self.termino}': un término unívoco no lleva interpretaciones ni tipo_ambiguedad")
        if not self.univoco and len(self.interpretaciones) < 2:
            raise ValueError(f"'{self.termino}': si no es unívoco necesita 2 o más interpretaciones")
        if not self.univoco and self.tipo_ambiguedad is None:
            raise ValueError(f"'{self.termino}': si no es unívoco necesita tipo_ambiguedad "
                             f"({', '.join(t.value for t in TipoAmbiguedad)})")
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
    """Entrada del LEL de un término con ambigüedad léxica (ADR 0010)."""

    entrada_lel: EntradaLEL


class Meta(Contrato):
    """Elemento del modelo de metas estratégicas (KMoS-SSA), con tipos al estilo i*.

    `meta_blanda` es una cualidad sin criterio exacto: es el destino natural de
    las expresiones vagas del catálogo («rápido», «ahorita»), que no se debaten.
    """

    id: str = Field(pattern=r"^M\d+$")
    enunciado: str = Field(min_length=1)
    tipo: Literal["meta", "meta_blanda", "tarea", "recurso"]
    actor: str | None = None
    simbolos: list[str] = []
    contribuye_a: str | None = None


class SalidaModeladorRequisito(Contrato):
    """Formalización de un requisito validado: reescrito completo y sin ambigüedad,
    su tipo (funcional o no funcional) y sus metas.

    `supuestos` registra lo que el Modelador concretó a partir del contexto del
    proyecto y no del texto (p. ej. «ahorita» → «en menos de 5 segundos»): queda a
    la vista para que una persona lo confirme o lo corrija (ADR 0017)."""

    requisito_reescrito: str = Field(min_length=1)
    tipo_requisito: TipoRequisito
    categoria: CategoriaNoFuncional | None = None
    supuestos: list[str] = Field(default=[], max_length=6)
    metas: list[Meta] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def _referencias(self) -> "SalidaModeladorRequisito":
        if self.tipo_requisito == TipoRequisito.FUNCIONAL:
            self.categoria = None  # la categoría solo describe a los no funcionales
        self.supuestos = [x for x in (s.strip() for s in self.supuestos) if x]
        ids = [m.id for m in self.metas]
        if len(ids) != len(set(ids)):
            raise ValueError(f"ids de meta repetidos: {ids}")
        for m in self.metas:
            if m.contribuye_a is not None and (m.contribuye_a not in ids or m.contribuye_a == m.id):
                raise ValueError(f"{m.id}.contribuye_a debe ser otra meta de la lista {ids}")
        return self


class EntradaLELFormalizada(EntradaLEL):
    """Entrada del LEL ya validada por un humano y guardada como memoria."""

    proyecto_id: str = "P00"
    req_id: str
    termino: str
    via: Via  # cómo llegó el sistema a la interpretación que propuso
    interpretacion: Interpretacion
    editada_por_humano: bool = False
    # qué hizo la persona con la propuesta: aceptarla, elegir otra interpretación o reescribirla.
    # None en las entradas guardadas antes de que existiera el campo.
    cambio: Literal["ninguno", "eleccion", "edicion"] | None = None
    fecha: str
    # fecha de la última corrección manual de la entrada ya formalizada (ADR 0017)
    corregida: str | None = None
