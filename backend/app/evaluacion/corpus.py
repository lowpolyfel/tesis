"""Corpus de requisitos con su ground truth en un archivo separado (CONTEXTO §11, ADR 0014).

Un directorio por corpus en `CORPUS_DIR/<nombre>/`:

- `requisitos.jsonl`: lo único que llega al sistema y a la línea base. Una línea
  `{id, texto}` por requisito.
- `ground_truth.jsonl`: lo que se espera de cada requisito, con el mismo `id`.
  Nunca entra a un prompt: solo lo leen las métricas.
- `corpus.json` (opcional): descripción y procedencia (`ejemplo`, `autoria`,
  `validado_por`).

El cargador valida las dos partes por separado y luego que sus ids coincidan, y
reporta todos los errores juntos para corregirlos de una vez.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.models import TipoAmbiguedad
from .emparejamiento import aparece_en, palabras

ARCHIVO_REQUISITOS = "requisitos.jsonl"
ARCHIVO_GROUND_TRUTH = "ground_truth.jsonl"
ARCHIVO_DESCRIPCION = "corpus.json"
PATRON_NOMBRE = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$"  # también evita salir del directorio de corpus
PATRON_ID = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$"


class CorpusNoEncontrado(LookupError):
    pass


class CorpusInvalido(ValueError):
    def __init__(self, nombre: str, errores: list[str]):
        self.nombre = nombre
        self.errores = errores
        super().__init__(f"El corpus «{nombre}» tiene {len(errores)} error(es): " + "; ".join(errores))


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _sin_vacios(valores: list[str], campo: str) -> list[str]:
    if any(not v for v in valores):
        raise ValueError(f"{campo} no puede tener cadenas vacías")
    return valores


class RequisitoCorpus(Modelo):
    id: str = Field(pattern=PATRON_ID)
    texto: str = Field(min_length=1, max_length=2000)


class TerminoGT(Modelo):
    """Un término ambiguo del requisito: cómo aparece en el texto, de qué tipo es y qué
    interpretaciones admite."""

    termino: str = Field(min_length=1)
    tipo_ambiguedad: TipoAmbiguedad
    interpretaciones_validas: list[str] = Field(min_length=2)
    interpretacion_esperada: str | None = None

    @field_validator("interpretaciones_validas")
    @classmethod
    def _validas(cls, v: list[str]) -> list[str]:
        return _sin_vacios(v, "interpretaciones_validas")

    @model_validator(mode="after")
    def _esperada(self) -> "TerminoGT":
        if self.interpretacion_esperada is not None and self.interpretacion_esperada not in self.interpretaciones_validas:
            raise ValueError(f"'{self.termino}': interpretacion_esperada debe ser una de interpretaciones_validas")
        return self


class RequisitoGT(Modelo):
    """Ground truth de un requisito. `ambiguo` es verdadero si y solo si hay términos
    ambiguos; la vaguedad no es ambigüedad (CONTEXTO §6) y va en su propia lista."""

    id: str = Field(pattern=PATRON_ID)
    ambiguo: bool
    terminos: list[TerminoGT] = []
    vaguedad: list[str] = []
    regionales: list[str] = []
    notas: str | None = None

    @field_validator("vaguedad", "regionales")
    @classmethod
    def _listas(cls, v: list[str], info) -> list[str]:
        return _sin_vacios(v, info.field_name)

    @model_validator(mode="after")
    def _coherencia(self) -> "RequisitoGT":
        if self.ambiguo and not self.terminos:
            raise ValueError("ambiguo es true pero no hay terminos: di qué término es ambiguo")
        if not self.ambiguo and self.terminos:
            raise ValueError("ambiguo es false pero hay terminos: un término en terminos es ambiguo")
        vistos = [palabras(t.termino) for t in self.terminos]
        if len(vistos) != len(set(vistos)):
            raise ValueError("hay términos repetidos en terminos (tras normalizar)")
        return self


class DescripcionCorpus(Modelo):
    descripcion: str | None = None
    ejemplo: bool = False  # corpus de muestra del formato, no el de la tesis
    autoria: str | None = None  # quién construyó el ground truth
    validado_por: str | None = None  # quién lo revisó, de preferencia otra persona


class ItemCorpus(Modelo):
    id: str
    texto: str
    ground_truth: RequisitoGT


class Corpus(Modelo):
    nombre: str
    descripcion: str | None = None
    ejemplo: bool = False
    autoria: str | None = None
    validado_por: str | None = None
    huella: str  # sha256 de requisitos.jsonl y ground_truth.jsonl
    items: list[ItemCorpus]
    avisos: list[str] = []


# ---------------------------------------------------------------- lectura

def _resumir(e: ValidationError) -> str:
    partes = []
    for err in e.errors():
        lugar = ".".join(str(x) for x in err["loc"])
        if err["type"] == "missing":
            msg = "falta el campo"
        elif err["type"] == "extra_forbidden":
            msg = "campo no permitido"
        else:
            msg = err["msg"].removeprefix("Value error, ")
        partes.append(f"{lugar}: {msg}" if lugar else msg)
    return "; ".join(partes)


def _leer_jsonl(ruta: Path, modelo: type[Modelo], errores: list[str]) -> tuple[list[tuple[int, Any]], list[str]] | None:
    """Filas válidas `(línea, modelo)` y los ids de todas las líneas que traen uno, aunque no
    validen (para cruzar los dos archivos sin inventar faltantes). `None` si no se pudo leer."""
    if not ruta.is_file():
        errores.append(f"falta el archivo {ruta.name}")
        return None
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        errores.append(f"{ruta.name} no está en UTF-8")
        return None
    filas, ids = [], []
    for n, linea in enumerate(lineas, 1):
        if not linea.strip():
            continue
        try:
            datos = json.loads(linea)
        except json.JSONDecodeError as e:
            errores.append(f"{ruta.name}, línea {n}: no es JSON válido ({e.msg})")
            continue
        ident = datos.get("id") if isinstance(datos, dict) and isinstance(datos.get("id"), str) else None
        if ident is not None:
            ids.append(ident.strip())
        try:
            filas.append((n, modelo.model_validate(datos)))
        except ValidationError as e:
            errores.append(f"{ruta.name}, línea {n}{f' (id {ident})' if ident else ''}: {_resumir(e)}")
    return filas, ids


def _repetidos(filas: list[tuple[int, Any]], archivo: str, errores: list[str]) -> dict[str, Any]:
    por_id: dict[str, tuple[int, Any]] = {}
    for n, x in filas:
        if x.id in por_id:
            errores.append(f"{archivo}: el id «{x.id}» se repite (líneas {por_id[x.id][0]} y {n})")
        else:
            por_id[x.id] = (n, x)
    return {k: x for k, (_, x) in por_id.items()}


def _descripcion(directorio: Path, errores: list[str]) -> DescripcionCorpus:
    ruta = directorio / ARCHIVO_DESCRIPCION
    if not ruta.is_file():
        return DescripcionCorpus()
    try:
        return DescripcionCorpus.model_validate(json.loads(ruta.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        errores.append(f"{ARCHIVO_DESCRIPCION}: no es JSON válido ({e})")
    except ValidationError as e:
        errores.append(f"{ARCHIVO_DESCRIPCION}: {_resumir(e)}")
    return DescripcionCorpus()


def huella(directorio: Path) -> str | None:
    """sha256 de los dos archivos de datos; `None` si falta alguno."""
    rutas = [directorio / ARCHIVO_REQUISITOS, directorio / ARCHIVO_GROUND_TRUTH]
    if not all(r.is_file() for r in rutas):
        return None
    h = hashlib.sha256()
    for r in rutas:
        h.update(r.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _avisos(items: list[ItemCorpus]) -> list[str]:
    """Lo que no impide usar el corpus pero conviene revisar."""
    avisos = []
    for it in items:
        gt = it.ground_truth
        listados = [t.termino for t in gt.terminos] + gt.vaguedad + gt.regionales
        for termino in listados:
            if not aparece_en(termino, it.texto):
                avisos.append(f"{it.id}: «{termino}» no aparece tal cual en el texto; escríbelo como aparece "
                              "para que el emparejamiento lo encuentre")
    if items and all(it.ground_truth.ambiguo for it in items):
        avisos.append("no hay requisitos sin ambigüedad: son los que revelan si el umbral dispara de más "
                      "(CONTEXTO §11)")
    return avisos


def directorio_de(raiz: Path, nombre: str) -> Path:
    if not re.fullmatch(PATRON_NOMBRE, nombre or ""):
        raise CorpusNoEncontrado(nombre)
    d = Path(raiz) / nombre
    if not d.is_dir():
        raise CorpusNoEncontrado(nombre)
    return d


def cargar_corpus(raiz: Path, nombre: str) -> Corpus:
    """Lee y valida un corpus. `CorpusNoEncontrado` si no existe; `CorpusInvalido`
    (con la lista completa de errores) si algo no cumple el formato."""
    d = directorio_de(raiz, nombre)
    errores: list[str] = []
    desc = _descripcion(d, errores)
    leidos_req = _leer_jsonl(d / ARCHIVO_REQUISITOS, RequisitoCorpus, errores)
    leidos_gt = _leer_jsonl(d / ARCHIVO_GROUND_TRUTH, RequisitoGT, errores)
    requisitos = _repetidos(leidos_req[0], ARCHIVO_REQUISITOS, errores) if leidos_req else {}
    gt = _repetidos(leidos_gt[0], ARCHIVO_GROUND_TRUTH, errores) if leidos_gt else {}

    if leidos_req and leidos_gt:
        ids_req, ids_gt = set(leidos_req[1]), set(leidos_gt[1])
        sin_gt = [i for i in dict.fromkeys(leidos_req[1]) if i not in ids_gt]
        sin_req = [i for i in dict.fromkeys(leidos_gt[1]) if i not in ids_req]
        if sin_gt:
            errores.append(f"requisitos sin ground truth: {', '.join(sin_gt)}")
        if sin_req:
            errores.append(f"ground truth de ids que no están en {ARCHIVO_REQUISITOS}: {', '.join(sin_req)}")
        if not leidos_req[1] and not leidos_req[0]:
            errores.append(f"{ARCHIVO_REQUISITOS} no tiene requisitos")
    if errores:
        raise CorpusInvalido(nombre, errores)

    items = [ItemCorpus(id=i, texto=r.texto, ground_truth=gt[i]) for i, r in requisitos.items()]
    return Corpus(nombre=nombre, **desc.model_dump(), huella=huella(d), items=items, avisos=_avisos(items))


def nombres_de_corpus(raiz: Path) -> list[str]:
    raiz = Path(raiz)
    if not raiz.is_dir():
        return []
    return sorted(p.name for p in raiz.iterdir() if p.is_dir() and re.fullmatch(PATRON_NOMBRE, p.name))


def conteo(items: list[ItemCorpus]) -> dict:
    gts = [it.ground_truth for it in items]
    terminos = [t for g in gts for t in g.terminos]
    return {
        "n_requisitos": len(items),
        "n_ambiguos": sum(g.ambiguo for g in gts),
        "n_sin_ambiguedad": sum(not g.ambiguo for g in gts),
        "n_terminos": len(terminos),
        "por_tipo": {t.value: sum(x.tipo_ambiguedad == t for x in terminos) for t in TipoAmbiguedad},
        "n_vaguedad": sum(len(g.vaguedad) for g in gts),
        "n_regionales": sum(len(g.regionales) for g in gts),
    }


def resumen_corpus(raiz: Path, nombre: str) -> dict:
    """Forma `formas.ResumenCorpus`. Un corpus inválido se lista con sus errores, no se oculta."""
    try:
        c = cargar_corpus(raiz, nombre)
    except CorpusInvalido as e:
        errores_desc: list[str] = []
        desc = _descripcion(Path(raiz) / nombre, errores_desc)
        return {"nombre": nombre, "valido": False, "errores": e.errores, "avisos": [], **desc.model_dump(),
                "huella": huella(Path(raiz) / nombre), "conteo": None}
    return {"nombre": c.nombre, "valido": True, "errores": [], "avisos": c.avisos, "descripcion": c.descripcion,
            "ejemplo": c.ejemplo, "autoria": c.autoria, "validado_por": c.validado_por, "huella": c.huella,
            "conteo": conteo(c.items)}
