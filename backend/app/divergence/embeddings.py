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
