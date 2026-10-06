"""Forma exacta de la respuesta de la calibración (ADR 0013). Las funciones del
paquete devuelven dicts en modo JSON; la ruta usa `Calibracion` como
`response_model` y las pruebas validan contra ella."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import Estado, Via

Decision = Literal["aceptado_directo", "en_debate"]


class Forma(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Valor(Forma):
    req_id: str
    proyecto_id: str
    ciclo: int
    termino: str
    similitud: float
    umbral_usado: float | None
    decision_real: Decision
    tipo_ambiguedad: str
    via: Via | None
    estado_requisito: Estado
    modelo_embeddings: str | None


class Cambio(Forma):
    req_id: str
    termino: str
    similitud: float
    decision_real: Decision
    decision_con_umbral: Decision


class FilaRejilla(Forma):
    umbral: float
    configurado: bool
    directos: int
    debates: int
    cambian: list[Cambio]


class Bin(Forma):
    desde: float
    hasta: float
    n: int


class Distribucion(Forma):
    ancho_bin: float
    origen: float
    n: int
    min: float | None
    max: float | None
    media: float | None
    mediana: float | None
    bins: list[Bin]


class Parametros(Forma):
    desde: float
    hasta: float
    paso: float


class Fuente(Forma):
    proyecto_id: str
    evaluacion_id: str | None
    n_etiquetas: int


class EtiquetaSinSimilitud(Forma):
    req_id: str
    termino: str
    ambiguo: bool
    tipo_ambiguedad: str | None


class ValorSinEtiqueta(Forma):
    req_id: str
    termino: str
    similitud: float


class Separacion(Forma):
    max_ambiguos: float | None
    min_no_ambiguos: float | None
    separa: bool | None


class MalSeparado(Forma):
    req_id: str
    termino: str
    similitud: float
    ambiguo: bool
    decision_con_umbral: Decision
    tipo_error: Literal["falso_positivo", "falso_negativo"]


class FilaGroundTruth(Forma):
    umbral: float
    configurado: bool
    vp: int
    fp: int
    vn: int
    fn: int
    precision: float | None
    exhaustividad: float | None
    f1: float | None
    mal_separados: list[MalSeparado]


class ConGroundTruth(Forma):
    fuentes: list[Fuente]
    n_invalidas: int
    n_etiquetas: int
    n_emparejados: int
    n_ambiguos: int
    n_no_ambiguos: int
    etiquetas_sin_similitud: list[EtiquetaSinSimilitud]
    valores_sin_etiqueta: list[ValorSinEtiqueta]
    separacion: Separacion
    por_umbral: list[FilaGroundTruth]


class Calibracion(Forma):
    proyecto_id: str | None  # null en la calibración de todos los proyectos normales
    umbral_configurado: float
    max_rondas: int
    parametros: Parametros
    n_valores: int
    valores: list[Valor]
    umbrales_usados: list[float]
    modelos_embeddings: list[str]
    reprocesados: list[str]
    distribucion: Distribucion
    rejilla: list[FilaRejilla]
    con_ground_truth: ConGroundTruth | None
    avisos: list[str]
    nota: str
