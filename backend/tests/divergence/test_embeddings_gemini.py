"""Embeddings por la API de Gemini (servidor sin Ollama)."""
import json

import httpx
import pytest

from app.config import Settings
from app.divergence import EmbeddingsGemini, EmbeddingsOllama, crear_embeddings


def _cliente(pedidos: list, estado: int = 200):
    def responder(request: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(request.content)
        pedidos.append((request, cuerpo))
        if estado != 200:
            return httpx.Response(estado, json={"error": {"message": "API key not valid"}})
        return httpx.Response(200, json={"embeddings": [{"values": [float(i), 1.0]} for i, _ in
                                                        enumerate(cuerpo["requests"])]})
    return httpx.Client(transport=httpx.MockTransport(responder))


def test_vectoriza_por_lotes_con_la_clave_en_el_encabezado():
    pedidos = []
    e = EmbeddingsGemini("gemini-embedding-001", "clave-secreta", cliente=_cliente(pedidos), dimensiones=768)
    vectores = e.vectorizar([f"texto {i}" for i in range(150)])
    assert len(vectores) == 150
    assert [len(c["requests"]) for _, c in pedidos] == [100, 50]
    request, cuerpo = pedidos[0]
    assert request.url.path.endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert request.headers["x-goog-api-key"] == "clave-secreta"
    assert "clave-secreta" not in str(request.url)
    primero = cuerpo["requests"][0]
    assert primero["taskType"] == "SEMANTIC_SIMILARITY"
    assert primero["outputDimensionality"] == 768
    assert primero["content"]["parts"][0]["text"] == "texto 0"


def test_un_error_de_google_no_incluye_la_clave():
    e = EmbeddingsGemini("gemini-embedding-001", "clave-secreta", cliente=_cliente([], estado=400))
    with pytest.raises(RuntimeError) as info:
        e.vectorizar(["a"])
    assert "API key not valid" in str(info.value)
    assert "clave-secreta" not in str(info.value)


def test_sin_clave_no_arranca():
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        EmbeddingsGemini("gemini-embedding-001", None)


def test_el_env_decide_el_proveedor_de_embeddings():
    assert isinstance(crear_embeddings(Settings(_env_file=None)), EmbeddingsOllama)
    s = Settings(_env_file=None, embedding_proveedor="google", embedding_model="gemini-embedding-001", llm_api_key="k")
    assert isinstance(crear_embeddings(s), EmbeddingsGemini)
