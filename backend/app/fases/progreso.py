"""Generar una fase en la cola y contar su avance en vivo (ADR 0024).

El mapa, las metas y los requisitos los genera el Modelador. Como todo lo que llama a un
LLM, la generación pasa por la cola de un solo trabajador (ADR 0008); mientras tanto, la
respuesta HTTP va diciendo qué hace, una línea JSON por evento (NDJSON, como el mapa de
la versión 1, ADR 0020):

    {"tipo": "paso", id, texto, estado: curso|ok|aviso, detalle}
    {"tipo": "resultado", ...}   ·   {"tipo": "error", mensaje}

Si la persona cierra la pantalla, el trabajo sigue y su resultado se guarda. Si vuelve a
pedir la misma fase mientras se genera (al volver a la pantalla, o porque React monta dos
veces en desarrollo), no se encola otra: se suma a la que corre y recibe su avance desde el
principio.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterator

Avisar = Callable[[dict], None]


class EnCurso(Exception):
    """Ya se está generando esa fase de ese proyecto."""


class _Trabajo:
    """Los eventos de una generación: se guardan todos para quien se sume después."""

    def __init__(self):
        self.eventos: list[dict] = []
        self.terminado = False
        self._cond = threading.Condition()

    def emitir(self, evento: dict) -> None:
        with self._cond:
            self.eventos.append(evento)
            self._cond.notify_all()

    def terminar(self) -> None:
        with self._cond:
            self.terminado = True
            self._cond.notify_all()

    def seguir(self) -> Iterator[dict]:
        i = 0
        while True:
            with self._cond:
                self._cond.wait_for(lambda: i < len(self.eventos) or self.terminado)
                nuevos, fin = self.eventos[i:], self.terminado
            i += len(nuevos)
            yield from nuevos
            if fin and i >= len(self.eventos):
                return


_en_curso: dict[str, _Trabajo] = {}
_candado = threading.Lock()


def paso(id_: str, texto: str, estado: str = "curso", detalle: str | None = None) -> dict:
    return {"tipo": "paso", "id": id_, "texto": texto, "estado": estado, "detalle": detalle}


def ocupado(clave: str) -> bool:
    with _candado:
        return clave in _en_curso


def en_cola(cola, clave: str, trabajo: Callable[[Avisar], None]) -> Iterator[dict]:
    """Encola `trabajo(avisar)` y devuelve sus eventos conforme ocurren. `clave`: «mapa:P01».
    Si esa clave ya se está generando, devuelve los eventos de la que corre."""
    with _candado:
        actual = _en_curso.get(clave)
        if actual is not None:
            return actual.seguir()
        actual = _en_curso[clave] = _Trabajo()
    estado = cola.estado()
    antes = len(estado["pendientes"]) + (1 if estado["en_proceso"] else 0)
    if antes:
        actual.emitir(paso("turno", "Esperando turno", detalle=f"{antes} trabajo(s) de los agentes antes"))

    def correr() -> None:
        try:
            if antes:
                actual.emitir(paso("turno", "Turno de los agentes", "ok"))
            trabajo(actual.emitir)
        except Exception as e:  # noqa: BLE001 — se informa en el flujo
            actual.emitir({"tipo": "error", "mensaje": f"{type(e).__name__}: {str(e)[:400]}"})
        finally:
            with _candado:
                _en_curso.pop(clave, None)
            actual.terminar()

    cola.encolar("fase", clave, correr)
    return actual.seguir()
