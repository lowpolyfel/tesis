"""A qué Mongo está conectado el servidor, medido en el momento (GET /conexion).

Distingue Atlas de un Mongo local y dice de dónde salió `MONGO_URI`. Ningún campo
lleva usuario ni contraseña: el host sale de `host_de_uri` y los mensajes de error
pasan por `enmascarar`.
"""
from __future__ import annotations

from time import perf_counter

from app.config import Settings
from app.models import ahora

from .repositorio import Repositorio, RepositorioMongo, enmascarar, host_de_uri

COLECCION_PRUEBA = "_prueba_conexion"


def _ms(desde: float) -> float:
    return round((perf_counter() - desde) * 1000, 1)


def _motivo(e: Exception, uri: str) -> str:
    return enmascarar(f"{type(e).__name__}: {e}", uri)


def _prueba_escritura(db, uri: str) -> dict:
    """Inserta, lee y borra un documento en `_prueba_conexion`; si la colección queda vacía, la borra."""
    col = db[COLECCION_PRUEBA]
    t0 = perf_counter()
    try:
        doc_id = col.insert_one({"prueba": "conexion", "creado": ahora()}).inserted_id
        leido = col.find_one({"_id": doc_id})
        col.delete_one({"_id": doc_id})
        ms = _ms(t0)
        if col.count_documents({}, limit=1) == 0:
            col.drop()
    except Exception as e:
        return {"ok": False, "ms": _ms(t0), "error": _motivo(e, uri)}
    if leido is None:
        return {"ok": False, "ms": ms, "error": "El documento de prueba se insertó pero no se pudo leer."}
    return {"ok": True, "ms": ms, "error": None}


def probar_conexion(repo: Repositorio, settings: Settings) -> dict:
    """Estado de la persistencia. Con Mongo mide `ping`, lee la versión, hace la prueba de
    escritura y cuenta los documentos de cada colección; un fallo va en `error` y la
    respuesta conserva su forma. Con el respaldo JSON, `error` es el motivo por el que
    no se pudo usar Mongo al arrancar."""
    mongo = isinstance(repo, RepositorioMongo)
    respuesta = {
        "persistencia": "mongo" if mongo else "json",
        "tipo": repo.tipo if mongo else None,
        "host": repo.host if mongo else host_de_uri(settings.mongo_uri),  # con JSON: al que intentó conectarse
        "base": repo.db.name if mongo else settings.mongo_db,
        "fuente_uri": settings.fuente_mongo_uri,
        "ping_ms": None,
        "version_servidor": None,
        "colecciones": [],
        "prueba_escritura": None,
        "checkpoints": f"sqlite:{settings.checkpoint_path}",
        "error": None if mongo else getattr(repo, "error_mongo", None),
    }
    if not mongo:
        return respuesta
    db, admin = repo.db, repo.db.client.admin
    try:
        t0 = perf_counter()
        admin.command("ping")
        respuesta["ping_ms"] = _ms(t0)
        respuesta["version_servidor"] = admin.command("buildInfo").get("version")
        respuesta["prueba_escritura"] = _prueba_escritura(db, settings.mongo_uri)
        respuesta["colecciones"] = [{"nombre": n, "documentos": db[n].estimated_document_count()}
                                    for n in sorted(db.list_collection_names()) if not n.startswith("system.")]
    except Exception as e:
        respuesta["error"] = _motivo(e, settings.mongo_uri)
    return respuesta
