"""Proveedores de LLM que cada cuenta puede elegir por agente (ADR 0021).

El catálogo es fijo: cada proveedor dice qué campos pide (clave, URL) y qué modelos
sugiere. Los modelos cambian cada pocas semanas (Google retira gemini-2.5-flash el
20-10-2026), así que la lista buena es la del propio proveedor: `listar_modelos` la pide
con la clave de la cuenta. Las sugerencias son solo para cuando aún no hay clave. Los clientes hablan HTTP directo con `httpx`:

- `ClienteCompatibleOpenAI`: el formato /chat/completions, que usan OpenAI y casi
  todos los demás (Google Gemini lo ofrece en su endpoint «openai», Groq, OpenRouter,
  DeepSeek, Mistral y cualquier servidor compatible).
- `ClienteAnthropic`: /v1/messages de Anthropic.
- Ollama usa el cliente de siempre (`ClienteOllama`), con la URL que elija la cuenta.

Los errores nunca incluyen la clave: dicen el proveedor, el código HTTP y el mensaje
que respondió el servicio.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from .prompts import PromptRenderizado

ROLES = ("extractor", "clasificador", "critico", "modelador", "revisor")
NOMBRE_ROL = {"extractor": "Extractor", "clasificador": "Clasificador", "critico": "Crítico",
              "modelador": "Modelador", "revisor": "Revisor del contexto"}


@dataclass(frozen=True)
class Proveedor:
    id: str
    nombre: str
    tipo: str  # ollama | openai | anthropic
    base_url: str | None  # por omisión; None si la cuenta debe escribirla
    pide_clave: bool
    pide_url: bool
    modelos: tuple[str, ...]
    ayuda: str  # dónde se saca la clave
    url_ayuda: str | None = None

    def publico(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "tipo": self.tipo, "base_url": self.base_url,
                "pide_clave": self.pide_clave, "pide_url": self.pide_url, "modelos": list(self.modelos),
                "ayuda": self.ayuda, "url_ayuda": self.url_ayuda}


CATALOGO: tuple[Proveedor, ...] = (
    Proveedor("ollama", "Ollama (en tu máquina)", "ollama", "http://localhost:11434", False, True,
              ("qwen2.5:7b", "qwen2.5:14b", "llama3.1:8b", "mistral:7b"),
              "No pide clave: corre en tu máquina. Descarga el modelo con «ollama pull <modelo>».",
              "https://ollama.com/library"),
    Proveedor("google", "Google Gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai",
              True, False, ("gemini-3.6-flash", "gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-3.1-flash-lite"),
              "Crea una clave en Google AI Studio (Get API key).", "https://aistudio.google.com/apikey"),
    Proveedor("openai", "OpenAI", "openai", "https://api.openai.com/v1", True, False,
              ("gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna", "gpt-5.6-terra"),
              "Crea una clave en la plataforma de OpenAI (API keys).", "https://platform.openai.com/api-keys"),
    Proveedor("anthropic", "Anthropic Claude", "anthropic", "https://api.anthropic.com/v1", True, False,
              ("claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"),
              "Crea una clave en la consola de Anthropic (API keys).", "https://console.anthropic.com/settings/keys"),
    Proveedor("groq", "Groq", "openai", "https://api.groq.com/openai/v1", True, False,
              ("llama-3.3-70b-versatile", "openai/gpt-oss-120b"),
              "Crea una clave en la consola de Groq.", "https://console.groq.com/keys"),
    Proveedor("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", True, False,
              ("google/gemini-2.5-flash", "meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-chat"),
              "Una clave de OpenRouter da acceso a modelos de varios proveedores.", "https://openrouter.ai/keys"),
    Proveedor("deepseek", "DeepSeek", "openai", "https://api.deepseek.com/v1", True, False,
              ("deepseek-chat",), "Crea una clave en la plataforma de DeepSeek.", "https://platform.deepseek.com/api_keys"),
    Proveedor("mistral", "Mistral", "openai", "https://api.mistral.ai/v1", True, False,
              ("mistral-large-latest", "mistral-small-latest"),
              "Crea una clave en la consola de Mistral.", "https://console.mistral.ai/api-keys"),
    Proveedor("compatible", "Otro compatible con OpenAI", "openai", None, False, True, (),
              "Cualquier servidor con /chat/completions (LM Studio, vLLM…). La clave es opcional."),
)
POR_ID = {p.id: p for p in CATALOGO}


class FalloProveedor(RuntimeError):
    """El servicio respondió con error o no respondió. El mensaje nunca lleva la clave."""


def _detalle(r: httpx.Response) -> str:
    try:
        datos = r.json()
        error = datos.get("error", datos) if isinstance(datos, dict) else datos
        mensaje = error.get("message") if isinstance(error, dict) else None
        return str(mensaje or error)[:300]
    except ValueError:
        return r.text[:300]


def _post(nombre: str, url: str, cuerpo: dict, headers: dict, timeout: float | None) -> httpx.Response:
    try:
        r = httpx.post(url, json=cuerpo, headers=headers, timeout=timeout)
    except httpx.TimeoutException as e:
        raise TimeoutError(f"{nombre} no respondió en {timeout} s") from e
    except httpx.HTTPError as e:
        raise FalloProveedor(f"No se pudo conectar con {nombre} ({type(e).__name__})") from e
    if r.status_code in (401, 403):
        raise FalloProveedor(f"{nombre} rechazó la clave ({r.status_code}): {_detalle(r)}")
    return r


class ClienteCompatibleOpenAI:
    def __init__(self, nombre: str, modelo: str, base_url: str, api_key: str | None, temperatura: float,
                 seed: int | None, timeout_s: float | None, etiqueta: str):
        self.nombre, self.modelo, self.base_url, self._clave = nombre, etiqueta, base_url.rstrip("/"), api_key
        self._modelo, self.temperatura, self.seed, self.timeout_s = modelo, temperatura, seed, timeout_s

    def completar(self, prompt: PromptRenderizado, esquema: dict) -> str:
        cuerpo = {"model": self._modelo, "temperature": self.temperatura,
                  "messages": [{"role": "system", "content": prompt.sistema}, {"role": "user", "content": prompt.usuario}],
                  "response_format": {"type": "json_object"}}
        if self.seed is not None:
            cuerpo["seed"] = self.seed
        headers = {"Authorization": f"Bearer {self._clave}"} if self._clave else {}
        url = f"{self.base_url}/chat/completions"
        r = _post(self.nombre, url, cuerpo, headers, self.timeout_s)
        if r.status_code == 400:  # hay servicios que no aceptan response_format o seed
            cuerpo = {k: v for k, v in cuerpo.items() if k not in ("response_format", "seed")}
            r = _post(self.nombre, url, cuerpo, headers, self.timeout_s)
        if r.status_code >= 400:
            raise FalloProveedor(f"{self.nombre} respondió {r.status_code}: {_detalle(r)}")
        try:
            return r.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise FalloProveedor(f"{self.nombre} respondió algo inesperado: {r.text[:200]}") from e


class ClienteAnthropic:
    def __init__(self, modelo: str, base_url: str, api_key: str | None, temperatura: float,
                 timeout_s: float | None, etiqueta: str):
        self.modelo, self._modelo, self.base_url, self._clave = etiqueta, modelo, base_url.rstrip("/"), api_key
        self.temperatura, self.timeout_s = temperatura, timeout_s

    def completar(self, prompt: PromptRenderizado, esquema: dict) -> str:
        cuerpo = {"model": self._modelo, "max_tokens": 4096, "temperature": self.temperatura, "system": prompt.sistema,
                  "messages": [{"role": "user", "content": prompt.usuario}]}
        headers = {"x-api-key": self._clave or "", "anthropic-version": "2023-06-01"}
        r = _post("Anthropic", f"{self.base_url}/messages", cuerpo, headers, self.timeout_s)
        if r.status_code >= 400:
            raise FalloProveedor(f"Anthropic respondió {r.status_code}: {_detalle(r)}")
        try:
            return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
        except (ValueError, KeyError, TypeError) as e:
            raise FalloProveedor(f"Anthropic respondió algo inesperado: {r.text[:200]}") from e


def crear_cliente_de(eleccion: dict, settings):
    """`eleccion`: {proveedor, modelo, base_url, api_key} ya resuelta (con la clave en claro)."""
    from .cliente import ClienteOllama

    p = POR_ID[eleccion["proveedor"]]
    modelo = eleccion["modelo"]
    base = eleccion.get("base_url") or p.base_url
    if not base:
        raise FalloProveedor(f"Falta la URL de {p.nombre}")
    etiqueta = modelo if p.id == "ollama" else f"{p.id}:{modelo}"
    if p.tipo == "ollama":
        return ClienteOllama(modelo, base, settings.llm_temperature, settings.llm_seed, settings.ollama_timeout_s)
    if p.tipo == "anthropic":
        return ClienteAnthropic(modelo, base, eleccion.get("api_key"), settings.llm_temperature,
                                settings.ollama_timeout_s, etiqueta)
    return ClienteCompatibleOpenAI(p.nombre, modelo, base, eleccion.get("api_key"), settings.llm_temperature,
                                   settings.llm_seed, settings.ollama_timeout_s, etiqueta)



# lo que no sirve para generar texto (embeddings, audio, imagen, moderación…)
_NO_CHAT = re.compile(r"embed|whisper|tts|dall-e|image|imagen|veo|audio|realtime|transcribe|moderation|search|"
                      r"rerank|guard|davinci|babbage|sora|lyria", re.IGNORECASE)


def _get(nombre: str, url: str, headers: dict, timeout: float = 20) -> dict:
    try:
        r = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError as e:
        raise FalloProveedor(f"No se pudo conectar con {nombre} ({type(e).__name__})") from e
    if r.status_code in (401, 403):
        raise FalloProveedor(f"{nombre} rechazó la clave ({r.status_code}): {_detalle(r)}")
    if r.status_code >= 400:
        raise FalloProveedor(f"{nombre} respondió {r.status_code}: {_detalle(r)}")
    try:
        return r.json()
    except ValueError as e:
        raise FalloProveedor(f"{nombre} respondió algo inesperado: {r.text[:200]}") from e


def listar_modelos(eleccion: dict) -> list[dict]:
    """Los modelos de texto que la clave puede usar ahora: [{id, nombre}]. `eleccion`:
    {proveedor, base_url?, api_key?}. Lanza FalloProveedor (sin la clave en el mensaje)."""
    p = POR_ID[eleccion["proveedor"]]
    base = (eleccion.get("base_url") or p.base_url or "").rstrip("/")
    clave = eleccion.get("api_key")
    if not base:
        raise FalloProveedor(f"Falta la URL de {p.nombre}")
    if p.tipo == "ollama":
        datos = _get(p.nombre, f"{base}/api/tags", {})
        modelos = [{"id": m["name"], "nombre": m["name"]} for m in datos.get("models", [])]
    elif p.id == "google":  # la API nativa dice qué modelos generan texto (generateContent)
        datos = _get(p.nombre, "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
                     {"x-goog-api-key": clave or ""})
        modelos = [{"id": m["name"].removeprefix("models/"), "nombre": m.get("displayName") or m["name"]}
                   for m in datos.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    elif p.tipo == "anthropic":
        datos = _get(p.nombre, f"{base}/models?limit=1000", {"x-api-key": clave or "", "anthropic-version": "2023-06-01"})
        modelos = [{"id": m["id"], "nombre": m.get("display_name") or m["id"]} for m in datos.get("data", [])]
    else:
        datos = _get(p.nombre, f"{base}/models", {"Authorization": f"Bearer {clave}"} if clave else {})
        filas = sorted(datos.get("data", []), key=lambda m: -(m.get("created") or 0))  # los más nuevos primero
        modelos = [{"id": m["id"], "nombre": m.get("name") or m["id"]} for m in filas]
    return [m for m in modelos if not _NO_CHAT.search(m["id"])]
