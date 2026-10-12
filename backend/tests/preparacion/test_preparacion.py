"""Preparación antes de analizar, con un Ollama falso (httpx.MockTransport)."""
import json

import app.preparacion as modulo
import httpx
import pytest
from app.api.main import create_app
from app.config import Settings
from app.db import RepositorioJson, RepositorioMongo
from app.preparacion import (
    PreparacionFallida,
    cargar_modelo,
    modelos_del_analisis,
    preparacion,
)
from fastapi.testclient import TestClient

from tests.escenarios import guiones_sesion_cercana, montar
from tests.fakes import como_usuario

ClienteReal = httpx.Client  # las pruebas de la ruta reemplazan httpx.Client


def ollama_falso(instalados=("qwen2.5:7b", "nomic-embed-text:latest"), cargados=("qwen2.5:7b",), caido=False,
                 estado_carga=200):
    """Cliente httpx contra un Ollama de mentira; `pedidos` guarda (método, ruta, cuerpo)."""
    pedidos = []

    def responder(req: httpx.Request) -> httpx.Response:
        if caido:
            raise httpx.ConnectError("conexión rechazada", request=req)
        cuerpo = json.loads(req.content) if req.content else None
        pedidos.append((req.method, req.url.path, cuerpo))
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": n} for n in instalados]})
        if req.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [{"name": n} for n in cargados]})
        if req.url.path in ("/api/generate", "/api/embed"):
            return httpx.Response(estado_carga, json={"done": True})
        return httpx.Response(404)

    cliente = ClienteReal(transport=httpx.MockTransport(responder))
    cliente.pedidos = pedidos
    return cliente


@pytest.fixture
def s():
    return Settings(_env_file=None)


def test_un_renglon_por_modelo_con_sus_roles(s):
    assert modelos_del_analisis(s) == [
        {"modelo": "qwen2.5:7b", "proveedor": "ollama", "tipo": "generacion",
         "roles": ["extractor", "clasificador", "critico", "modelador"]},
        {"modelo": "nomic-embed-text", "proveedor": "ollama", "tipo": "embeddings", "roles": ["embeddings"]},
    ]


def test_todo_listo_y_que_falta_cargar(s, tmp_path):
    r = preparacion(RepositorioJson(tmp_path), s, ollama_falso())
    assert r["listo"] and r["ollama"]["ok"]
    assert r["base"]["tipo"] == "json" and r["base"]["aviso"]
    assert [(m["modelo"], m["disponible"], m["cargado"]) for m in r["modelos"]] == [
        ("qwen2.5:7b", True, True), ("nomic-embed-text", True, False)]


def test_ollama_caido_o_modelo_sin_descargar(s, tmp_path):
    r = preparacion(RepositorioJson(tmp_path), s, ollama_falso(caido=True))
    assert not r["listo"] and not r["ollama"]["ok"] and "ollama serve" in r["ollama"]["error"]
    assert not any(m["disponible"] for m in r["modelos"])
    r = preparacion(RepositorioJson(tmp_path), s, ollama_falso(instalados=("qwen2.5:7b",)))
    falta = next(m for m in r["modelos"] if m["modelo"] == "nomic-embed-text")
    assert not r["listo"] and "ollama pull nomic-embed-text" in falta["error"]


def test_critico_externo_solo_necesita_su_clave(tmp_path):
    sin = Settings(_env_file=None, critico_provider="anthropic", critico_model="claude-x")
    critico = lambda r: next(m for m in r["modelos"] if m["proveedor"] == "anthropic")
    r = preparacion(RepositorioJson(tmp_path), sin, ollama_falso())
    assert not r["listo"] and "CRITICO_API_KEY" in critico(r)["error"]
    con = Settings(_env_file=None, critico_provider="anthropic", critico_model="claude-x", critico_api_key="k")
    assert critico(preparacion(RepositorioJson(tmp_path), con, ollama_falso()))["disponible"]


def test_base_mongo_con_ping():
    mongomock = pytest.importorskip("mongomock")
    repo = RepositorioMongo(mongomock.MongoClient(tz_aware=True)["tesis"], "localhost:27017")
    base = modulo.estado_base(repo)
    assert (base["ok"], base["tipo"], base["host"]) == (True, "local", "localhost:27017") and base["ms"] is not None


def test_precargar_solo_modelos_del_analisis(s):
    c = ollama_falso()
    assert cargar_modelo(s, "qwen2.5:7b", c)["modelo"] == "qwen2.5:7b"
    assert c.pedidos[-1] == ("POST", "/api/generate", {"model": "qwen2.5:7b"})  # sin prompt: solo carga
    c = ollama_falso()
    cargar_modelo(s, "nomic-embed-text", c)
    assert c.pedidos[-1][:2] == ("POST", "/api/embed")
    with pytest.raises(ValueError):
        cargar_modelo(s, "llama-cualquiera", ollama_falso())
    with pytest.raises(PreparacionFallida):
        cargar_modelo(s, "qwen2.5:7b", ollama_falso(estado_carga=500))


def test_rutas(tmp_path, analizador, monkeypatch):
    srv, _, _ = montar(tmp_path, analizador, guiones_sesion_cercana())
    assert TestClient(create_app(srv)).get("/preparacion").status_code == 401
    monkeypatch.setattr(modulo.httpx, "Client", lambda: ollama_falso())
    c = TestClient(como_usuario(create_app(srv)))
    assert c.get("/preparacion").json()["listo"] is True
    assert c.post("/preparacion/cargar", json={"modelo": "nomic-embed-text"}).status_code == 200
    assert c.post("/preparacion/cargar", json={"modelo": "otro"}).status_code == 422
