"""Contratos de la versión 2 (ADR 0024): de la entrevista a los requisitos.

El flujo de un proyecto pasa por cinco fases y una persona valida cada una antes
de pasar a la siguiente:

    entrevista → LEL interactivo → mapa conceptual → metas → requisitos

Como en la versión 1 (ADR 0001), ningún agente devuelve texto libre: los modelos
`Salida*` son lo que se le pide al LLM y el código verifica sus referencias. Los
modelos `*Editable` son lo que guarda el sistema y lo que la persona corrige.

Algunas listas se recortan en lugar de rechazarse (`_recortar`): si el modelo da
31 necesidades donde se piden 30, sobra una, no falla la entrevista completa.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from .comunes import Categoria, CategoriaNoFuncional, TipoAmbiguedad, TipoRequisito
from .contratos import Contrato

# Una cita de la entrevista: «E01:T12» es el turno 12 de la entrevista E01
PATRON_CITA = re.compile(r"^(E\d+):T(\d+)$")

_SINONIMOS_CATEGORIA = {
    "actor": "sujeto", "persona": "sujeto", "rol": "sujeto", "sujeto": "sujeto",
    "objeto": "objeto", "concepto": "objeto", "entidad": "objeto", "cosa": "objeto", "recurso": "objeto",
    "verbo": "verbo", "accion": "verbo", "acción": "verbo", "proceso": "verbo", "actividad": "verbo",
    "estado": "estado", "situacion": "estado", "situación": "estado", "condicion": "estado", "condición": "estado",
}
_SINONIMOS_TIPO_REQUISITO = {"funcional": "funcional", "no funcional": "no_funcional", "no_funcional": "no_funcional",
                             "no-funcional": "no_funcional", "nofuncional": "no_funcional"}


def categoria_flexible(valor: Any) -> Any:
    """«Actor», «Acción», «Sujeto»… al vocabulario del LEL (sujeto, objeto, verbo, estado)."""
    if isinstance(valor, str):
        return _SINONIMOS_CATEGORIA.get(valor.strip().lower(), valor.strip().lower())
    return valor


def normalizar_simple(texto: str) -> str:
    """Minúsculas y sin acentos (como app.nlp.normalizar, sin importar spaCy)."""
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower().strip()


def _recortar(datos: Any, limites: dict[str, int]) -> Any:
    if isinstance(datos, dict):
        datos = dict(datos)
        for campo, n in limites.items():
            if isinstance(datos.get(campo), list):
                datos[campo] = datos[campo][:n]
    return datos


def _sin_vacios(xs: list[str]) -> list[str]:
    return [x for x in (s.strip() for s in xs) if x]


# ================================================================ Revisor: ficha de la entrevista

class ParticipanteEntrevista(Contrato):
    nombre: str = Field(min_length=1, max_length=80)
    rol: str = Field(min_length=1, max_length=240)


class HechoEntrevista(Contrato):
    """Algo que se dijo en la entrevista (un problema, una necesidad, una regla) con los turnos que lo dicen."""

    texto: str = Field(min_length=1, max_length=400)
    turnos: list[int] = Field(default=[], max_length=8)


class SalidaFichaEntrevista(Contrato):
    """Lo que el Revisor saca de una tanda de la entrevista. Las tandas se unen en código."""

    participantes: list[ParticipanteEntrevista] = Field(default=[], max_length=12)
    objetivo: str | None = Field(None, max_length=500)
    problemas: list[HechoEntrevista] = Field(default=[], max_length=20)
    necesidades: list[HechoEntrevista] = Field(default=[], max_length=30)
    reglas: list[HechoEntrevista] = Field(default=[], max_length=20)

    @model_validator(mode="before")
    @classmethod
    def _limites(cls, datos: Any) -> Any:
        return _recortar(datos, {"participantes": 12, "problemas": 20, "necesidades": 30, "reglas": 20})


# ================================================================ Extractor: términos del dominio

class TerminoEntrevistaLLM(Contrato):
    termino: str = Field(min_length=1, max_length=80)
    categoria: Categoria
    turnos: list[int] = Field(default=[], max_length=30)

    @field_validator("categoria", mode="before")
    @classmethod
    def _categoria(cls, v: Any) -> Any:
        return categoria_flexible(v)


class SalidaExtractorEntrevista(Contrato):
    terminos: list[TerminoEntrevistaLLM] = Field(default=[], max_length=60)

    @model_validator(mode="before")
    @classmethod
    def _limites(cls, datos: Any) -> Any:
        return _recortar(datos, {"terminos": 60})


# ================================================================ Clasificador: intenciones

class IntencionCandidata(Contrato):
    """Una interpretación posible de un término en la entrevista (la «intención candidata»).

    - `significado`: a qué se refiere el término con esta interpretación (corto: lo usa la divergencia).
    - `intencion`: qué quiere lograr quien habla cuando usa el término así (el propósito).
    - `parafrasis`: una de las citas reescrita para que solo admita esta interpretación (la compara la
      divergencia y la revisa el Crítico, como la paráfrasis del requisito en la versión 1)."""

    id: str = Field(pattern=r"^I\d+$")
    significado: str = Field(min_length=1)
    intencion: str = Field(min_length=1, max_length=400)
    parafrasis: str = Field(min_length=1, max_length=900)

    @field_validator("significado")
    @classmethod
    def _limite_palabras(cls, v: str, info: ValidationInfo) -> str:
        limite = (info.context or {}).get("significado_max_palabras")
        if limite is not None and len(v.split()) > limite:
            raise ValueError(f"significado tiene {len(v.split())} palabras; el máximo es {limite}")
        return v


class ResultadoIntencion(Contrato):
    """Una sola intención: el término es unívoco en la entrevista. Dos o más: es ambiguo."""

    termino: str = Field(min_length=1)
    tipo_ambiguedad: TipoAmbiguedad | None = None
    intenciones: list[IntencionCandidata] = Field(min_length=1, max_length=4)

    @field_validator("tipo_ambiguedad", mode="before")
    @classmethod
    def _tipo_flexible(cls, v: Any) -> Any:
        """«Léxica» → «lexica»; un tipo que no existe se deja sin tipo (léxica si hay varias interpretaciones)."""
        if isinstance(v, str):
            limpio = normalizar_simple(v)
            return limpio if limpio in {t.value for t in TipoAmbiguedad} else None
        return v

    @model_validator(mode="after")
    def _coherencia(self) -> "ResultadoIntencion":
        ids = [i.id for i in self.intenciones]
        if len(ids) != len(set(ids)):
            raise ValueError(f"'{self.termino}': ids de intención repetidos: {ids}")
        if len(self.intenciones) == 1:
            self.tipo_ambiguedad = None
        elif self.tipo_ambiguedad is None:
            self.tipo_ambiguedad = TipoAmbiguedad.LEXICA  # un término con varias interpretaciones: léxica por omisión
        return self

    @property
    def univoco(self) -> bool:
        return len(self.intenciones) == 1


class SalidaIntenciones(Contrato):
    resultados: list[ResultadoIntencion]


# ================================================================ Modelador: entradas del LEL

class EntradaLexicoLLM(Contrato):
    termino: str = Field(min_length=1)
    simbolo: str = Field(min_length=1, max_length=80)
    tipo: Categoria
    nocion: list[str] = Field(min_length=1, max_length=4)
    impacto: list[str] = Field(min_length=1, max_length=4)
    intencion: str = Field(min_length=1, max_length=400)
    sinonimos: list[str] = Field(default=[], max_length=8)

    @field_validator("tipo", mode="before")
    @classmethod
    def _tipo(cls, v: Any) -> Any:
        return categoria_flexible(v)

    @model_validator(mode="before")
    @classmethod
    def _limites(cls, datos: Any) -> Any:
        return _recortar(datos, {"nocion": 4, "impacto": 4, "sinonimos": 8})


class SalidaLexico(Contrato):
    entradas: list[EntradaLexicoLLM]


# ================================================================ Modelador: mapa conceptual con propósito

class ConceptoPropuesto(Contrato):
    id: str = Field(pattern=r"^C\d+$")
    etiqueta: str = Field(min_length=1, max_length=60)
    simbolo: str | None = Field(None, max_length=80)  # el símbolo del LEL que representa


class RelacionPropuesta(Contrato):
    origen: str = Field(min_length=1)
    enlace: str = Field(min_length=1, max_length=50)
    destino: str = Field(min_length=1)


class SalidaMapaProposito(Contrato):
    """`proposito`: la pregunta de enfoque que el mapa responde (Novak). `central`: el id del
    concepto del que parte el mapa."""

    proposito: str = Field(min_length=1, max_length=240)
    central: str = Field(min_length=1)
    conceptos: list[ConceptoPropuesto] = Field(min_length=2, max_length=30)
    relaciones: list[RelacionPropuesta] = Field(min_length=1, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def _limites(cls, datos: Any) -> Any:
        return _recortar(datos, {"conceptos": 30, "relaciones": 50})


# ================================================================ Modelador: metas en tres niveles

NivelMeta = Literal["organizacional", "estrategica", "especifica"]
PREFIJO_META: dict[str, str] = {"organizacional": "MO", "estrategica": "ME", "especifica": "MS"}
NIVEL_SUPERIOR: dict[str, str | None] = {"organizacional": None, "estrategica": "organizacional",
                                         "especifica": "estrategica"}


class MetaPropuesta(Contrato):
    id: str = Field(min_length=1, max_length=12)
    enunciado: str = Field(min_length=1, max_length=320)
    contribuye_a: str | None = None
    indicador: str | None = Field(None, max_length=240)  # cómo se sabe que se cumplió (específicas)
    simbolos: list[str] = Field(default=[], max_length=10)
    evidencia: list[str] = Field(default=[], max_length=8)

    @model_validator(mode="before")
    @classmethod
    def _limites(cls, datos: Any) -> Any:
        return _recortar(datos, {"simbolos": 10, "evidencia": 8})


class SalidaMetas(Contrato):
    organizacionales: list[MetaPropuesta] = Field(min_length=1, max_length=5)
    estrategicas: list[MetaPropuesta] = Field(min_length=1, max_length=10)
    especificas: list[MetaPropuesta] = Field(min_length=1, max_length=24)

    @model_validator(mode="before")
    @classmethod
    def _limites(cls, datos: Any) -> Any:
        return _recortar(datos, {"organizacionales": 5, "estrategicas": 10, "especificas": 24})


# ================================================================ Modelador: requisitos

Prioridad = Literal["alta", "media", "baja"]


class RequisitoGenerado(Contrato):
    texto: str = Field(min_length=1, max_length=700)
    tipo: TipoRequisito
    categoria: CategoriaNoFuncional | None = None
    prioridad: Prioridad = "media"
    metas: list[str] = Field(default=[], max_length=5)
    simbolos: list[str] = Field(default=[], max_length=12)
    evidencia: list[str] = Field(default=[], max_length=8)
    criterios: list[str] = Field(default=[], max_length=5)
    supuestos: list[str] = Field(default=[], max_length=5)

    @model_validator(mode="before")
    @classmethod
    def _flexible(cls, datos: Any) -> Any:
        datos = _recortar(datos, {"metas": 5, "simbolos": 12, "evidencia": 8, "criterios": 5, "supuestos": 5})
        if isinstance(datos, dict):
            if isinstance(datos.get("tipo"), str):
                datos["tipo"] = _SINONIMOS_TIPO_REQUISITO.get(datos["tipo"].strip().lower(), datos["tipo"])
            if isinstance(datos.get("prioridad"), str):
                datos["prioridad"] = datos["prioridad"].strip().lower()
            if isinstance(datos.get("categoria"), str):
                datos["categoria"] = datos["categoria"].strip().lower() or None
        return datos

    @model_validator(mode="after")
    def _coherencia(self) -> "RequisitoGenerado":
        if self.tipo == TipoRequisito.FUNCIONAL:
            self.categoria = None
        self.criterios, self.supuestos = _sin_vacios(self.criterios), _sin_vacios(self.supuestos)
        return self


class SalidaRequisitos(Contrato):
    requisitos: list[RequisitoGenerado] = Field(min_length=1, max_length=25)

    @model_validator(mode="before")
    @classmethod
    def _limites(cls, datos: Any) -> Any:
        return _recortar(datos, {"requisitos": 25})


# ================================================================ Lo que guarda el sistema y corrige la persona

class Editable(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


EstadoEntrada = Literal["propuesto", "validado", "corregido", "descartado"]


class CambiosEntradaLexico(Editable):
    """Lo que la persona puede corregir de una entrada del LEL."""

    simbolo: str | None = Field(None, min_length=1, max_length=80)
    tipo: Categoria | None = None
    nocion: list[str] | None = Field(None, min_length=1, max_length=6)
    impacto: list[str] | None = Field(None, min_length=1, max_length=6)
    intencion: str | None = Field(None, min_length=1, max_length=400)
    sinonimos: list[str] | None = Field(None, max_length=10)

    @field_validator("nocion", "impacto", "sinonimos")
    @classmethod
    def _limpias(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _sin_vacios(v)


class EntradaLexicoNueva(Editable):
    """Un término que la persona agrega al LEL a mano."""

    simbolo: str = Field(min_length=1, max_length=80)
    tipo: Categoria
    nocion: list[str] = Field(min_length=1, max_length=6)
    impacto: list[str] = Field(default=[], max_length=6)
    intencion: str = Field(min_length=1, max_length=400)
    sinonimos: list[str] = Field(default=[], max_length=10)


class ConceptoMapaEditable(Editable):
    id: str = Field(pattern=r"^C\d+$")
    etiqueta: str = Field(min_length=1, max_length=60)
    simbolo: str | None = Field(None, max_length=80)
    x: float | None = None
    y: float | None = None
    validado: bool = False
    origen: Literal["agentes", "persona"] = "agentes"


class RelacionMapaEditable(Editable):
    id: str = Field(pattern=r"^R\d+$")
    origen: str = Field(pattern=r"^C\d+$")
    enlace: str = Field(min_length=1, max_length=50)
    destino: str = Field(pattern=r"^C\d+$")
    validado: bool = False
    autor: Literal["agentes", "persona"] = "agentes"


class MapaEditable(Editable):
    proposito: str = Field(min_length=1, max_length=240)
    central: str = Field(pattern=r"^C\d+$")
    conceptos: list[ConceptoMapaEditable] = Field(min_length=1, max_length=60)
    relaciones: list[RelacionMapaEditable] = Field(default=[], max_length=120)
    proposito_validado: bool = False

    @model_validator(mode="after")
    def _referencias(self) -> "MapaEditable":
        ids = [c.id for c in self.conceptos]
        if len(ids) != len(set(ids)):
            raise ValueError(f"conceptos repetidos: {ids}")
        if self.central not in ids:
            raise ValueError(f"el concepto central {self.central} no está en el mapa")
        rids = [r.id for r in self.relaciones]
        if len(rids) != len(set(rids)):
            raise ValueError(f"relaciones repetidas: {rids}")
        for r in self.relaciones:
            if r.origen not in ids or r.destino not in ids:
                raise ValueError(f"la relación {r.id} une conceptos que no están en el mapa")
            if r.origen == r.destino:
                raise ValueError(f"la relación {r.id} une un concepto consigo mismo")
        return self


class MetaEditable(Editable):
    id: str = Field(pattern=r"^M[OES]\d+$")
    nivel: NivelMeta
    enunciado: str = Field(min_length=1, max_length=320)
    contribuye_a: str | None = None
    indicador: str | None = Field(None, max_length=240)
    simbolos: list[str] = Field(default=[], max_length=12)
    evidencia: list[str] = Field(default=[], max_length=10)
    validada: bool = False
    origen: Literal["agentes", "persona"] = "agentes"


class MetasEditables(Editable):
    metas: list[MetaEditable] = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def _jerarquia(self) -> "MetasEditables":
        por_id = {m.id: m for m in self.metas}
        if len(por_id) != len(self.metas):
            raise ValueError("ids de meta repetidos")
        for m in self.metas:
            if not m.id.startswith(PREFIJO_META[m.nivel]):
                raise ValueError(f"{m.id}: el id de una meta {m.nivel} empieza con {PREFIJO_META[m.nivel]}")
            superior = NIVEL_SUPERIOR[m.nivel]
            if superior is None:
                if m.contribuye_a is not None:
                    raise ValueError(f"{m.id}: una meta de la organización no contribuye a otra")
            elif m.contribuye_a is None or por_id.get(m.contribuye_a) is None \
                    or por_id[m.contribuye_a].nivel != superior:
                raise ValueError(f"{m.id}: una meta {m.nivel} contribuye a una meta {superior} del proyecto")
        return self


class RequisitoEditable(Editable):
    id: str = Field(pattern=r"^RN?F\d+$")
    texto: str = Field(min_length=1, max_length=700)
    tipo: TipoRequisito
    categoria: CategoriaNoFuncional | None = None
    prioridad: Prioridad = "media"
    metas: list[str] = Field(default=[], max_length=6)
    simbolos: list[str] = Field(default=[], max_length=16)
    evidencia: list[str] = Field(default=[], max_length=10)
    criterios: list[str] = Field(default=[], max_length=6)
    supuestos: list[str] = Field(default=[], max_length=6)
    avisos: list[str] = Field(default=[], max_length=10)
    validado: bool = False
    origen: Literal["agentes", "persona"] = "agentes"

    @model_validator(mode="after")
    def _coherencia(self) -> "RequisitoEditable":
        if self.tipo == TipoRequisito.FUNCIONAL:
            self.categoria = None
        self.criterios, self.supuestos = _sin_vacios(self.criterios), _sin_vacios(self.supuestos)
        return self


class RequisitosEditables(Editable):
    requisitos: list[RequisitoEditable] = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def _unicos(self) -> "RequisitosEditables":
        ids = [r.id for r in self.requisitos]
        if len(ids) != len(set(ids)):
            raise ValueError(f"ids de requisito repetidos: {ids}")
        return self
