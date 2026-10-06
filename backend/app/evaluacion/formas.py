"""Forma exacta de las respuestas de corpus y evaluación (ADR 0014). Las funciones del
paquete devuelven dicts en modo JSON; las rutas usan estos modelos como
`response_model` y las pruebas validan contra ellos."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.models import Estado

from .corpus import RequisitoGT
from .emparejamiento import Criterio
from .modelos import EstadoEvaluacion, Etiqueta


class Forma(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- corpus

class ConteoCorpus(Forma):
    n_requisitos: int
    n_ambiguos: int
    n_sin_ambiguedad: int
    n_terminos: int
    por_tipo: dict[str, int]  # lexica, alcance, anaforica, sintactica
    n_vaguedad: int
    n_regionales: int


class ResumenCorpus(Forma):
    nombre: str
    valido: bool
    errores: list[str]
    avisos: list[str]
    descripcion: str | None
    ejemplo: bool
    autoria: str | None
    validado_por: str | None
    huella: str | None
    conteo: ConteoCorpus | None  # null si el corpus no es válido


class ItemCorpus(Forma):
    id: str
    texto: str
    ground_truth: RequisitoGT


class DetalleCorpus(Forma):
    nombre: str
    descripcion: str | None
    ejemplo: bool
    autoria: str | None
    validado_por: str | None
    huella: str
    avisos: list[str]
    conteo: ConteoCorpus
    items: list[ItemCorpus]


# ---------------------------------------------------------------- evaluación

class EvaluacionCreada(Forma):
    evaluacion_id: str
    proyecto_id: str
    total: int


class Progreso(Forma):
    total: int
    listos_sistema: int
    listos_linea_base: int


class ResumenEvaluacion(Forma):
    evaluacion_id: str
    nombre: str
    proyecto_id: str
    corpus: str
    ejemplo: bool
    creado: datetime
    terminado: datetime | None
    estado: EstadoEvaluacion
    progreso: Progreso


class Conteo(Forma):
    vp: int
    fp: int
    fn: int


class Deteccion(Conteo):
    precision: float | None
    exhaustividad: float | None
    f1: float | None


class NivelRequisito(Forma):
    vp: int
    fp: int
    vn: int
    fn: int
    sin_decision: int
    exactitud: float | None


class ExactitudTipo(Forma):
    n: int
    aciertos: int
    exactitud: float | None


class Debates(Forma):
    activados: int
    necesarios: int
    justificados: int
    de_mas: int
    faltantes: int


class Vias(Forma):
    aceptado_directo: int
    consenso: int
    arbitraje: int
    sin_via: int


class ResumenLineaBase(Forma):
    n: int
    errores: int
    deteccion: Deteccion
    deteccion_ambiguedad: Deteccion
    requisito: NivelRequisito
    tipo: ExactitudTipo


class ResumenSistema(ResumenLineaBase):
    debates: Debates
    vias: Vias


class Resumen(Forma):
    sistema: ResumenSistema
    linea_base: ResumenLineaBase


class TerminoEvaluado(Forma):
    termino: str
    origen: str  # decisión de los filtros (candidato, regional, alcance, anafora, vaguedad) o agente_unico
    detectado: bool
    motivo_deteccion: Literal["interpretaciones", "vaguedad", "regional", "agente_unico"] | None
    tipo_ambiguedad: str | None
    interpretacion: str | None  # significado propuesto (sistema) o interpretación elegida (línea base)
    via: str | None
    similitud: float | None  # inicial (ronda 0)
    emparejado_con: str | None
    criterio: Criterio | None
    clase_gt: Literal["ambiguedad", "vaguedad", "regional"] | None
    tipo_gt: str | None
    tipo_correcto: bool | None


class LadoComun(Forma):
    listo: bool
    error: str | None
    ambiguo: bool | None
    correcto: bool | None
    terminos: list[TerminoEvaluado]
    faltantes: list[str]
    deteccion: Conteo
    deteccion_ambiguedad: Conteo


class LadoSistema(LadoComun):
    estado: Estado | None
    debate: bool
    debate_gt: Literal["justificado", "de_mas", "faltante", "sin_debate_correcto"] | None


class LadoLineaBase(LadoComun):
    modelo: str | None
    prompt_version: str | None


class FilaRequisito(Forma):
    id_corpus: str
    req_id: str
    texto: str | None
    ground_truth: RequisitoGT
    sistema: LadoSistema
    linea_base: LadoLineaBase


class InformeEvaluacion(Forma):
    evaluacion_id: str
    nombre: str
    proyecto_id: str
    corpus: str
    ejemplo: bool
    creado: datetime
    terminado: datetime | None
    estado: EstadoEvaluacion
    config: dict[str, Any]
    progreso: Progreso
    resumen: Resumen
    requisitos: list[FilaRequisito]
    etiquetas: list[Etiqueta]
    avisos: list[str]
    nota: str
