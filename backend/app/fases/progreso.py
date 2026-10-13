"""Generar una fase en la cola y contar su avance en vivo (ADR 0024).

El mapa, las metas y los requisitos los genera el Modelador. Como todo lo que llama a un
LLM, la generación pasa por la cola de un solo trabajador (ADR 0008); mientras tanto, la
respuesta HTTP va diciendo qué hace, una línea JSON por evento (NDJSON, como el mapa de
la versión 1, ADR 0020):

    {"tipo": "paso", id, texto, estado: curso|ok|aviso, detalle}
    {"tipo": "resultado", ...}   ·   {"tipo": "error", mensaje}

Si la persona cierra la pantalla, el trabajo sigue y su resultado se guarda.
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterator

Avisar = Callable[[dict], None]


class EnCurso(Exception):
    """Ya se está generando esa fase de ese proyecto (409)."""


_en_curso: set[str] = set()
_candado = threading.Lock()


def paso(id_: str, texto: str, estado: str = "curso", detalle: str | None = None) -> dict:
    return {"tipo": "paso", "id": id_, "texto": texto, "estado": estado, "detalle": detalle}


def ocupado(clave: str) -> bool:
    with _candado:
        return clave in _en_curso


def en_cola(cola, clave: str, trabajo: Callable[[Avisar], None]) -> Iterator[dict]:
    """Encola `trabajo(avisar)` y devuelve sus eventos conforme ocurren. `clave`: «mapa:P01»."""
    with _candado:
        if clave in _en_curso:
            raise EnCurso(clave)
        _en_curso.add(clave)
    eventos: queue.Queue = queue.Queue()
    estado = cola.estado()
    antes = len(estado["pendientes"]) + (1 if estado["en_proceso"] else 0)
    if antes:
        eventos.put(paso("turno", "Esperando turno", detalle=f"{antes} trabajo(s) de los agentes antes"))

    def correr() -> None:
        try:
            if antes:
                eventos.put(paso("turno", "Turno de los agentes", "ok"))
            trabajo(eventos.put)
        except Exception as e:  # noqa: BLE001 — se informa en el flujo
            eventos.put({"tipo": "error", "mensaje": f"{type(e).__name__}: {str(e)[:400]}"})
        finally:
            with _candado:
                _en_curso.discard(clave)
            eventos.put(None)

    cola.encolar("fase", clave, correr)

    def lineas() -> Iterator[dict]:
        while (e := eventos.get()) is not None:
            yield e

    return lineas()
