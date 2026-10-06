"""Formas exactas de las vistas derivadas (ADR 0015).

Las funciones de `app.analisis` devuelven dicts en modo JSON; estos modelos son
el contrato de esas formas: las rutas los usan como `response_model` (así quedan
en `/docs`) y las pruebas validan contra ellos. Lo que viene tal cual de un
payload de la traza (evaluaciones del Crítico, metas, entradas del LEL) se
declara como `dict` para no duplicar aquí los contratos de los agentes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.models import DecisionFiltro, Estado, Origen, Proyecto, Transicion, Via


class Forma(BaseModel):
    model_config = ConfigDict(extra="forbid")


TipoMarcado = Literal["lexica", "alcance", "anaforica", "sintactica", "vaguedad", "regional", "lel"]


# ---------------------------------------------------------------- configuración

class ModelosAgentes(Forma):
    extractor: str | None
    clasificador: str | None
    critico: str | None  # proveedor:modelo
    modelador: str | None


class ConfigNormalizada(Forma):
    umbral: float | None
    max_rondas: int | None
    modelos: ModelosAgentes
    modelo_embeddings: str | None
    temperatura: float | None
    semilla: int | None
    significado_max_palabras: int | None
    spacy_model: str | None
    catalogos: dict[str, str | None]
    persistencia: str | None
    otros: dict[str, Any]  # claves de la configuración que esta vista no reconoce


class Calibracion(Forma):
    desde: float
    hasta: float
    paso: float
    umbrales: list[float]


class Comparacion(Forma):
    relacion_umbral: float
    duplicado_umbral: float
    max_pares: int


class Configuracion(ConfigNormalizada):
    proveedor_critico: str
    modelos_auxiliares: dict[str, str]  # comparador, agente_unico
    calibracion: Calibracion
    comparacion: Comparacion
    nota: str


class Catalogos(Forma):
    regionales: dict[str, Any] | None
    vaguedad: dict[str, Any] | None
    versiones: dict[str, str | None]
    nota: str


# ---------------------------------------------------------------- vista por requisito

class InterpretacionPlana(Forma):
    id: str
    significado: str
    parafrasis_del_requisito: str


class InterpretacionVista(InterpretacionPlana):
    estado: Literal["vigente", "retirada"]
    retirada_en_ronda: int | None
    motivo_retiro: str | None


class Marcado(Forma):
    inicio: int
    fin: int
    texto: str  # el tramo del requisito
    termino: str  # como lo nombran los filtros (enlaza con `terminos`)
    decision_filtro: DecisionFiltro
    tipo: TipoMarcado | None
    detalle: str | None
    univoco: bool | None


class Extraccion(Forma):
    terminos: list[dict[str, Any]]
    descartados: list[Any]
    modelo: str | None
    prompt_version: str | None
    intentos: int | None
    duracion_ms: int | None


class SimilitudRonda(Forma):
    similitud: float | None
    umbral: float | None
    decision: str | None
    pares: dict[str, float]
    par_minimo: list[str] | None


class Divergencia(SimilitudRonda):
    modelo_embeddings: str | None


class Refinamiento(Forma):
    interpretaciones: list[InterpretacionPlana]
    retiradas: list[dict[str, Any]]
    nota: str | None


class ConsensoRonda(Forma):
    motivo: str | None
    similitud: float | None
    umbral: float | None
    propuesta: str | None


class Ronda(Forma):
    ronda: int
    evaluadas: list[InterpretacionPlana]  # lo que el Crítico evaluó en esta ronda
    evaluaciones: list[dict[str, Any]]
    objeciones: list[dict[str, Any]]
    refinamiento: Refinamiento | None
    similitud: SimilitudRonda | None
    consenso: ConsensoRonda | None


class Arbitraje(Forma):
    interpretacion_elegida: str
    justificacion_por_regla: list[dict[str, Any]]


class Resolucion(Forma):
    via: Via
    decision: Estado
    propuesta: InterpretacionPlana | None
    motivo: Literal["umbral", "una_interpretacion", "rondas_agotadas"] | None
    similitud_final: float | None
    arbitraje: Arbitraje | None


class ValidacionTermino(Forma):
    final: InterpretacionPlana | None
    cambio: str | None


class TerminoVista(Forma):
    termino: str
    origen: str | None  # extractor | regional | alcance | anafora
    detalle: str | None
    categoria: str | None
    univoco: bool | None  # None: el Clasificador aún no lo vio
    tipo_ambiguedad: str | None
    interpretaciones: list[InterpretacionVista]
    divergencia_inicial: Divergencia | None
    rondas: list[Ronda]
    resolucion: Resolucion | None
    validacion: ValidacionTermino | None
    entrada_lel: dict[str, Any] | None


class ResumenTerminos(Forma):
    n_terminos: int
    n_ambiguos: int
    tipos: dict[str, int]
    vaguedad: list[str]
    regionales: list[str]
    resueltos_por_lel: list[str]
    estructuras: int
    similitud_minima: float | None
    via: Via | None
    rondas_max: int
    n_errores: int


class ValidacionVista(Forma):
    decision: str
    comentario: str | None
    terminos: list[dict[str, Any]]
    timestamp: datetime


class ErrorVista(Forma):
    secuencia: int
    nodo: str | None
    excepcion: str | None
    mensaje: str | None
    prompt_version: str | None


class VistaRequisito(Forma):
    req_id: str
    proyecto_id: str
    ciclo: int
    texto: str
    origen: Origen | None
    estado: Estado
    creado: datetime
    actualizado: datetime
    en_proceso: bool
    terminal: bool
    config: ConfigNormalizada
    transiciones: list[Transicion]
    marcados: list[Marcado]
    extraccion: Extraccion | None
    terminos: list[TerminoVista]
    resumen: ResumenTerminos
    solicitud: dict[str, Any] | None
    validacion: ValidacionVista | None
    formalizacion: dict[str, Any] | None
    errores: list[ErrorVista]
    n_mensajes: int
    n_repetidos: int
    ultima_secuencia: int


class ResumenRequisito(Forma):
    req_id: str
    proyecto_id: str
    ciclo: int
    texto: str
    origen: Origen | None
    estado: Estado
    creado: datetime
    actualizado: datetime
    similitud_minima: float | None
    via: Via | None
    rondas_max: int
    n_ambiguos: int
    tipos: dict[str, int]
    vaguedad: list[str]
    en_proceso: bool


# ---------------------------------------------------------------- proyecto

class Contadores(Forma):
    requisitos: int
    ciclos: int
    en_proceso: int
    por_validar: int
    formalizados: int
    rechazados: int
    errores: int
    ambiguos: int
    lel: int


class CicloResumen(Forma):
    ciclo: int
    requisitos: int
    por_estado: dict[str, int]


class ResumenProyecto(Forma):
    proyecto: Proyecto
    contadores: Contadores
    por_estado: dict[str, int]
    por_ciclo: list[CicloResumen]
    requisitos: list[ResumenRequisito]


class Aparicion(Forma):
    req_id: str
    ciclo: int
    estado: Estado
    tipo_ambiguedad: str | None
    decision_filtro: DecisionFiltro | None
    via: Via | None
    similitud_inicial: float | None
    rondas: int
    interpretacion_final: str | None  # significado validado (solo si se aprobó)
    propuesta: str | None  # significado propuesto al humano


class SignificadoValidado(Forma):
    significado: str
    req_ids: list[str]


class EntradaEnConflicto(Forma):
    simbolo: str
    nocion: list[str]
    req_id: str


class DetalleInconsistencia(Forma):
    texto: str
    significados: list[SignificadoValidado]
    lel: list[EntradaEnConflicto]


class GrupoAmbiguedad(Forma):
    clave: str
    termino: str
    tipos: list[str]
    origenes: list[str]
    apariciones: list[Aparicion]
    inconsistente: bool
    detalle_inconsistencia: DetalleInconsistencia | None


class TerminoEnRequisitos(Forma):
    termino: str
    req_ids: list[str]


class Estructura(Forma):
    termino: str
    decision_filtro: DecisionFiltro
    detalle: str | None
    req_id: str


class TotalesAmbiguedad(Forma):
    por_tipo: dict[str, int]
    por_via: dict[str, int]
    inconsistentes: int


class AmbiguedadesProyecto(Forma):
    terminos: list[GrupoAmbiguedad]
    vaguedad: list[TerminoEnRequisitos]
    regionales: list[TerminoEnRequisitos]
    estructuras: list[Estructura]
    totales: TotalesAmbiguedad


class Fase(Forma):
    fase: int
    nombre: str
    agentes: list[str]
    mensajes: int
    requisitos_que_pasaron: int


class FlujoCiclo(Forma):
    ciclo: int | None  # None en el total del proyecto
    requisitos: int
    por_estado: dict[str, int]
    mensajes_por_agente: dict[str, int]
    mensajes_por_tipo: dict[str, int]
    fases: list[Fase]
    debates: int
    rondas_totales: int
    consensos: int
    arbitrajes: int
    directos: int
    validados: int
    rechazados: int
    formalizados: int
    lel_nuevas: int
    duracion_s: float | None


class FlujoProyecto(Forma):
    ciclos: list[FlujoCiclo]
    total: FlujoCiclo
