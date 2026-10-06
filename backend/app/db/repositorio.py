"""Persistencia de trazas y del LEL: MongoDB con respaldo en JSON (ADR 0006).

Las dos implementaciones cumplen la misma interfaz. La fábrica intenta Mongo y,
si no responde dentro de `MONGO_TIMEOUT_MS`, usa archivos JSON en
`data/resultados/` para que la sandbox funcione igual.

- Colección/archivo `trazas`: un documento por requisito con todos sus mensajes.
- Colección/archivo `lel`: las entradas formalizadas (cada una con su proyecto).
- Colecciones genéricas (`proyectos`, `documentos`, `comparaciones`,
  `evaluaciones`…): documentos JSON con id propio (`P01`, `D01`…). Los módulos
  validan sus datos con sus modelos Pydantic; el repositorio solo los guarda.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable, Protocol

from app.config import Settings
from app.models import PROYECTO_GENERAL, EntradaLELFormalizada, Estado, Mensaje, Origen, Transicion, Traza, ahora

log = logging.getLogger(__name__)

_PATRON_REQ = re.compile(r"^R(\d+)$")
_PATRON_COLECCION = re.compile(r"^[a-z_]+$")
CAMPOS_RESUMEN = ("req_id", "proyecto_id", "ciclo", "texto", "origen", "estado", "creado", "actualizado")


def formato_req_id(n: int) -> str:
    return f"R{n:02d}"


def formato_id(prefijo: str, n: int) -> str:
    return f"{prefijo}{n:02d}"


def _numero(doc_id: str, prefijo: str) -> int | None:
    m = re.fullmatch(rf"{re.escape(prefijo)}(\d+)", str(doc_id))
    return int(m.group(1)) if m else None


def _nueva_traza(req_id: str, texto: str, config: dict, proyecto_id: str, origen: Origen | None, ciclo: int) -> Traza:
    return Traza(req_id=req_id, proyecto_id=proyecto_id, ciclo=ciclo, texto=texto, origen=origen, estado=Estado.CARGADO,
                 config=config, transiciones=[Transicion(estado=Estado.CARGADO, secuencia=0)])


def _coincide(doc: dict, filtro: dict) -> bool:
    return all(doc.get(k) == v for k, v in filtro.items())


class Repositorio(Protocol):
    descripcion: str

    # trazas
    def crear_traza(self, texto: str, config: dict[str, Any], proyecto_id: str = PROYECTO_GENERAL,
                    origen: Origen | None = None, ciclo: int = 1) -> Traza: ...
    def agregar_mensaje(self, req_id: str, **campos: Any) -> Mensaje: ...
    def cambiar_estado(self, req_id: str, estado: Estado) -> None: ...
    def obtener_traza(self, req_id: str) -> Traza | None: ...
    def listar_trazas(self, proyecto_id: str | None = None) -> list[dict]: ...
    def trazas_completas(self, proyecto_id: str | None = None) -> list[Traza]: ...
    # LEL
    def guardar_lel(self, entradas: list[EntradaLELFormalizada]) -> None: ...
    def listar_lel(self, proyecto_id: str | None = None) -> list[EntradaLELFormalizada]: ...
    # documentos genéricos por colección
    def crear_doc(self, coleccion: str, prefijo: str, fabricar: Callable[[str], dict]) -> dict: ...
    def guardar_doc(self, coleccion: str, doc_id: str, datos: dict) -> None: ...
    def obtener_doc(self, coleccion: str, doc_id: str) -> dict | None: ...
    def listar_docs(self, coleccion: str, **filtro: Any) -> list[dict]: ...


# ---------------------------------------------------------------- JSON

class RepositorioJson:
    """Un archivo por traza (`trazas/R01.json`) y un archivo para el LEL (`lel.json`).

    Escrituras atómicas (archivo temporal + `os.replace`) bajo un candado: el
    servidor es un solo proceso y el grafo escribe desde hilos de fondo.
    """

    def __init__(self, directorio: Path):
        self.dir = Path(directorio)
        self.dir_trazas = self.dir / "trazas"
        self.archivo_lel = self.dir / "lel.json"
        self.dir_trazas.mkdir(parents=True, exist_ok=True)
        self._candado = threading.RLock()
        self.descripcion = f"json:{self.dir}"

    # utilidades
    def _ruta(self, req_id: str) -> Path:
        if not _PATRON_REQ.match(req_id):
            raise ValueError(f"req_id inválido: {req_id}")
        return self.dir_trazas / f"{req_id}.json"

    @staticmethod
    def _escribir(ruta: Path, datos: Any) -> None:
        tmp = ruta.with_suffix(ruta.suffix + ".tmp")
        tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, ruta)

    def _leer(self, req_id: str) -> Traza:
        ruta = self._ruta(req_id)
        if not ruta.exists():
            raise KeyError(req_id)
        return Traza.model_validate_json(ruta.read_text(encoding="utf-8"))

    def _guardar(self, traza: Traza) -> None:
        traza.actualizado = ahora()
        self._escribir(self._ruta(traza.req_id), traza.model_dump(mode="json"))

    # interfaz
    def crear_traza(self, texto: str, config: dict[str, Any], proyecto_id: str = PROYECTO_GENERAL,
                    origen: Origen | None = None, ciclo: int = 1) -> Traza:
        with self._candado:
            usados = [int(m.group(1)) for p in self.dir_trazas.glob("R*.json") if (m := _PATRON_REQ.match(p.stem))]
            traza = _nueva_traza(formato_req_id(max(usados, default=0) + 1), texto, config, proyecto_id, origen, ciclo)
            self._guardar(traza)
            return traza

    def agregar_mensaje(self, req_id: str, **campos: Any) -> Mensaje:
        with self._candado:
            traza = self._leer(req_id)
            msg = Mensaje(req_id=req_id, secuencia=len(traza.mensajes) + 1, **campos)
            traza.mensajes.append(msg)
            self._guardar(traza)
            return msg

    def cambiar_estado(self, req_id: str, estado: Estado) -> None:
        with self._candado:
            traza = self._leer(req_id)
            traza.estado = estado
            traza.transiciones.append(Transicion(estado=estado, secuencia=len(traza.mensajes)))
            self._guardar(traza)

    def obtener_traza(self, req_id: str) -> Traza | None:
        with self._candado:
            try:
                return self._leer(req_id)
            except (KeyError, ValueError):
                return None

    def _todas(self, proyecto_id: str | None) -> list[dict]:
        salida = []
        for ruta in self.dir_trazas.glob("R*.json"):
            if _PATRON_REQ.match(ruta.stem):
                d = json.loads(ruta.read_text(encoding="utf-8"))
                d.setdefault("proyecto_id", PROYECTO_GENERAL)
                if proyecto_id is None or d["proyecto_id"] == proyecto_id:
                    salida.append(d)
        return sorted(salida, key=lambda d: int(d["req_id"][1:]))

    def listar_trazas(self, proyecto_id: str | None = None) -> list[dict]:
        """Resumen de cada traza (sin mensajes), ordenado por req_id."""
        with self._candado:
            return [{**{k: d.get(k) for k in CAMPOS_RESUMEN}, "ciclo": d.get("ciclo") or 1} for d in self._todas(proyecto_id)]

    def trazas_completas(self, proyecto_id: str | None = None) -> list[Traza]:
        with self._candado:
            return [Traza.model_validate(d) for d in self._todas(proyecto_id)]

    def guardar_lel(self, entradas: list[EntradaLELFormalizada]) -> None:
        with self._candado:
            actuales = [e.model_dump(mode="json") for e in self.listar_lel()]
            self._escribir(self.archivo_lel, actuales + [e.model_dump(mode="json") for e in entradas])

    def listar_lel(self, proyecto_id: str | None = None) -> list[EntradaLELFormalizada]:
        with self._candado:
            if not self.archivo_lel.exists():
                return []
            todas = [EntradaLELFormalizada.model_validate(d) for d in json.loads(self.archivo_lel.read_text(encoding="utf-8"))]
            return [e for e in todas if proyecto_id is None or e.proyecto_id == proyecto_id]

    # documentos genéricos: <dir>/<coleccion>/<id>.json
    def _dir_coleccion(self, coleccion: str) -> Path:
        if not _PATRON_COLECCION.match(coleccion) or coleccion == "trazas":
            raise ValueError(f"colección inválida: {coleccion}")
        d = self.dir / coleccion
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _id_valido(doc_id: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z]+\d+", str(doc_id)))

    def crear_doc(self, coleccion: str, prefijo: str, fabricar: Callable[[str], dict]) -> dict:
        with self._candado:
            d = self._dir_coleccion(coleccion)
            usados = [n for p in d.glob(f"{prefijo}*.json") if (n := _numero(p.stem, prefijo)) is not None]
            doc_id = formato_id(prefijo, max(usados, default=0) + 1)
            datos = fabricar(doc_id)
            self._escribir(d / f"{doc_id}.json", datos)
            return datos

    def guardar_doc(self, coleccion: str, doc_id: str, datos: dict) -> None:
        if not self._id_valido(doc_id):
            raise ValueError(f"id inválido: {doc_id}")
        with self._candado:
            self._escribir(self._dir_coleccion(coleccion) / f"{doc_id}.json", datos)

    def obtener_doc(self, coleccion: str, doc_id: str) -> dict | None:
        if not self._id_valido(doc_id):
            return None
        with self._candado:
            ruta = self._dir_coleccion(coleccion) / f"{doc_id}.json"
            return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None

    def listar_docs(self, coleccion: str, **filtro: Any) -> list[dict]:
        with self._candado:
            rutas = sorted(self._dir_coleccion(coleccion).glob("*.json"), key=lambda r: (len(r.stem), r.stem))
            docs = [json.loads(r.read_text(encoding="utf-8")) for r in rutas]
            return [x for x in docs if _coincide(x, filtro)]


# ---------------------------------------------------------------- Mongo

class RepositorioMongo:
    """`trazas` usa `_id = req_id`; el contador de secuencia vive en el propio
    documento (`ultima_secuencia`) y se incrementa con `$inc` atómico."""

    def __init__(self, db):
        self.db = db
        self.trazas = db["trazas"]
        self.lel = db["lel"]
        self.descripcion = f"mongo:{db.name}"

    @staticmethod
    def _a_traza(doc: dict) -> Traza:
        return Traza.model_validate({k: v for k, v in doc.items() if k in Traza.model_fields})

    def crear_traza(self, texto: str, config: dict[str, Any], proyecto_id: str = PROYECTO_GENERAL,
                    origen: Origen | None = None, ciclo: int = 1) -> Traza:
        from pymongo.errors import DuplicateKeyError

        ultimo = max((int(m.group(1)) for d in self.trazas.find({}, {"_id": 1})
                      if (m := _PATRON_REQ.match(str(d["_id"])))), default=0)
        while True:
            req_id = formato_req_id(ultimo + 1)
            traza = _nueva_traza(req_id, texto, config, proyecto_id, origen, ciclo)
            doc = traza.model_dump(mode="json")
            doc.update(_id=req_id, ultima_secuencia=0, creado=traza.creado, actualizado=traza.actualizado)
            try:
                self.trazas.insert_one(doc)
                return traza
            except DuplicateKeyError:  # otro proceso tomó el mismo id
                ultimo += 1

    def agregar_mensaje(self, req_id: str, **campos: Any) -> Mensaje:
        from pymongo import ReturnDocument

        doc = self.trazas.find_one_and_update({"_id": req_id}, {"$inc": {"ultima_secuencia": 1}},
                                              projection={"ultima_secuencia": 1}, return_document=ReturnDocument.AFTER)
        if doc is None:
            raise KeyError(req_id)
        msg = Mensaje(req_id=req_id, secuencia=doc["ultima_secuencia"], **campos)
        guardado = msg.model_dump(mode="json")
        guardado["timestamp"] = msg.timestamp
        self.trazas.update_one({"_id": req_id}, {"$push": {"mensajes": guardado}, "$set": {"actualizado": ahora()}})
        return msg

    def cambiar_estado(self, req_id: str, estado: Estado) -> None:
        doc = self.trazas.find_one({"_id": req_id}, {"ultima_secuencia": 1})
        if doc is None:
            raise KeyError(req_id)
        t = Transicion(estado=estado, secuencia=doc["ultima_secuencia"])
        self.trazas.update_one({"_id": req_id}, {
            "$set": {"estado": estado.value, "actualizado": ahora()},
            "$push": {"transiciones": {**t.model_dump(mode="json"), "timestamp": t.timestamp}},
        })

    def obtener_traza(self, req_id: str) -> Traza | None:
        doc = self.trazas.find_one({"_id": req_id})
        return self._a_traza(doc) if doc else None

    @staticmethod
    def _filtro_proyecto(proyecto_id: str | None) -> dict:
        if proyecto_id is None:
            return {}
        if proyecto_id == PROYECTO_GENERAL:  # trazas anteriores a los proyectos no tienen el campo
            return {"$or": [{"proyecto_id": PROYECTO_GENERAL}, {"proyecto_id": {"$exists": False}}]}
        return {"proyecto_id": proyecto_id}

    def listar_trazas(self, proyecto_id: str | None = None) -> list[dict]:
        docs = self.trazas.find(self._filtro_proyecto(proyecto_id), {k: 1 for k in CAMPOS_RESUMEN})
        salida = []
        for d in docs:
            r = {k: d.get(k) for k in CAMPOS_RESUMEN}
            r["proyecto_id"] = r["proyecto_id"] or PROYECTO_GENERAL
            r["ciclo"] = r["ciclo"] or 1
            for k in ("creado", "actualizado"):
                if hasattr(r[k], "isoformat"):
                    r[k] = r[k].isoformat()
            salida.append(r)
        return sorted(salida, key=lambda d: int(d["req_id"][1:]))

    def trazas_completas(self, proyecto_id: str | None = None) -> list[Traza]:
        docs = self.trazas.find(self._filtro_proyecto(proyecto_id))
        return sorted((self._a_traza(d) for d in docs), key=lambda t: int(t.req_id[1:]))

    def guardar_lel(self, entradas: list[EntradaLELFormalizada]) -> None:
        if entradas:
            self.lel.insert_many([e.model_dump(mode="json") for e in entradas])

    def listar_lel(self, proyecto_id: str | None = None) -> list[EntradaLELFormalizada]:
        return [EntradaLELFormalizada.model_validate({k: v for k, v in d.items() if k != "_id"})
                for d in self.lel.find(self._filtro_proyecto(proyecto_id)).sort("_id", 1)]

    # documentos genéricos: colección propia, _id = id del documento
    def _col(self, coleccion: str):
        if not _PATRON_COLECCION.match(coleccion) or coleccion in ("trazas", "lel"):
            raise ValueError(f"colección inválida: {coleccion}")
        return self.db[coleccion]

    def crear_doc(self, coleccion: str, prefijo: str, fabricar: Callable[[str], dict]) -> dict:
        from pymongo.errors import DuplicateKeyError

        col = self._col(coleccion)
        ultimo = max((n for d in col.find({}, {"_id": 1}) if (n := _numero(d["_id"], prefijo)) is not None), default=0)
        while True:
            doc_id = formato_id(prefijo, ultimo + 1)
            datos = fabricar(doc_id)
            try:
                col.insert_one({**datos, "_id": doc_id})
                return datos
            except DuplicateKeyError:
                ultimo += 1

    def guardar_doc(self, coleccion: str, doc_id: str, datos: dict) -> None:
        self._col(coleccion).replace_one({"_id": doc_id}, {**datos, "_id": doc_id}, upsert=True)

    def obtener_doc(self, coleccion: str, doc_id: str) -> dict | None:
        d = self._col(coleccion).find_one({"_id": doc_id})
        return {k: v for k, v in d.items() if k != "_id"} if d else None

    def listar_docs(self, coleccion: str, **filtro: Any) -> list[dict]:
        docs = sorted(self._col(coleccion).find(filtro), key=lambda d: (len(str(d["_id"])), str(d["_id"])))
        return [{k: v for k, v in d.items() if k != "_id"} for d in docs]


# ---------------------------------------------------------------- fábrica

def crear_repositorio(settings: Settings) -> Repositorio:
    """Mongo si responde al `ping` dentro del tiempo límite; si no, JSON."""
    try:
        from pymongo import MongoClient

        cliente = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=settings.mongo_timeout_ms, tz_aware=True)
        cliente.admin.command("ping")
        repo = RepositorioMongo(cliente[settings.mongo_db])
        log.info("Persistencia en %s", repo.descripcion)
        return repo
    except Exception as e:  # sin Mongo: respaldo JSON
        repo = RepositorioJson(settings.ruta(settings.resultados_dir))
        log.warning("MongoDB no disponible (%s); persistencia en %s", type(e).__name__, repo.descripcion)
        return repo
