"""Persistencia de trazas y del LEL: MongoDB con respaldo en JSON (ADR 0006).

Las dos implementaciones cumplen la misma interfaz. La fábrica intenta Mongo y,
si no responde dentro de `MONGO_TIMEOUT_MS`, usa archivos JSON en
`data/resultados/` para que la sandbox funcione igual.

- Colección/archivo `trazas`: un documento por requisito con todos sus mensajes.
- Colección/archivo `lel`: las entradas formalizadas.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Protocol

from app.config import Settings
from app.models import EntradaLELFormalizada, Estado, Mensaje, Transicion, Traza, ahora

log = logging.getLogger(__name__)

_PATRON_REQ = re.compile(r"^R(\d+)$")


def formato_req_id(n: int) -> str:
    return f"R{n:02d}"


class Repositorio(Protocol):
    descripcion: str

    def crear_traza(self, texto: str, config: dict[str, Any]) -> Traza: ...
    def agregar_mensaje(self, req_id: str, **campos: Any) -> Mensaje: ...
    def cambiar_estado(self, req_id: str, estado: Estado) -> None: ...
    def obtener_traza(self, req_id: str) -> Traza | None: ...
    def guardar_lel(self, entradas: list[EntradaLELFormalizada]) -> None: ...
    def listar_lel(self) -> list[EntradaLELFormalizada]: ...


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
    def crear_traza(self, texto: str, config: dict[str, Any]) -> Traza:
        with self._candado:
            usados = [int(m.group(1)) for p in self.dir_trazas.glob("R*.json") if (m := _PATRON_REQ.match(p.stem))]
            req_id = formato_req_id(max(usados, default=0) + 1)
            traza = Traza(req_id=req_id, texto=texto, estado=Estado.CARGADO, config=config,
                          transiciones=[Transicion(estado=Estado.CARGADO, secuencia=0)])
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

    def guardar_lel(self, entradas: list[EntradaLELFormalizada]) -> None:
        with self._candado:
            actuales = [e.model_dump(mode="json") for e in self.listar_lel()]
            self._escribir(self.archivo_lel, actuales + [e.model_dump(mode="json") for e in entradas])

    def listar_lel(self) -> list[EntradaLELFormalizada]:
        with self._candado:
            if not self.archivo_lel.exists():
                return []
            return [EntradaLELFormalizada.model_validate(d) for d in json.loads(self.archivo_lel.read_text(encoding="utf-8"))]


# ---------------------------------------------------------------- Mongo

class RepositorioMongo:
    """`trazas` usa `_id = req_id`; el contador de secuencia vive en el propio
    documento (`ultima_secuencia`) y se incrementa con `$inc` atómico."""

    def __init__(self, db):
        self.trazas = db["trazas"]
        self.lel = db["lel"]
        self.descripcion = f"mongo:{db.name}"

    @staticmethod
    def _a_traza(doc: dict) -> Traza:
        return Traza.model_validate({k: v for k, v in doc.items() if k in Traza.model_fields})

    def crear_traza(self, texto: str, config: dict[str, Any]) -> Traza:
        from pymongo.errors import DuplicateKeyError

        ultimo = max((int(m.group(1)) for d in self.trazas.find({}, {"_id": 1})
                      if (m := _PATRON_REQ.match(str(d["_id"])))), default=0)
        while True:
            req_id = formato_req_id(ultimo + 1)
            traza = Traza(req_id=req_id, texto=texto, estado=Estado.CARGADO, config=config,
                          transiciones=[Transicion(estado=Estado.CARGADO, secuencia=0)])
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

    def guardar_lel(self, entradas: list[EntradaLELFormalizada]) -> None:
        if entradas:
            self.lel.insert_many([e.model_dump(mode="json") for e in entradas])

    def listar_lel(self) -> list[EntradaLELFormalizada]:
        return [EntradaLELFormalizada.model_validate({k: v for k, v in d.items() if k != "_id"})
                for d in self.lel.find().sort("_id", 1)]


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
