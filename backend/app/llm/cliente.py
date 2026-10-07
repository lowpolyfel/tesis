"""Clientes de LLM. Cada agente recibe el suyo según la configuración.

Ollama es el proveedor por defecto. Anthropic y OpenAI se importan solo si se
eligen como CRITICO_PROVIDER; sus paquetes no están en requirements.
"""
from __future__ import annotations

import json
from typing import Protocol

from .prompts import PromptRenderizado


class ClienteLLM(Protocol):
    modelo: str

    def completar(self, prompt: PromptRenderizado, esquema: dict) -> str:
        """Devuelve el texto crudo que produjo el modelo."""
        ...


class ClienteOllama:
    def __init__(self, modelo: str, base_url: str, temperatura: float, seed: int | None, timeout_s: float | None = None):
        self.modelo = modelo
        self.base_url = base_url
        self.temperatura = temperatura
        self.seed = seed
        self.timeout_s = timeout_s

    def completar(self, prompt: PromptRenderizado, esquema: dict) -> str:
        import httpx
        from langchain_ollama import ChatOllama

        # `format` con el JSON schema restringe la decodificación de Ollama al esquema
        chat = ChatOllama(
            model=self.modelo,
            base_url=self.base_url,
            temperature=self.temperatura,
            seed=self.seed,
            format=esquema,
            client_kwargs={"timeout": self.timeout_s},
        )
        try:
            respuesta = chat.invoke([("system", prompt.sistema), ("human", prompt.usuario)])
        except httpx.TimeoutException as e:  # el nodo lo registra como error en la traza
            raise TimeoutError(f"Ollama ({self.modelo} en {self.base_url}) no respondió en {self.timeout_s} s "
                               "(OLLAMA_TIMEOUT_S)") from e
        return respuesta.content if isinstance(respuesta.content, str) else json.dumps(respuesta.content)


class _ClienteChatGenerico:
    """Proveedores por API: el esquema va en el prompt (ya lo agrega `estructurado`)."""

    paquete: str
    clase: str

    def __init__(self, modelo: str, api_key: str | None, temperatura: float):
        try:
            modulo = __import__(self.paquete, fromlist=[self.clase])
        except ImportError as e:
            raise RuntimeError(
                f"CRITICO_PROVIDER requiere el paquete '{self.paquete.replace('_', '-')}'. "
                f"Instálalo con: pip install {self.paquete.replace('_', '-')}"
            ) from e
        self.modelo = modelo
        self._chat = getattr(modulo, self.clase)(model=modelo, api_key=api_key, temperature=temperatura)

    def completar(self, prompt: PromptRenderizado, esquema: dict) -> str:
        respuesta = self._chat.invoke([("system", prompt.sistema), ("human", prompt.usuario)])
        return respuesta.content if isinstance(respuesta.content, str) else json.dumps(respuesta.content)


class ClienteAnthropic(_ClienteChatGenerico):
    paquete, clase = "langchain_anthropic", "ChatAnthropic"


class ClienteOpenAI(_ClienteChatGenerico):
    paquete, clase = "langchain_openai", "ChatOpenAI"


def crear_cliente(proveedor: str, modelo: str, settings) -> ClienteLLM:
    if proveedor == "ollama":
        return ClienteOllama(modelo, settings.ollama_base_url, settings.llm_temperature, settings.llm_seed,
                             settings.ollama_timeout_s)
    if proveedor == "anthropic":
        return ClienteAnthropic(modelo, settings.critico_api_key, settings.llm_temperature)
    if proveedor == "openai":
        return ClienteOpenAI(modelo, settings.critico_api_key, settings.llm_temperature)
    raise ValueError(f"proveedor desconocido: {proveedor}")
