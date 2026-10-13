"""Cola de trabajos con un solo trabajador (ADR 0008).

Ollama local atiende una generación a la vez: correr varios requisitos en
paralelo solo los haría competir por la GPU. Todo lo que llama a un LLM pasa por
aquí, en orden de prioridad y, dentro de la misma prioridad, en orden de llegada.

Prioridades: reanudar una validación (el humano está esperando) > continuar un
grafo interrumpido o generar una fase del proyecto > ejecutar un requisito nuevo o
procesar una entrevista > análisis de proyecto.
"""
from __future__ import annotations

import heapq
import itertools
import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)

# Versión 2 (ADR 0024): generar una fase (la persona espera viendo el avance) va antes que procesar una
# entrevista, que corre en segundo plano como un requisito nuevo.
PRIORIDADES = {"reanudar": 0, "continuar": 1, "fase": 1, "ejecutar": 2, "entrevista": 2, "analisis": 3}


@dataclass(order=True)
class Trabajo:
    prioridad: int
    orden: int
    tipo: str = field(compare=False)
    clave: str = field(compare=False)  # req_id, o el id del análisis
    funcion: Callable[[], None] = field(compare=False, repr=False)

    def resumen(self) -> dict:
        return {"tipo": self.tipo, "clave": self.clave}


class Cola:
    def __init__(self):
        self._q: queue.PriorityQueue[Trabajo] = queue.PriorityQueue()
        self._contador = itertools.count()
        self._cond = threading.Condition()
        self._sin_terminar = 0
        self._actual: Trabajo | None = None
        self._hilo: threading.Thread | None = None
        self._detener = threading.Event()

    def encolar(self, tipo: str, clave: str, funcion: Callable[[], None]) -> None:
        if tipo not in PRIORIDADES:
            raise ValueError(f"tipo de trabajo desconocido: {tipo}")
        with self._cond:
            self._sin_terminar += 1
        self._q.put(Trabajo(PRIORIDADES[tipo], next(self._contador), tipo, clave, funcion))

    def iniciar(self) -> None:
        if self._hilo and self._hilo.is_alive():
            return
        self._detener.clear()
        self._hilo = threading.Thread(target=self._trabajar, name="cola-llm", daemon=True)
        self._hilo.start()

    def detener(self, espera: float = 5.0) -> None:
        self._detener.set()
        if self._hilo:
            self._hilo.join(espera)

    def esperar(self, limite: float | None = None) -> bool:
        """Bloquea hasta que no haya trabajos pendientes ni en curso (para pruebas y scripts)."""
        with self._cond:
            return self._cond.wait_for(lambda: self._sin_terminar == 0, timeout=limite)

    def quitar(self, claves: set[str]) -> set[str]:
        """Saca de la cola los trabajos pendientes de esas claves (no el que está corriendo).
        Devuelve las claves que sí estaban esperando."""
        with self._q.mutex:
            quedan = [t for t in self._q.queue if t.clave not in claves]
            quitadas = {t.clave for t in self._q.queue if t.clave in claves}
            n = len(self._q.queue) - len(quedan)
            self._q.queue[:] = quedan
            heapq.heapify(self._q.queue)
            self._q.unfinished_tasks -= n
        if n:
            with self._cond:
                self._sin_terminar -= n
                self._cond.notify_all()
        return quitadas

    def corriendo(self) -> str | None:
        return self._actual.clave if self._actual else None

    def estado(self) -> dict:
        with self._q.mutex:
            pendientes = sorted(self._q.queue)
        return {"en_proceso": self._actual.resumen() if self._actual else None,
                "pendientes": [t.resumen() for t in pendientes]}

    def _trabajar(self) -> None:
        while not self._detener.is_set():
            try:
                t = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            self._actual = t
            try:
                t.funcion()
            except Exception:  # un trabajo que falla no detiene la cola
                log.exception("Falló el trabajo %s %s", t.tipo, t.clave)
            finally:
                self._actual = None
                with self._cond:
                    self._sin_terminar -= 1
                    self._cond.notify_all()
