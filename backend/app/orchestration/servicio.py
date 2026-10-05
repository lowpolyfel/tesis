"""Punto de entrada de la orquestación para la API (y para scripts).

`thread_id` del checkpointer = `req_id`: el grafo de cada requisito se reanuda
por su identificador.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from langgraph.types import Command

from app.models import ESTADOS_TERMINALES, Estado, Nodo, TipoMensaje, Traza, Validacion

from .dependencias import Dependencias
from .estado import con_interpretaciones
from .grafo import construir_grafo


log = logging.getLogger(__name__)


class ConflictoDeEstado(Exception):
    """La operación no corresponde al estado actual del requisito."""


def checkpointer_sqlite(ruta: Path):
    from langgraph.checkpoint.sqlite import SqliteSaver

    ruta.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False es seguro: SqliteSaver serializa el acceso con un candado.
    return SqliteSaver(sqlite3.connect(str(ruta), check_same_thread=False))


class Servicio:
    def __init__(self, deps: Dependencias, checkpointer=None):
        self.deps = deps
        self.repo = deps.repo
        if checkpointer is None:
            checkpointer = checkpointer_sqlite(deps.settings.ruta(deps.settings.checkpoint_path))
        self.grafo = construir_grafo(deps, checkpointer)
        self._ocupados: set[str] = set()
        self._candado = threading.Lock()

    @staticmethod
    def _config(req_id: str) -> dict:
        return {"configurable": {"thread_id": req_id}}

    def _reservar(self, req_id: str) -> None:
        with self._candado:
            if req_id in self._ocupados:
                raise ConflictoDeEstado(f"{req_id} ya se está procesando")
            self._ocupados.add(req_id)

    def _liberar(self, req_id: str) -> None:
        with self._candado:
            self._ocupados.discard(req_id)

    # ------------------------------------------------------------ operaciones

    def registrar(self, texto: str) -> str:
        """Crea la traza en `cargado` y reserva el requisito para ejecutarlo."""
        traza = self.repo.crear_traza(texto, self.deps.config_traza())
        self._reservar(traza.req_id)
        return traza.req_id

    def _correr(self, req_id: str, entrada) -> None:
        """Invoca el grafo. Los nodos ya registran sus fallas; esto cubre lo que
        falle fuera de ellos (p. ej. el checkpointer), para que el caso no quede
        a medias sin explicación en la traza."""
        try:
            self.grafo.invoke(entrada, self._config(req_id))
        except Exception as e:
            log.exception("Falla fuera de los nodos en %s", req_id)
            self.repo.agregar_mensaje(req_id, ronda=0, emisor=Nodo.SISTEMA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.ERROR,
                                      payload={"nodo": None, "excepcion": type(e).__name__, "mensaje": str(e)})
            self.repo.cambiar_estado(req_id, Estado.ERROR)
        finally:
            self._liberar(req_id)

    def ejecutar(self, req_id: str) -> None:
        """Corre el grafo hasta la pausa de validación (o hasta el final)."""
        traza = self.repo.obtener_traza(req_id)
        self._correr(req_id, {"req_id": req_id, "texto": traza.texto})

    def procesar(self, texto: str) -> str:
        """Registrar y ejecutar en el mismo hilo (scripts y pruebas)."""
        req_id = self.registrar(texto)
        self.ejecutar(req_id)
        return req_id

    def preparar_validacion(self, req_id: str, validacion: Validacion) -> None:
        """Comprueba que se puede reanudar y reserva el requisito."""
        traza = self.repo.obtener_traza(req_id)
        if traza is None:
            raise KeyError(req_id)
        if traza.estado != Estado.PENDIENTE_VALIDACION:
            raise ConflictoDeEstado(f"{req_id} está en '{traza.estado}', no en 'pendiente_validacion'")
        snapshot = self.grafo.get_state(self._config(req_id))
        if snapshot.next != ("humano",):
            raise ConflictoDeEstado(f"{req_id} no tiene una ejecución pausada esperando validación")
        conocidos = set(con_interpretaciones(snapshot.values.get("candidatos", {})))
        desconocidos = set(validacion.interpretaciones_editadas) - conocidos
        if desconocidos:
            raise ValueError(f"términos sin interpretaciones en {req_id}: {sorted(desconocidos)}; válidos: {sorted(conocidos)}")
        self._reservar(req_id)

    def reanudar(self, req_id: str, validacion: Validacion) -> None:
        self._correr(req_id, Command(resume=validacion.model_dump(mode="json")))

    def validar(self, req_id: str, validacion: Validacion) -> None:
        """Preparar y reanudar en el mismo hilo (scripts y pruebas)."""
        self.preparar_validacion(req_id, validacion)
        self.reanudar(req_id, validacion)

    def traza(self, req_id: str) -> Traza | None:
        return self.repo.obtener_traza(req_id)

    def trazas(self) -> list[dict]:
        return self.repo.listar_trazas()

    @staticmethod
    def terminado(traza: Traza) -> bool:
        return traza.estado in ESTADOS_TERMINALES
