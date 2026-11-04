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

**Gemini se satura** (503 UNAVAILABLE) o corta por cuota (429 RESOURCE_EXHAUSTED) con
frecuencia en el nivel gratuito. Para Google, cada llamada se reintenta hasta
GEMINI_REINTENTOS veces (máx. 5) solo ante esas dos respuestas, con espera exponencial y
jitter (`esperas`); si se agotan y hay GEMINI_FALLBACK_MODEL, se intenta una vez con ese
modelo. El cliente recuerda qué modelo respondió de verdad (`ultimo_uso`) para que la
corrida lo registre.
"""
from __future__ import annotations

import random
import re
import threading
import time
from collections.abc import Callable
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


def _error_de(r: httpx.Response) -> dict:
    """El objeto `error` de la respuesta. Gemini, en su endpoint compatible con OpenAI, lo manda
    dentro de una lista: [{"error": {"code": 503, "message": …, "status": "UNAVAILABLE"}}]."""
    try:
        datos = r.json()
    except ValueError:
        return {}
    if isinstance(datos, list) and datos and isinstance(datos[0], dict):
        datos = datos[0]
    if isinstance(datos, dict):
        error = datos.get("error", datos)
        return error if isinstance(error, dict) else {"message": str(error)}
    return {}


def _detalle(r: httpx.Response) -> str:
    error = _error_de(r)
    if not error:
        return r.text[:300]
    mensaje = error.get("message") or str(error)
    estado = error.get("status")
    return (f"{mensaje} ({estado})" if estado and estado not in mensaje else str(mensaje))[:300]


# ---------------------------------------------------------------- reintentos (Gemini)

REINTENTABLES = {503: "UNAVAILABLE", 429: "RESOURCE_EXHAUSTED"}
_dormir: Callable[[float], None] = time.sleep  # las pruebas lo sustituyen
_azar: Callable[[], float] = random.random


def reintentable(r: httpx.Response) -> bool:
    """Solo 503/UNAVAILABLE y 429/RESOURCE_EXHAUSTED: lo demás (400, 401, 404, 500…) no mejora
    con esperar."""
    if r.status_code in REINTENTABLES:
        return True
    return _error_de(r).get("status") in REINTENTABLES.values()


def espera(intento: int, base: float, tope: float, retry_after: str | None = None) -> float:
    """Espera antes del reintento `intento` (0, 1, 2…): exponencial con jitter «igual»
    (la mitad fija y la otra mitad al azar), sin pasar del tope. Si el servicio dice
    Retry-After en segundos, se respeta (también con tope)."""
    techo = min(tope, base * 2 ** intento)
    s = techo / 2 + _azar() * techo / 2
    if retry_after:
        try:
            s = max(s, float(retry_after))
        except ValueError:
            pass
    return min(s, tope) if tope else s


def con_reintentos(hacer: Callable[[], httpx.Response], reintentos: int, base: float, tope: float,
                   al_reintentar: Callable[[int, httpx.Response, float], None] | None = None
                   ) -> tuple[httpx.Response, int]:
    """Llama `hacer()` y la repite mientras responda 503/429, hasta `reintentos` veces.
    Devuelve (última respuesta, reintentos hechos)."""
    r = hacer()
    hechos = 0
    while reintentable(r) and hechos < reintentos:
        s = espera(hechos, base, tope, r.headers.get("retry-after"))
        if al_reintentar:
            al_reintentar(hechos + 1, r, s)
        _dormir(s)
        hechos += 1
        r = hacer()
    return r, hechos


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
    """/chat/completions. Con `reintentos` > 0 (Google), una respuesta 503 o 429 se repite con
    espera exponencial; si se agotan y hay `respaldo`, se intenta una vez con ese modelo."""

    def __init__(self, nombre: str, modelo: str, base_url: str, api_key: str | None, temperatura: float,
                 seed: int | None, timeout_s: float | None, etiqueta: str, *, reintentos: int = 0,
                 backoff_base_s: float = 1.0, backoff_max_s: float = 30.0, respaldo: str | None = None,
                 prefijo: str | None = None):
        self.nombre, self.modelo, self.base_url, self._clave = nombre, etiqueta, base_url.rstrip("/"), api_key
        self._modelo, self.temperatura, self.seed, self.timeout_s = modelo, temperatura, seed, timeout_s
        self.reintentos, self.backoff_base_s, self.backoff_max_s = reintentos, backoff_base_s, backoff_max_s
        self.respaldo = respaldo if respaldo and respaldo != modelo else None
        self._prefijo = prefijo
        self._uso = threading.local()

    def ultimo_uso(self) -> dict | None:
        """Qué respondió la última llamada de este hilo: {modelo, respaldo, original, reintentos}."""
        return getattr(self._uso, "valor", None)

    def _etiqueta(self, modelo: str) -> str:
        return f"{self._prefijo}:{modelo}" if self._prefijo else modelo

    def _una(self, modelo: str, prompt: PromptRenderizado, reintentos: int) -> tuple[httpx.Response, int]:
        cuerpo = {"model": modelo, "temperature": self.temperatura,
                  "messages": [{"role": "system", "content": prompt.sistema}, {"role": "user", "content": prompt.usuario}],
                  "response_format": {"type": "json_object"}}
        if self.seed is not None:
            cuerpo["seed"] = self.seed
        headers = {"Authorization": f"Bearer {self._clave}"} if self._clave else {}
        url = f"{self.base_url}/chat/completions"

        def hacer(c: dict) -> Callable[[], httpx.Response]:
            return lambda: _post(self.nombre, url, c, headers, self.timeout_s)

        r, hechos = con_reintentos(hacer(cuerpo), reintentos, self.backoff_base_s, self.backoff_max_s)
        if r.status_code == 400:  # hay servicios que no aceptan response_format o seed
            sin = {k: v for k, v in cuerpo.items() if k not in ("response_format", "seed")}
            r, mas = con_reintentos(hacer(sin), max(0, reintentos - hechos), self.backoff_base_s, self.backoff_max_s)
            hechos += mas
        return r, hechos

    def completar(self, prompt: PromptRenderizado, esquema: dict) -> str:
        self._uso.valor = None
        r, hechos = self._una(self._modelo, prompt, self.reintentos)
        usado, respaldo = self._modelo, False
        if r.status_code >= 400 and reintentable(r) and self.respaldo:
            primero = f"{r.status_code}: {_detalle(r)}"
            r, _ = self._una(self.respaldo, prompt, 0)  # una sola vez con el modelo de respaldo
            usado, respaldo = self.respaldo, True
            if r.status_code >= 400:
                raise FalloProveedor(f"{self.nombre} respondió {primero} tras {hechos} reintento(s), y el modelo de "
                                     f"respaldo {self.respaldo} respondió {r.status_code}: {_detalle(r)}")
        if r.status_code >= 400:
            tras = f" tras {hechos} reintento(s)" if hechos else ""
            raise FalloProveedor(f"{self.nombre} respondió {r.status_code}{tras}: {_detalle(r)}")
        self._uso.valor = {"modelo": self._etiqueta(usado), "respaldo": respaldo,
                           "original": self.modelo, "reintentos": hechos}
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


def crear_cliente_de(eleccion: dict, settings, *, con_respaldo: bool = True):
    """`eleccion`: {proveedor, modelo, base_url, api_key} ya resuelta (con la clave en claro).
    `con_respaldo=False` (prueba de modelos, probar una clave): sin GEMINI_FALLBACK_MODEL, porque
    lo que se mide es ese modelo."""
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
    extra = {}
    if p.id == "google":
        extra = {"reintentos": getattr(settings, "gemini_reintentos", 0),
                 "backoff_base_s": getattr(settings, "gemini_backoff_base_s", 1.0),
                 "backoff_max_s": getattr(settings, "gemini_backoff_max_s", 30.0),
                 "respaldo": (getattr(settings, "gemini_fallback_model", None) or None) if con_respaldo else None,
                 "prefijo": p.id}
    return ClienteCompatibleOpenAI(p.nombre, modelo, base, eleccion.get("api_key"), settings.llm_temperature,
                                   settings.llm_seed, settings.ollama_timeout_s, etiqueta, **extra)



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
