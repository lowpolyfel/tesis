"""A qué Mongo está conectado el servidor (GET /conexion), sin credenciales en ningún campo."""
import json
import logging

import pytest

import app.config as config
from app.config import Settings, fuente_de
from app.db import RepositorioJson, RepositorioMongo, crear_repositorio
from app.db.conexion import COLECCION_PRUEBA, probar_conexion
from app.db.repositorio import enmascarar, host_de_uri, tipo_de_host

USUARIO, CLAVE = "usuario_tesis", "cl@ve/secreta"
ATLAS = f"mongodb+srv://{USUARIO}:cl%40ve%2Fsecreta@cluster0.abc123.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"


def _sin_credenciales(texto: str) -> bool:
    return all(s not in texto for s in (USUARIO, CLAVE, "cl%40ve%2Fsecreta", "secreta"))


@pytest.mark.parametrize("uri, host", [
    (ATLAS, "cluster0.abc123.mongodb.net"),
    ("mongodb://localhost:27017", "localhost:27017"),
    ("mongodb://u:p@h1:27017,h2:27017/tesis?replicaSet=rs", "h1:27017,h2:27017"),
    # contraseña con «/» y «?» sin codificar: no se cuela en el host
    ("mongodb+srv://u:pa/ss?x@cluster0.abc123.mongodb.net/", "cluster0.abc123.mongodb.net"),
])
def test_host_de_uri_sin_credenciales(uri, host):
    assert host_de_uri(uri) == host


@pytest.mark.parametrize("host, tipo", [
    ("cluster0.abc123.mongodb.net", "atlas"),
    ("cluster0-shard-00-00.abc123.mongodb.net:27017,cluster0-shard-00-01.abc123.mongodb.net:27017", "atlas"),
    ("localhost:27017", "local"),
    ("127.0.0.1", "local"),
    ("[::1]:27017", "local"),
    ("mongo.ejemplo.com:27017", "otro"),
    ("localhost:27017,cluster0.abc123.mongodb.net", "otro"),
    ("", "otro"),
])
def test_tipo_de_host(host, tipo):
    assert tipo_de_host(host) == tipo


def test_enmascarar_quita_la_uri_y_las_credenciales_sueltas():
    texto = enmascarar(f"falló {ATLAS} con la clave {CLAVE} del usuario {USUARIO}", ATLAS)
    assert _sin_credenciales(texto)
    assert "mongodb+srv://****@cluster0.abc123.mongodb.net" in texto
    assert enmascarar("timed out", "mongodb://localhost:27017") == "timed out"


def test_descripcion_dice_tipo_host_y_base():
    mongomock = pytest.importorskip("mongomock")
    db = mongomock.MongoClient(tz_aware=True)["tesis"]
    repo = RepositorioMongo(db, "cluster0.abc123.mongodb.net")
    assert (repo.tipo, repo.host) == ("atlas", "cluster0.abc123.mongodb.net")
    assert repo.descripcion == "mongo:atlas:cluster0.abc123.mongodb.net/tesis"
    assert RepositorioMongo(db, "localhost:27017").descripcion == "mongo:local:localhost:27017/tesis"


# ---------------------------------------------------------------- de dónde sale MONGO_URI

@pytest.fixture
def archivos_env(tmp_path, monkeypatch):
    """El .env de la raíz y backend/.env en una carpeta temporal, y sin MONGO_URI en el entorno."""
    raiz, backend = tmp_path / ".env", tmp_path / "backend.env"
    monkeypatch.setattr(config, "ARCHIVOS_ENV", (raiz, backend))
    monkeypatch.delenv("MONGO_URI", raising=False)
    return raiz, backend


def test_fuente_de_mongo_uri_con_la_prioridad_de_pydantic_settings(archivos_env, monkeypatch):
    raiz, backend = archivos_env
    assert fuente_de("MONGO_URI") == "default"
    raiz.write_text(f"MONGO_URI={ATLAS}\nMONGO_DB=tesis\n", encoding="utf-8")
    assert fuente_de("MONGO_URI") == "env_raiz"
    backend.write_text("OLLAMA_TIMEOUT_S=300\n", encoding="utf-8")  # otras variables no cuentan
    assert fuente_de("MONGO_URI") == "env_raiz"
    backend.write_text("mongo_uri=mongodb://localhost:27017\n", encoding="utf-8")
    assert fuente_de("MONGO_URI") == "env_backend"
    # pydantic-settings coincide: backend/.env gana al de la raíz
    assert Settings(_env_file=(raiz, backend)).mongo_uri == "mongodb://localhost:27017"
    monkeypatch.setenv("MONGO_URI", "mongodb://127.0.0.1:27017")
    assert fuente_de("MONGO_URI") == "variable_de_sistema"
    assert Settings(_env_file=(raiz, backend)).mongo_uri == "mongodb://127.0.0.1:27017"


