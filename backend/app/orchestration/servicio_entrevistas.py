"""Las entrevistas en la cola (ADR 0024, como los requisitos en ADR 0008).

Cada entrevista corre el grafo de la fase del LEL (`grafo_entrevista.py`) en el único
trabajador de la cola, con los modelos de la cuenta dueña del proyecto (ADR 0021). El
`thread_id` del checkpointer es «entrevista:E01#1» (id y corrida): volver a procesar
abre una corrida nueva y el checkpoint de la anterior no se mezcla.

Al arrancar, lo que quedó a medias se retoma: si su grafo tiene un checkpoint con
nodos pendientes, continúa; si no, se vuelve a correr desde el principio.
"""
from __future__ import annotations

import logging
import threading

from app.entrevistas import almacen as ea
from app.entrevistas.almacen import Entrevistas
from app.entrevistas.turnos import EntrevistaLeida
from app.fases.lexico import Lexico
from app.llm.perfiles import con_perfil

from .grafo import Cancelado
from .grafo_entrevista import construir_grafo_entrevista
from .servicio import ConflictoDeEstado

log = logging.getLogger(__name__)


class ConflictoEntrevista(ConflictoDeEstado):
    """La operación no corresponde al estado de la entrevista (409)."""


class ServicioEntrevistas:
    def __init__(self, srv):
        self.srv = srv
        self.repo = srv.repo
        self.almacen = Entrevistas(srv.repo)
        self.lexico = Lexico(srv.repo)
        self._cancelados: set[str] = set()
        self._ocupadas: set[str] = set()
        self._candado = threading.Lock()
        self.grafo = construir_grafo_entrevista(srv.deps, srv.checkpointer,
                                                cancelado=lambda eid: eid in self._cancelados)

    @staticmethod
    def hilo(doc: dict) -> dict:
        return {"configurable": {"thread_id": f"entrevista:{doc['entrevista_id']}#{doc.get('corrida', 1)}"}}

    def ocupada(self, entrevista_id: str) -> bool:
        with self._candado:
            return entrevista_id in self._ocupadas

    def ocupadas_del_proyecto(self, proyecto_id: str) -> list[str]:
        with self._candado:
            ocupadas = set(self._ocupadas)
        return [d["entrevista_id"] for d in self.almacen.listar(proyecto_id) if d["entrevista_id"] in ocupadas]

    def _reservar(self, entrevista_id: str) -> None:
        with self._candado:
            if entrevista_id in self._ocupadas:
                raise ConflictoEntrevista(f"{entrevista_id} ya se está procesando o espera turno")
            self._ocupadas.add(entrevista_id)

    def _liberar(self, entrevista_id: str) -> None:
        with self._candado:
            self._ocupadas.discard(entrevista_id)
            self._cancelados.discard(entrevista_id)

    def config(self, proyecto) -> dict:
        """Con qué se procesa: se guarda en la entrevista para poder repetir el experimento."""
        s = self.srv.deps.settings
        elegidos = self.srv.perfiles.resuelto(proyecto.propietario)
        modelos = {**s.resumen()["modelos"], **{
            rol: e["modelo"] if e["proveedor"] == "ollama" else f"{e['proveedor']}:{e['modelo']}"
            for rol, e in elegidos.items()}}
        return {"similarity_threshold": s.similarity_threshold, "max_debate_rounds": s.max_debate_rounds,
                "modelos": modelos, "lel_max_terminos": s.lel_max_terminos, "llm_temperature": s.llm_temperature,
                "llm_seed": s.llm_seed, "persistencia": self.repo.descripcion,
                "contexto_proyecto": (proyecto.contexto or "").strip() or None}

    # ------------------------------------------------------------ operaciones

    def registrar(self, proyecto_id: str, titulo: str, leida: EntrevistaLeida, origen: dict) -> dict:
        proyecto = self.srv.proyectos.obtener(proyecto_id)
        if proyecto is None:
            raise KeyError(proyecto_id)
        if not leida.turnos:
            raise ValueError("La entrevista no tiene texto.")
        doc = self.almacen.crear(proyecto_id, titulo, leida, origen, self.config(proyecto))
        self._reservar(doc["entrevista_id"])
        return doc

    def solicitar(self, proyecto_id: str, titulo: str, leida: EntrevistaLeida, origen: dict) -> dict:
        """Registrar y encolar (API)."""
        doc = self.registrar(proyecto_id, titulo, leida, origen)
        eid = doc["entrevista_id"]
        self.srv.cola.encolar("entrevista", eid, lambda: self.ejecutar(eid))
        return doc

    def ejecutar(self, entrevista_id: str, continuar: bool = False) -> None:
        """Corre el grafo hasta el LEL propuesto (o el error). `continuar`: desde su último checkpoint."""
        try:
            doc = self.almacen.obtener(entrevista_id)
            if doc is None:
                return
            entrada = None if continuar else {"entrevista_id": entrevista_id, "proyecto_id": doc["proyecto_id"]}
            with con_perfil(self.srv.perfil(doc["proyecto_id"])):
                self.grafo.invoke(entrada, self.hilo(doc))
        except Cancelado:
            log.info("Entrevista %s cancelada", entrevista_id)
            if self.almacen.obtener(entrevista_id) is not None:
                self.almacen.cambiar_estado(entrevista_id, ea.CANCELADA, error=None)
        except Exception as e:
            log.exception("Falla fuera de los nodos en la entrevista %s", entrevista_id)
            if self.almacen.obtener(entrevista_id) is not None:
                self.almacen.agregar_mensaje(entrevista_id, emisor="sistema", receptor="sistema", tipo="error",
                                             payload={"nodo": None, "excepcion": type(e).__name__, "mensaje": str(e)})
                self.almacen.cambiar_estado(entrevista_id, ea.ERROR, error=f"{type(e).__name__}: {e}")
        finally:
            self._liberar(entrevista_id)

    def procesar(self, proyecto_id: str, titulo: str, leida: EntrevistaLeida, origen: dict | None = None) -> str:
        """Registrar y ejecutar en el mismo hilo (scripts y pruebas)."""
        doc = self.registrar(proyecto_id, titulo, leida, origen or {"tipo": "texto"})
        self.ejecutar(doc["entrevista_id"])
        return doc["entrevista_id"]

    def reprocesar(self, entrevista_id: str) -> dict:
        """Vuelve a procesar una entrevista que terminó en error o se canceló. Lo que había propuesto
        y nadie validó sale del LEL; lo validado se queda."""
        doc = self.almacen.obtener(entrevista_id)
        if doc is None:
            raise KeyError(entrevista_id)
        if doc["estado"] not in (ea.ERROR, ea.CANCELADA):
            raise ConflictoEntrevista(f"{entrevista_id} está «{doc['estado']}»: solo se vuelve a procesar lo que "
                                      "terminó en error o se canceló")
        self._reservar(entrevista_id)
        self.lexico.quitar_entrevista(doc["proyecto_id"], entrevista_id)
        self.almacen.reiniciar_bitacora(entrevista_id, doc["proyecto_id"])
        proyecto = self.srv.proyectos.obtener(doc["proyecto_id"])
        doc = self.almacen.actualizar(entrevista_id, estado=ea.CARGADA, corrida=doc.get("corrida", 1) + 1, error=None,
                                      resumen=None, config=self.config(proyecto) if proyecto else doc["config"])
        self.srv.cola.encolar("entrevista", entrevista_id, lambda: self.ejecutar(entrevista_id))
        return doc

    def cancelar(self, entrevista_id: str) -> dict:
        """Si espera turno, sale de la cola; si corre, se detiene antes del siguiente paso (una llamada
        al modelo en curso no se corta). Queda «cancelada»: se puede volver a procesar o borrar."""
        doc = self.almacen.obtener(entrevista_id)
        if doc is None:
            raise KeyError(entrevista_id)
        if self.srv.cola.quitar({entrevista_id}):
            self._liberar(entrevista_id)
            self.almacen.cambiar_estado(entrevista_id, ea.CANCELADA)
            return {"cancelada": True, "deteniendo": False}
        with self._candado:
            corriendo = entrevista_id in self._ocupadas
            if corriendo:
                self._cancelados.add(entrevista_id)
        return {"cancelada": not corriendo and doc["estado"] in ea.TERMINALES, "deteniendo": corriendo}

    def borrar(self, entrevista_id: str) -> dict:
        doc = self.almacen.obtener(entrevista_id)
        if doc is None:
            raise KeyError(entrevista_id)
        self._reservar(entrevista_id)  # 409 si se procesa o espera turno
        try:
            quitado = self.lexico.quitar_entrevista(doc["proyecto_id"], entrevista_id)
            for n in range(1, doc.get("corrida", 1) + 1):
                self.srv.checkpointer.delete_thread(f"entrevista:{entrevista_id}#{n}")
            self.almacen.borrar(entrevista_id)
            return quitado
        finally:
            self._liberar(entrevista_id)

    def borrar_de_proyecto(self, proyecto_id: str) -> None:
        if self.ocupadas_del_proyecto(proyecto_id):
            raise ConflictoEntrevista("el proyecto tiene entrevistas en proceso; bórralo cuando terminen")
        for d in self.almacen.listar(proyecto_id):
            for n in range(1, d.get("corrida", 1) + 1):
                self.srv.checkpointer.delete_thread(f"entrevista:{d['entrevista_id']}#{n}")
        self.almacen.borrar_de_proyecto(proyecto_id)

    def recuperar(self) -> list[str]:
        """Tras un reinicio: continúa desde su checkpoint lo que quedó a medias, o lo vuelve a correr."""
        retomadas = []
        for d in self.almacen.listar():
            eid = d["entrevista_id"]
            if d["estado"] in ea.TERMINALES or self.ocupada(eid):
                continue
            snapshot = self.grafo.get_state(self.hilo(d))
            continuar = bool(snapshot.values) and bool(snapshot.next or snapshot.tasks)
            self._reservar(eid)
            self.srv.cola.encolar("entrevista", eid, lambda e=eid, c=continuar: self.ejecutar(e, continuar=c))
            retomadas.append(eid)
        return retomadas
