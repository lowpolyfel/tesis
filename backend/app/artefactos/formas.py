"""Formas exactas de los artefactos de proyecto (ADR 0011).

Las funciones de `app.artefactos` devuelven dicts en modo JSON; estos modelos
son su contrato: las rutas los usan como `response_model` y las pruebas validan
contra ellos. El documento de `formalizados` se declara como `dict` porque su
contrato es el del Modelador (ADR 0010) y no se duplica aquí.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import EntradaLELFormalizada


class Forma(BaseModel):
    model_config = ConfigDict(extra="forbid")


TipoMeta = Literal["meta", "meta_blanda", "tarea", "recurso"]
TipoNodo = Literal["actor", "meta", "meta_blanda", "tarea", "recurso", "simbolo", "requisito"]
SubtipoSimbolo = Literal["sujeto", "objeto", "verbo", "estado"]
Relacion = Literal["persigue", "contribuye_a", "deriva_de", "usa", "resuelve", "menciona", "relacionado_con"]
MotivoFuera = Literal["en_proceso", "rechazado", "error", "reprocesado", "sin_formalizacion", "sin_traza"]


class RequisitoFuera(Forma):
    """Requisito del proyecto que no entra a los artefactos, y por qué."""

    req_id: str
    estado: str | None
    motivo: MotivoFuera
    detalle: str | None = None


# ---------------------------------------------------------------- metas

class MetaGlobal(Forma):
    id: str  # R03.M1: req_id + id local de la meta
    req_id: str
    enunciado: str
    tipo: TipoMeta
    actor: str | None  # nombre normalizado (el mismo de `actores`)
    actor_original: str | None  # como lo escribió el Modelador
    simbolos: list[str]
    contribuye_a: str | None  # id global


class Actor(Forma):
    nombre: str
    simbolo_lel: str | None  # símbolo sujeto del LEL con el que coincide
    metas: list[str]


class VaguedadCandidata(Forma):
    texto: str
    req_id: str
    meta_blanda: str | None  # meta blanda del mismo requisito que ya la recoge


class MetasProyecto(Forma):
    metas: list[MetaGlobal]
    actores: list[Actor]
    por_tipo: dict[TipoMeta, int]
    metas_blandas_desde_vaguedad: list[VaguedadCandidata]
    sin_actor: list[str]
    requisitos_fuera: list[RequisitoFuera]


# ---------------------------------------------------------------- Big Picture

class Nodo(Forma):
    id: str
    tipo: TipoNodo
    subtipo: SubtipoSimbolo | None  # solo en símbolos
    etiqueta: str
    detalle: str | None  # requisito: el reescrito; símbolo: su primera noción
    req_ids: list[str]


class Arista(Forma):
    origen: str
    destino: str
    relacion: Relacion


class Accion(Forma):
    actor: str | None
    verbo: str | None  # None si el enunciado no empieza con un infinitivo
    objeto: str
    req_id: str
    meta: str


class Restriccion(Forma):
    texto: str
    req_id: str
    origen: Literal["meta_blanda", "vaguedad"]
    meta: str | None


class TerminoResuelto(Forma):
    termino: str
    significado: str
    via: str | None
    tipo_ambiguedad: str
    cambio: str | None  # ninguno | eleccion | edicion (lo que hizo el humano)
    req_id: str


class Dependencia(Forma):
    de: str  # requisito que usa el símbolo
    a: str  # requisito cuya formalización lo resolvió
    por: str  # el símbolo


class RequisitoPanorama(Forma):
    req_id: str
    requisito_reescrito: str


class Panorama(Forma):
    actores: list[str]
    acciones: list[Accion]
    restricciones: list[Restriccion]
    terminos_resueltos: list[TerminoResuelto]
    dependencias: list[Dependencia]
    requisitos: list[RequisitoPanorama]


class TerminoSinSimbolo(Forma):
    termino: str
    metas: list[str]


class BigPicture(Forma):
    nodos: list[Nodo]
    aristas: list[Arista]
    panorama: Panorama
    terminos_sin_simbolo: list[TerminoSinSimbolo]
    requisitos_fuera: list[RequisitoFuera]
    mermaid: str
    plantuml: str


# ---------------------------------------------------------------- requisito

class ArtefactosRequisito(Forma):
    req_id: str
    proyecto_id: str
    estado: str
    formalizado: dict | None
    entradas_lel: list[EntradaLELFormalizada]
    metas: list[MetaGlobal]


# ---------------------------------------------------------------- especificación (ADR 0017)

class RequisitoEspecificado(Forma):
    clave: str  # RF-01, RNF-01; el req_id si no tiene tipo
    req_id: str
    marca: str | None  # numeración del documento de origen
    original: str
    reescrito: str
    tipo_requisito: Literal["funcional", "no_funcional"] | None
    categoria: str | None
    supuestos: list[str]
    corregido: str | None  # fecha de la última corrección manual


class EntradaGlosario(Forma):
    simbolo: str
    tipo: SubtipoSimbolo
    nocion: str | None
    req_ids: list[str]


class Especificacion(Forma):
    funcionales: list[RequisitoEspecificado]
    no_funcionales: list[RequisitoEspecificado]
    sin_clasificar: list[RequisitoEspecificado]
    glosario: list[EntradaGlosario]
    requisitos_fuera: list[RequisitoFuera]