def test_la_fuente_se_fija_al_crear_la_configuracion(archivos_env, monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://127.0.0.1:27017")
    s = Settings(_env_file=None)
    monkeypatch.delenv("MONGO_URI")
    assert s.fuente_mongo_uri == "variable_de_sistema"  # la de la URI en uso, aunque el entorno cambie


# ---------------------------------------------------------------- respaldo JSON

def test_respaldo_json_guarda_el_motivo_sin_credenciales(tmp_path, caplog):
    uri = f"mongodb://{USUARIO}:cl%40ve%2Fsecreta@127.0.0.1:1/"
    s = Settings(_env_file=None, mongo_uri=uri, mongo_timeout_ms=200, resultados_dir=str(tmp_path / "res"),
                 checkpoint_path="data/checkpoints.sqlite")
    with caplog.at_level(logging.WARNING, logger="app.db.repositorio"):
        repo = crear_repositorio(s)
    assert isinstance(repo, RepositorioJson)
    assert repo.error_mongo.startswith("ServerSelectionTimeoutError: ")
    assert "127.0.0.1:1" in caplog.text and _sin_credenciales(caplog.text)

    r = probar_conexion(repo, s)
    assert r == {
        "persistencia": "json", "tipo": None, "host": "127.0.0.1:1", "base": "tesis", "fuente_uri": s.fuente_mongo_uri,
        "ping_ms": None, "version_servidor": None, "colecciones": [], "prueba_escritura": None,
        "checkpoints": "sqlite:data/checkpoints.sqlite", "error": repo.error_mongo,
    }
    assert _sin_credenciales(json.dumps(r))


# ---------------------------------------------------------------- con Mongo (mongomock)

@pytest.fixture
def mongo(monkeypatch):
    """Mongo en memoria; mongomock no implementa `buildInfo`, se responde aquí."""
    mongomock = pytest.importorskip("mongomock")
    from mongomock.database import Database

    original = Database.command

    def command(self, orden, **kwargs):
        return {"version": "8.0.4", "ok": 1.0} if orden == "buildInfo" else original(self, orden, **kwargs)

    monkeypatch.setattr(Database, "command", command)
    db = mongomock.MongoClient(tz_aware=True)["tesis"]
    return RepositorioMongo(db, host_de_uri(ATLAS))


def test_probar_conexion_con_mongo(mongo):
    s = Settings(_env_file=None, mongo_uri=ATLAS)
    mongo.guardar_doc("proyectos", "P00", {"proyecto_id": "P00", "nombre": "General"})
    r = probar_conexion(mongo, s)
    assert (r["persistencia"], r["tipo"], r["host"], r["base"]) == ("mongo", "atlas", "cluster0.abc123.mongodb.net", "tesis")
    assert r["version_servidor"] == "8.0.4" and isinstance(r["ping_ms"], float) and r["error"] is None
    assert r["prueba_escritura"]["ok"] is True and r["prueba_escritura"]["error"] is None
    assert r["colecciones"] == [{"nombre": "proyectos", "documentos": 1}]
    # la prueba de escritura no deja rastro: ni documento ni colección
    assert COLECCION_PRUEBA not in mongo.db.list_collection_names()
    assert _sin_credenciales(json.dumps(r))


def test_probar_conexion_con_mongo_caido_responde_el_error_sin_credenciales(mongo, monkeypatch):
    from mongomock.database import Database
    from pymongo.errors import ServerSelectionTimeoutError

    def caido(self, orden, **kwargs):
        raise ServerSelectionTimeoutError(f"no responde {ATLAS} (usuario {USUARIO})")

    monkeypatch.setattr(Database, "command", caido)
    r = probar_conexion(mongo, Settings(_env_file=None, mongo_uri=ATLAS))
    assert r["persistencia"] == "mongo" and r["ping_ms"] is None and r["prueba_escritura"] is None
    assert r["error"].startswith("ServerSelectionTimeoutError: no responde mongodb+srv://****@cluster0")
    assert _sin_credenciales(json.dumps(r))
