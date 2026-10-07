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
from app.models import (
    PROYECTO_GENERAL,
    ESTADOS_TERMINALES,
    Estado,
    Nodo,
    Origen,
    TipoMensaje,
    Traza,
    Validacion,
    ahora,
)

from .cola import Cola
from .dependencias import Dependencias
from .estado import con_interpretaciones
from .grafo import construir_grafo


log = logging.getLogger(__name__)

# Validaciones aceptadas (202) que esperan turno en la cola: si el proceso se reinicia
# antes de aplicarlas, `recuperar()` las vuelve a encolar (un documento por req_id).
COLECCION_VALIDACIONES = "validaciones"


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
        self._candado_ciclos = threading.RLock()  # leer el último ciclo y abrir el siguiente, sin carreras

    # ------------------------------------------------------------ ciclo de vida

    def iniciar(self) -> None:
        """Arranca el trabajador de la cola y retoma lo que quedó a medias."""
        self.cola.iniciar()
        self.recuperar()

    def detener(self) -> None:
        self.cola.detener()

    def recuperar(self) -> list[str]:
        """Tras un reinicio, según el checkpoint de cada requisito no terminado (ADR 0008):
        - sin checkpoint (se quedó en `cargado`): se vuelve a encolar;
        - a mitad del grafo: continúa desde su último checkpoint. Incluye los que el
          repositorio ya marca `pendiente_validacion` pero cuyo grafo no llegó a pausarse
          en `humano`, o ya pasó de ahí con la validación registrada;
        - pausado en `humano`: si había una validación aceptada esperando turno, se
          reanuda con ella; si no, sigue esperando a la persona.
        Devuelve los req_id retomados."""
        retomados = []
        for r in self.repo.listar_trazas():
            req_id, estado = r["req_id"], Estado(r["estado"])
            if estado in ESTADOS_TERMINALES or req_id in self._ocupados:
                continue
            snapshot = self.grafo.get_state(self._config(req_id))
            if not snapshot.values:
                if estado == Estado.PENDIENTE_VALIDACION:  # sin checkpoint no hay ejecución que reanudar
                    continue
                tipo, trabajo = "ejecutar", lambda r=req_id: self.ejecutar(r)
            elif snapshot.next == ("humano",):
                validacion = self.validacion_aceptada(req_id)
                if validacion is None:
                    continue
                tipo, trabajo = "reanudar", lambda r=req_id, v=validacion: self.reanudar(r, v)
            elif snapshot.next:
                tipo, trabajo = "continuar", lambda r=req_id: self._correr(r, None)
            else:
                continue
            self._reservar(req_id)
            self.cola.encolar(tipo, req_id, trabajo)
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

    def siguiente_ciclo(self, proyecto_id: str) -> int:
        return max((t.get("ciclo") or 1 for t in self.repo.listar_trazas(proyecto_id)), default=0) + 1

    def registrar(self, texto: str, proyecto_id: str = PROYECTO_GENERAL, origen: Origen | None = None,
                  ciclo: int | None = None) -> str:
        """Crea la traza en `cargado` y reserva el requisito para ejecutarlo. Sin `ciclo`, abre uno nuevo."""
        if self.proyectos.obtener(proyecto_id) is None:
            raise KeyError(proyecto_id)
        with self._candado_ciclos:  # el ciclo nuevo queda tomado al crear su primera traza
            ciclo = ciclo or self.siguiente_ciclo(proyecto_id)
            traza = self.repo.crear_traza(texto, self.deps.config_traza(), proyecto_id=proyecto_id, origen=origen,
                                          ciclo=ciclo)
        self._reservar(traza.req_id)
        return traza.req_id

    def solicitar(self, texto: str, proyecto_id: str = PROYECTO_GENERAL, origen: Origen | None = None,
                  ciclo: int | None = None) -> str:
        """Registrar y encolar (API)."""
        req_id = self.registrar(texto, proyecto_id, origen, ciclo)
        self.cola.encolar("ejecutar", req_id, lambda: self.ejecutar(req_id))
        return req_id

    def solicitar_lote(self, requisitos: list[tuple[str, Origen | None]], proyecto_id: str) -> tuple[int, list[str]]:
        """Una carga de varios requisitos abre un solo ciclo nuevo; se encolan en orden."""
        if self.proyectos.obtener(proyecto_id) is None:
            raise KeyError(proyecto_id)
        with self._candado_ciclos:  # dos cargas simultáneas al mismo proyecto abren ciclos distintos
            ciclo = self.siguiente_ciclo(proyecto_id)
            return ciclo, [self.solicitar(texto, proyecto_id, origen, ciclo) for texto, origen in requisitos]

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

    def procesar(self, texto: str, proyecto_id: str = PROYECTO_GENERAL, origen: Origen | None = None,
                 ciclo: int | None = None) -> str:
        """Registrar y ejecutar en el mismo hilo (scripts y pruebas)."""
        req_id = self.registrar(texto, proyecto_id, origen, ciclo)
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
        """Preparar y encolar la reanudación (API). Va antes que los requisitos nuevos.
        Se guarda antes de encolarla: si el proceso se reinicia mientras espera turno,
        `recuperar()` la vuelve a encolar en vez de perder la decisión de la persona."""
        self.preparar_validacion(req_id, validacion)
        try:
            self.repo.guardar_doc(COLECCION_VALIDACIONES, req_id, {
                "req_id": req_id, "validacion": validacion.model_dump(mode="json"), "aceptada": ahora().isoformat()})
        except Exception:
            self._liberar(req_id)
            raise
        self.cola.encolar("reanudar", req_id, lambda: self.reanudar(req_id, validacion))

    def validacion_aceptada(self, req_id: str) -> Validacion | None:
        """La última validación aceptada para `req_id`. Solo cuenta si el grafo sigue
        pausado en `humano`: después de aplicarla, el checkpoint ya pasó de ahí."""
        doc = self.repo.obtener_doc(COLECCION_VALIDACIONES, req_id)
        return Validacion.model_validate(doc["validacion"]) if doc else None

    def traza(self, req_id: str) -> Traza | None:
        return self.repo.obtener_traza(req_id)

    def trazas(self, proyecto_id: str | None = None) -> list[dict]:
        return self.repo.listar_trazas(proyecto_id)

    @staticmethod
    def terminado(traza: Traza) -> bool:
        return traza.estado in ESTADOS_TERMINALES
