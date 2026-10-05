"""Embeddings de las paráfrasis. Interfaz inyectable para poder probar sin Ollama."""
from __future__ import annotations

from typing import Protocol


class ProveedorEmbeddings(Protocol):
    modelo: str

    def vectorizar(self, textos: list[str]) -> list[list[float]]: ...


class EmbeddingsOllama:
    """`nomic-embed-text` (o el configurado) vía langchain-ollama."""

    def __init__(self, modelo: str, base_url: str):
        from langchain_ollama import OllamaEmbeddings

        self.modelo = modelo
        self._cliente = OllamaEmbeddings(model=modelo, base_url=base_url)

    def vectorizar(self, textos: list[str]) -> list[list[float]]:
        return self._cliente.embed_documents(textos)
