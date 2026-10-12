"""Preparación antes de analizar (GET /preparacion, POST /preparacion/cargar).

La escena en vivo la recorre antes de empezar, con la esfera grande al centro:
¿responde la base de datos?, ¿responde Ollama?, ¿están descargados los modelos que
usa el análisis? y, si alguno no está en memoria, lo precarga: la primera llamada a
un modelo frío tarda (Ollama lo lee del disco), y así ya está listo cuando el primer
requisito llega al Extractor.

Solo se precargan los modelos configurados: la API no carga cualquier modelo que se
le pida.
"""
from __future__ import annotations

from time import perf_counter

import httpx

from app.config import Settings
from app.db.repositorio import RepositorioMongo, enmascarar


class PreparacionFallida(Exception):
    """Ollama no respondió o no pudo cargar el modelo."""


def _ms(desde: float) -> float:
    return round((perf_counter() - desde) * 1000, 1)


def modelos_del_analisis(s: Settings) -> list[dict]:
    """Un renglón por modelo distinto que usa el grafo, con los roles que lo usan."""
    usos = [("extractor", "ollama", s.extractor_model, "generacion"),
            ("clasificador", "ollama", s.clasificador_model, "generacion"),
            ("critico", s.critico_provider, s.critico_model, "generacion"),
            ("modelador", "ollama", s.modelador_model, "generacion"),
            ("embeddings", "ollama", s.embedding_model, "embeddings")]
    modelos: dict[tuple, dict] = {}
    for rol, proveedor, modelo, tipo in usos:
        m = modelos.setdefault((proveedor, modelo, tipo),
                               {"modelo": modelo, "proveedor": proveedor, "tipo": tipo, "roles": []})
        m["roles"].append(rol)
    return list(modelos.values())


def _esta(modelo: str, nombres: set[str]) -> bool:
    """Ollama guarda «nomic-embed-text» como «nomic-embed-text:latest»."""
    return modelo in nombres or f"{modelo}:latest" in nombres


def estado_base(repo) -> dict:
    if not isinstance(repo, RepositorioMongo):
        return {"ok": True, "tipo": "json", "host": None, "ms": None, "error": None,
                "aviso": "Sin MongoDB: los resultados se guardan en archivos JSON de esta máquina."}
    from pymongo.errors import PyMongoError

    t0 = perf_counter()
    try:
        repo.db.client.admin.command("ping")
    except PyMongoError as e:
        return {"ok": False, "tipo": repo.tipo, "host": repo.host, "ms": None, "aviso": None,
                "error": enmascarar(f"{type(e).__name__}: {e}", "")}
    return {"ok": True, "tipo": repo.tipo, "host": repo.host, "ms": _ms(t0), "error": None, "aviso": None}


def estado_modelos(s: Settings, cliente: httpx.Client) -> dict:
    modelos = modelos_del_analisis(s)
    url = s.ollama_base_url.rstrip("/")
    ollama = None
    instalados: set[str] = set()
    cargados: set[str] = set()
    if any(m["proveedor"] == "ollama" for m in modelos):
        t0 = perf_counter()
        try:
            r = cliente.get(f"{url}/api/tags", timeout=5)
            r.raise_for_status()
            instalados = {m["name"] for m in r.json().get("models", [])}
            ollama = {"ok": True, "url": url, "ms": _ms(t0), "error": None}
        except (httpx.HTTPError, ValueError) as e:
            ollama = {"ok": False, "url": url, "ms": None,
                      "error": f"Ollama no responde en {url} ({type(e).__name__}). Arráncalo con «ollama serve»."}
        if ollama["ok"]:
            try:  # qué modelos ya están en memoria (si falla, se precargan todos)
                cargados = {m["name"] for m in cliente.get(f"{url}/api/ps", timeout=5).json().get("models", [])}
            except (httpx.HTTPError, ValueError):
                cargados = set()
    for m in modelos:
        if m["proveedor"] == "ollama":
            m["disponible"] = bool(ollama and ollama["ok"] and _esta(m["modelo"], instalados))
            m["cargado"] = m["disponible"] and _esta(m["modelo"], cargados)
            m["error"] = (None if m["disponible"] or not (ollama and ollama["ok"])
                          else f"Falta el modelo en Ollama: corre «ollama pull {m['modelo']}».")
        else:  # servicio externo: no hay nada que cargar; basta la clave
            m["disponible"] = bool(s.critico_api_key)
            m["cargado"] = m["disponible"]
            m["error"] = None if m["disponible"] else "Falta CRITICO_API_KEY en el .env."
    return {"ollama": ollama, "modelos": modelos}


def preparacion(repo, s: Settings, cliente: httpx.Client | None = None) -> dict:
    """Estado de todo lo que necesita el análisis. `listo`: se puede empezar."""
    with (cliente or httpx.Client()) as c:
        modelos = estado_modelos(s, c)
    base = estado_base(repo)
    listo = base["ok"] and all(m["disponible"] for m in modelos["modelos"])
    return {"listo": listo, "base": base, **modelos}


def cargar_modelo(s: Settings, modelo: str, cliente: httpx.Client | None = None) -> dict:
    """Deja en memoria un modelo de Ollama de los que usa el análisis. ValueError si no es
    uno de ellos; PreparacionFallida si Ollama no responde o no lo puede cargar."""
    m = next((x for x in modelos_del_analisis(s) if x["modelo"] == modelo and x["proveedor"] == "ollama"), None)
    if m is None:
        raise ValueError(f"«{modelo}» no es un modelo de Ollama del análisis")
    url = s.ollama_base_url.rstrip("/")
    t0 = perf_counter()
    try:
        with (cliente or httpx.Client()) as c:
            if m["tipo"] == "embeddings":
                r = c.post(f"{url}/api/embed", json={"model": modelo, "input": "carga"}, timeout=s.ollama_timeout_s)
            else:  # sin prompt, Ollama solo carga el modelo en memoria
                r = c.post(f"{url}/api/generate", json={"model": modelo}, timeout=s.ollama_timeout_s)
            r.raise_for_status()
    except httpx.HTTPError as e:
        raise PreparacionFallida(f"Ollama no pudo cargar {modelo} ({type(e).__name__}: {e})") from e
    return {"modelo": modelo, "ms": _ms(t0)}
