"""Qué mensajes de una traza cuentan y cómo se normaliza su configuración.

Funciones puras sobre `Traza`: no llaman a ningún modelo ni al repositorio.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import Mensaje, TipoMensaje, Traza
from app.nlp import normalizar

# Se emiten una vez por requisito; si aparecen dos veces es por un nodo reejecutado
_UNO_POR_REQUISITO = {TipoMensaje.EXTRACCION, TipoMensaje.FILTRADO, TipoMensaje.INTERPRETACIONES,
                      TipoMensaje.SOLICITUD_VALIDACION, TipoMensaje.VALIDACION}


def clave(termino: str | None) -> str | None:
    """Un término se identifica por su forma normalizada, como en el grafo."""
    return normalizar(termino) if termino else None


def alcance_formalizacion(payload: dict) -> str:
    """`termino` o `requisito`. Las trazas anteriores al ADR 0010 no traen `alcance`:
    las que traen `entrada_lel` son por término."""
    return payload.get("alcance") or ("termino" if "entrada_lel" in payload else "requisito")


def clave_mensaje(m: Mensaje) -> tuple | None:
    """Dos mensajes con la misma clave dicen lo mismo; None si nunca se reemplaza (errores)."""
    p = m.payload or {}
    if m.tipo == TipoMensaje.ERROR:
        return None
    if m.tipo in _UNO_POR_REQUISITO:
        return (m.tipo,)
    if m.tipo == TipoMensaje.FORMALIZACION:
        alcance = alcance_formalizacion(p)
        return (m.tipo, alcance, clave(p.get("termino")) if alcance == "termino" else None)
    return (m.tipo, m.ronda, clave(p.get("termino")))  # similitud, objecion, refinamiento, consenso, arbitraje


def mensajes_efectivos(traza: Traza) -> tuple[list[Mensaje], int]:
    """Los mensajes que cuentan, en orden de secuencia, y cuántos se descartaron.

    Un nodo que continúa tras un reinicio se vuelve a ejecutar completo y repite
    sus mensajes (ADR 0008). Cuenta el último de cada clave, que es el que quedó en
    el estado del grafo; las similitudes iniciales anteriores a la última
    clasificación también quedan reemplazadas. Los errores nunca se descartan.
    """
    ordenados = sorted(traza.mensajes, key=lambda m: m.secuencia)
    ultimo: dict[tuple, int] = {}
    for m in ordenados:
        if (k := clave_mensaje(m)) is not None:
            ultimo[k] = m.secuencia
    clasificacion = ultimo.get((TipoMensaje.INTERPRETACIONES,), 0)

    def cuenta(m: Mensaje) -> bool:
        k = clave_mensaje(m)
        if k is None:
            return True
        if m.tipo == TipoMensaje.SIMILITUD and m.ronda == 0 and m.secuencia < clasificacion:
            return False
        return ultimo[k] == m.secuencia

    efectivos = [m for m in ordenados if cuenta(m)]
    return efectivos, len(ordenados) - len(efectivos)


def ultimo(mensajes: list[Mensaje], tipo: TipoMensaje) -> Mensaje | None:
    return next((m for m in reversed(mensajes) if m.tipo == tipo), None)


def utc(t: datetime) -> datetime:
    """Mongo puede devolver fechas sin zona; todas se guardan en UTC."""
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def duracion_ms(traza: Traza, m: Mensaje) -> int:
    """Desde la última transición anterior al mensaje hasta el mensaje. Para la
    extracción, esa transición es `cargado`: incluye la espera en la cola."""
    previas = [t.timestamp for t in traza.transiciones if t.secuencia < m.secuencia]
    inicio = utc(max(previas, key=utc)) if previas else utc(traza.creado)
    return round((utc(m.timestamp) - inicio).total_seconds() * 1000)


def _primero(d: dict, *nombres: str) -> Any:
    """El valor del primer nombre presente en `d`; quita de `d` todos los nombres dados."""
    valor = None
    for n in nombres:
        if n in d:
            v = d.pop(n)
            valor = v if valor is None else valor
    return valor


def normalizar_config(config: dict | None) -> dict:
    """La configuración que cada traza guarda (`Settings.resumen()` + catálogos +
    persistencia + extras) con nombres de la vista. Lo que no se reconoce va a `otros`."""
    c = dict(config or {})
    modelos = dict(c.pop("modelos", None) or {})
    agentes = {k: modelos.pop(k, None) for k in ("extractor", "clasificador", "critico", "modelador")}
    embeddings = modelos.pop("embeddings", None)
    if embeddings is None:
        embeddings = _primero(c, "embedding_model", "modelo_embeddings")
    salida = {
        "umbral": _primero(c, "similarity_threshold", "umbral"),
        "max_rondas": _primero(c, "max_debate_rounds", "max_rondas"),
        "modelos": agentes,
        "modelo_embeddings": embeddings,
        "temperatura": _primero(c, "llm_temperature", "temperatura"),
        "semilla": _primero(c, "llm_seed", "semilla"),
        "significado_max_palabras": _primero(c, "significado_max_palabras"),
        "spacy_model": _primero(c, "spacy_model"),
        "catalogos": dict(_primero(c, "catalogos") or {}),
        "persistencia": _primero(c, "persistencia"),
    }
    if modelos:
        c["modelos"] = modelos
    salida["otros"] = c
    return salida
