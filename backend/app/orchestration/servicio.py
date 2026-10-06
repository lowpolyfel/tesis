"""Punto de entrada de la orquestación para la API (y para scripts).

`thread_id` del checkpointer = `req_id`: el grafo de cada requisito se reanuda
por su identificador. La API encola el trabajo (ADR 0008); los scripts y las
pruebas pueden correrlo en el mismo hilo con `procesar` y `validar`.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from langgraph.types import Command

from app.db.proyectos import Proyectos
from app.models import PROYECTO_GENERAL, ESTADOS_TERMINALES, Estado, Nodo, Origen, TipoMensaje, Traza, Validacion

from .cola import Cola
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
        self.proyectos = Proyectos(self.repo)
        self.proyectos.asegurar_general()
        self.cola = Cola()
        self._ocupados: set[str] = set()
        self._candado = threading.Lock()

    # ------------------------------------------------------------ ciclo de vida

    def iniciar(self) -> None:
        """Arranca el trabajador de la cola y retoma lo que quedó a medias."""
        self.cola.iniciar()
        self.recuperar()

    def detener(self) -> None:
        self.cola.detener()

    def recuperar(self) -> list[str]:
        """Tras un reinicio: los requisitos en `cargado` se vuelven a encolar, los
        que quedaron a mitad del grafo continúan desde su último checkpoint y los
        que esperan validación siguen esperando. Devuelve los req_id retomados."""
        retomados = []
        for r in self.repo.listar_trazas():
            req_id, estado = r["req_id"], Estado(r["estado"])
            if estado in ESTADOS_TERMINALES or estado == Estado.PENDIENTE_VALIDACION or req_id in self._ocupados:
                continue
            snapshot = self.grafo.get_state(self._config(req_id))
            self._reservar(req_id)
            if not snapshot.values:
                self.cola.encolar("ejecutar", req_id, lambda r=req_id: self.ejecutar(r))
            elif snapshot.next and snapshot.next != ("humano",):
                self.cola.encolar("continuar", req_id, lambda r=req_id: self._correr(r, None))
            else:
                self._liberar(req_id)
                continue
            retomados.append(req_id)
        return retomados

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

    def registrar(self, texto: str, proyecto_id: str = PROYECTO_GENERAL, origen: Origen | None = None) -> str:
        """Crea la traza en `cargado` y reserva el requisito para ejecutarlo."""
        if self.proyectos.obtener(proyecto_id) is None:
            raise KeyError(proyecto_id)
        traza = self.repo.crear_traza(texto, self.deps.config_traza(), proyecto_id=proyecto_id, origen=origen)
        self._reservar(traza.req_id)
        return traza.req_id

    def solicitar(self, texto: str, proyecto_id: str = PROYECTO_GENERAL, origen: Origen | None = None) -> str:
        """Registrar y encolar (API)."""
        req_id = self.registrar(texto, proyecto_id, origen)
        self.cola.encolar("ejecutar", req_id, lambda: self.ejecutar(req_id))
        return req_id

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
        self._correr(req_id, {"req_id": req_id, "proyecto_id": traza.proyecto_id, "texto": traza.texto})

    def procesar(self, texto: str, proyecto_id: str = PROYECTO_GENERAL, origen: Origen | None = None) -> str:
        """Registrar y ejecutar en el mismo hilo (scripts y pruebas)."""
        req_id = self.registrar(texto, proyecto_id, origen)
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

    def solicitar_validacion(self, req_id: str, validacion: Validacion) -> None:
        """Preparar y encolar la reanudación (API). Va antes que los requisitos nuevos."""
        self.preparar_validacion(req_id, validacion)
        self.cola.encolar("reanudar", req_id, lambda: self.reanudar(req_id, validacion))

    def traza(self, req_id: str) -> Traza | None:
        return self.repo.obtener_traza(req_id)

    def trazas(self, proyecto_id: str | None = None) -> list[dict]:
        return self.repo.listar_trazas(proyecto_id)

    @staticmethod
    def terminado(traza: Traza) -> bool:
        return traza.estado in ESTADOS_TERMINALES
