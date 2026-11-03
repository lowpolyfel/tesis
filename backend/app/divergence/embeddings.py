"""Embeddings de las paráfrasis. Interfaz inyectable para poder probar sin Ollama."""
from __future__ import annotations

from typing import Protocol


class ProveedorEmbeddings(Protocol):
    modelo: str

    def vectorizar(self, textos: list[str]) -> list[list[float]]: ...


class EmbeddingsOllama:
    """`nomic-embed-text` (o el configurado) vía langchain-ollama. `timeout_s` acota cada
    llamada: sin él, un Ollama que acepta la conexión y no responde detiene la cola."""

    def __init__(self, modelo: str, base_url: str, timeout_s: float | None = None):
        from langchain_ollama import OllamaEmbeddings

        self.modelo = modelo
        self.base_url = base_url
        self.timeout_s = timeout_s
        self._cliente = OllamaEmbeddings(model=modelo, base_url=base_url, client_kwargs={"timeout": timeout_s})

    def vectorizar(self, textos: list[str]) -> list[list[float]]:
        import httpx

        try:
            return self._cliente.embed_documents(textos)
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Ollama ({self.modelo} en {self.base_url}) no respondió en {self.timeout_s} s "
                               "(OLLAMA_TIMEOUT_S)") from e


class EmbeddingsGemini:
    """Embeddings de la API de Gemini (Google AI Studio), sin Ollama: `batchEmbedContents`
    con `taskType=SEMANTIC_SIMILARITY`, que es para lo que se usan aquí (similitud coseno
    entre paráfrasis). Ojo: el umbral de divergencia se calibró con `nomic-embed-text`; con
    otro modelo las similitudes cambian y conviene recalibrar (ADR 0013)."""

    URL = "https://generativelanguage.googleapis.com/v1beta"
    LOTE = 100  # máximo de textos por petición

    def __init__(self, modelo: str, api_key: str | None, timeout_s: float | None = None,
                 dimensiones: int | None = None, cliente=None):
        import httpx

        if not api_key:
            raise ValueError("EMBEDDING_PROVEEDOR=google necesita LLM_API_KEY (clave de Google AI Studio)")
        self.modelo = modelo
        self.timeout_s = timeout_s
        self.dimensiones = dimensiones
        self._clave = api_key
        self._cliente = cliente or httpx.Client(timeout=timeout_s)

    def vectorizar(self, textos: list[str]) -> list[list[float]]:
        import httpx

        nombre = self.modelo if self.modelo.startswith("models/") else f"models/{self.modelo}"
        vectores: list[list[float]] = []
        for i in range(0, len(textos), self.LOTE):
            pedidos = []
            for t in textos[i:i + self.LOTE]:
                p = {"model": nombre, "content": {"parts": [{"text": t}]}, "taskType": "SEMANTIC_SIMILARITY"}
                if self.dimensiones:
                    p["outputDimensionality"] = self.dimensiones
                pedidos.append(p)
            try:
                r = self._cliente.post(f"{self.URL}/{nombre}:batchEmbedContents", json={"requests": pedidos},
                                       headers={"x-goog-api-key": self._clave})
            except httpx.TimeoutException as e:
                raise TimeoutError(f"Gemini ({self.modelo}) no respondió en {self.timeout_s} s") from e
            if r.status_code >= 400:  # el mensaje de Google, nunca la clave
                try:
                    detalle = r.json().get("error", {}).get("message", r.text[:200])
                except ValueError:
                    detalle = r.text[:200]
                raise RuntimeError(f"Gemini ({self.modelo}) respondió {r.status_code}: {detalle}")
            vectores.extend(e["values"] for e in r.json()["embeddings"])
        return vectores


def crear_embeddings(s) -> ProveedorEmbeddings:
    """Los embeddings que dice el .env: Ollama (por omisión) o Gemini."""
    if s.embedding_proveedor == "google":
        return EmbeddingsGemini(s.embedding_model, s.llm_api_key, s.ollama_timeout_s, s.embedding_dimensiones)
    return EmbeddingsOllama(s.embedding_model, s.ollama_base_url, s.ollama_timeout_s)
