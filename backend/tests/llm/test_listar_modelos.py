"""La lista real de modelos de cada proveedor (ADR 0021): Gemini nativa (solo los que generan
texto), Anthropic, OpenAI y compatibles (sin embeddings ni audio), Ollama; y la ruta."""
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.llm.proveedores as prov
from app.api.routes import modelos
from app.llm.proveedores import FalloProveedor, listar_modelos
from tests.escenarios import montar
from tests.fakes import USUARIO_PRUEBA, como_usuario


class Get:
    def __init__(self, estado, cuerpo):
        self.estado, self.cuerpo, self.llamadas = estado, cuerpo, []

    def __call__(self, url, headers=None, timeout=None):
        self.llamadas.append((url, headers))
        return httpx.Response(self.estado, json=self.cuerpo, request=httpx.Request("GET", url))


def test_gemini_solo_los_que_generan_texto(monkeypatch):
    get = Get(200, {"models": [
        {"name": "models/gemini-3.6-flash", "displayName": "Gemini 3.6 Flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/imagen-4", "supportedGenerationMethods": ["predict"]}]})
    monkeypatch.setattr(prov.httpx, "get", get)
    assert listar_modelos({"proveedor": "google", "api_key": "k"}) == [{"id": "gemini-3.6-flash", "nombre": "Gemini 3.6 Flash"}]
    url, headers = get.llamadas[0]
    assert url.startswith("https://generativelanguage.googleapis.com/v1beta/models") and "k" not in url
    assert headers == {"x-goog-api-key": "k"}


def test_openai_sin_embeddings_ni_audio_y_los_nuevos_primero(monkeypatch):
    monkeypatch.setattr(prov.httpx, "get", Get(200, {"data": [
        {"id": "gpt-5.6-terra", "created": 1}, {"id": "text-embedding-3-large", "created": 9},
        {"id": "gpt-6-astra", "created": 5}, {"id": "whisper-1", "created": 3}]}))
    assert [m["id"] for m in listar_modelos({"proveedor": "openai", "api_key": "k"})] == ["gpt-6-astra", "gpt-5.6-terra"]


def test_anthropic_y_ollama(monkeypatch):
    get = Get(200, {"data": [{"id": "claude-sonnet-5-5", "display_name": "Claude Sonnet 5.5"}]})
    monkeypatch.setattr(prov.httpx, "get", get)
    assert listar_modelos({"proveedor": "anthropic", "api_key": "k"}) == [{"id": "claude-sonnet-5-5", "nombre": "Claude Sonnet 5.5"}]
    assert get.llamadas[0][1]["x-api-key"] == "k"
    monkeypatch.setattr(prov.httpx, "get", Get(200, {"models": [{"name": "qwen2.5:7b"}, {"name": "nomic-embed-text:latest"}]}))
    assert [m["id"] for m in listar_modelos({"proveedor": "ollama", "base_url": "http://x:11434"})] == ["qwen2.5:7b"]


def test_clave_rechazada(monkeypatch):
    monkeypatch.setattr(prov.httpx, "get", Get(400, {"error": {"message": "API key not valid"}}))
    with pytest.raises(FalloProveedor, match="400: API key not valid"):
        listar_modelos({"proveedor": "google", "api_key": "secreta-123"})


def test_ruta(tmp_path, analizador, monkeypatch):
    srv, _, _ = montar(tmp_path, analizador, {}, clave_cifrado_path=str(tmp_path / "k.key"))
    app = como_usuario(FastAPI())
    app.include_router(modelos.router)
    app.state.servicio = srv
    c = TestClient(app)
    assert c.post("/cuenta/modelos/listar", json={"proveedor": "google"}).json() == {
        "modelos": [], "error": "Falta la clave de Google Gemini."}
    srv.perfiles.guardar(USUARIO_PRUEBA.usuario_id, {}, {"google": {"api_key": "guardada-1"}})
    vistas = []
    monkeypatch.setattr(modelos, "listar_modelos", lambda e: vistas.append(e) or [{"id": "gemini-3.6-flash", "nombre": "x"}])
    r = c.post("/cuenta/modelos/listar", json={"proveedor": "google"}).json()
    assert r == {"modelos": [{"id": "gemini-3.6-flash", "nombre": "x"}], "error": None} and vistas[0]["api_key"] == "guardada-1"
