"""Entrevistas de un proyecto y su bitácora (ADR 0024).

- Colección `entrevistas` (E01, E02…): el texto, sus turnos, su estado y lo que dejó
  (ficha de la entrevista, resumen del LEL que propuso).
- Colección `bitacoras` (mismo id): los mensajes entre agentes mientras se procesó, con
  el mismo sobre que la traza de un requisito en la versión 1 (emisor, receptor, tipo,
  payload, modelo, versión del prompt). Es la trazabilidad de la fase del LEL y lo que
  anima la escena en vivo.
- Colección `etapas_entrevista` (mismo id): la salida de cada etapa del grafo (el estado
  completo al terminar cada nodo), la que está en curso y la que falló. «Volver a procesar»
  retoma desde la etapa que falló con el estado de la anterior, sin repetir lo que ya salió
  bien (ni volver a pagarle al modelo por ello):

      {entrevista_id, proyecto_id, corrida, en_curso: nodo | null, fallo: {nodo, mensaje} | null,
       orden: [nodos completados], salidas: {nodo: {fecha, corrida, estado}}}

Solo el trabajador de la cola escribe mientras una entrevista se procesa; un candado
cubre cada leer-y-escribir de este proceso (renombrar mientras corre).
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from app.db.repositorio import Repositorio

from .turnos import EntrevistaLeida

COLECCION = "entrevistas"
COLECCION_BITACORAS = "bitacoras"
COLECCION_ETAPAS = "etapas_entrevista"
COLECCION_ETIQUETAS = "etiquetas_entrevista"  # el ground truth de la calibración (app/calibracion/entrevistas.py)
COLECCION_ANOTACIONES = "etiquetas_anotadores"  # el ground truth por persona (app/calibracion/anotaciones.py)

# Estados de una entrevista. `lista`: su LEL propuesto espera a la persona experta.
CARGADA, LEIDA, EXTRAIDA, INTERPRETADA, EN_DEBATE, ARBITRADA, LISTA, ERROR, CANCELADA = (
    "cargada", "leida", "extraida", "interpretada", "en_debate", "arbitrada", "lista", "error", "cancelada")
ESTADOS = (CARGADA, LEIDA, EXTRAIDA, INTERPRETADA, EN_DEBATE, ARBITRADA, LISTA, ERROR, CANCELADA)
TERMINALES = {LISTA, ERROR, CANCELADA}

_candado = threading.RLock()


def ahora_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Entrevistas:
    def __init__(self, repo: Repositorio):
        self.repo = repo

    # ------------------------------------------------------------ entrevistas

    def crear(self, proyecto_id: str, titulo: str, leida: EntrevistaLeida, origen: dict,
              config: dict | None = None) -> dict:
        momento = ahora_iso()

        def fabricar(eid: str) -> dict:
            return {"entrevista_id": eid, "proyecto_id": proyecto_id, "titulo": titulo, "origen": origen,
                    "modo": leida.modo, "turnos": leida.a_dict()["turnos"], "hablantes": leida.hablantes,
                    "advertencias": leida.advertencias, "caracteres": leida.caracteres,
                    "estado": CARGADA, "corrida": 1, "config": config or {}, "ficha": None, "vaguedad": [],
                    "resumen": None, "error": None, "creada": momento, "actualizada": momento}

        doc = self.repo.crear_doc(COLECCION, "E", fabricar)
        self.repo.guardar_doc(COLECCION_BITACORAS, doc["entrevista_id"],
                              {"entrevista_id": doc["entrevista_id"], "proyecto_id": proyecto_id,
                               "mensajes": [], "transiciones": [{"estado": CARGADA, "secuencia": 0, "fecha": momento}]})
        return doc

    def obtener(self, entrevista_id: str) -> dict | None:
        return self.repo.obtener_doc(COLECCION, entrevista_id)

    def listar(self, proyecto_id: str | None = None) -> list[dict]:
        return self.repo.listar_docs(COLECCION, **({"proyecto_id": proyecto_id} if proyecto_id else {}))

    def actualizar(self, entrevista_id: str, **cambios: Any) -> dict:
        with _candado:
            doc = self.obtener(entrevista_id)
            if doc is None:
                raise KeyError(entrevista_id)
            doc.update(cambios, actualizada=ahora_iso())
            self.repo.guardar_doc(COLECCION, entrevista_id, doc)
            return doc

    def cambiar_estado(self, entrevista_id: str, estado: str, **cambios: Any) -> None:
        if estado not in ESTADOS:
            raise ValueError(f"estado de entrevista desconocido: {estado}")
        with _candado:
            self.actualizar(entrevista_id, estado=estado, **cambios)
            b = self.bitacora(entrevista_id)
            ultimo = b["mensajes"][-1]["secuencia"] if b["mensajes"] else 0
            b["transiciones"].append({"estado": estado, "secuencia": ultimo, "fecha": ahora_iso()})
            self.repo.guardar_doc(COLECCION_BITACORAS, entrevista_id, b)

    def borrar(self, entrevista_id: str) -> bool:
        self.repo.borrar_doc(COLECCION_BITACORAS, entrevista_id)
        self.repo.borrar_doc(COLECCION_ETAPAS, entrevista_id)
        self.repo.borrar_doc(COLECCION_ETIQUETAS, entrevista_id)  # su ground truth (ADR 0026)
        self.repo.borrar_docs(COLECCION_ANOTACIONES, entrevista_id=entrevista_id)  # y el de cada persona (ADR 0029)
        return self.repo.borrar_doc(COLECCION, entrevista_id)

    def borrar_de_proyecto(self, proyecto_id: str) -> None:
        self.repo.borrar_docs(COLECCION_BITACORAS, proyecto_id=proyecto_id)
        self.repo.borrar_docs(COLECCION_ETAPAS, proyecto_id=proyecto_id)
        self.repo.borrar_docs(COLECCION, proyecto_id=proyecto_id)

    # ------------------------------------------------------------ bitácora

    def bitacora(self, entrevista_id: str) -> dict:
        return self.repo.obtener_doc(COLECCION_BITACORAS, entrevista_id) or {
            "entrevista_id": entrevista_id, "mensajes": [], "transiciones": []}

    def reiniciar_bitacora(self, entrevista_id: str, proyecto_id: str, conservar: bool = False) -> None:
        """Al volver a procesar: la bitácora anterior se conserva en `anteriores`. Con `conservar`
        (se retoma desde la etapa que falló) siguen los mensajes de las etapas que salieron bien,
        sin los de error, para que la escena cuente la historia completa."""
        with _candado:
            b = self.bitacora(entrevista_id)
            anteriores = b.get("anteriores", []) + ([{"mensajes": b["mensajes"], "transiciones": b["transiciones"]}]
                                                    if b["mensajes"] else [])
            mensajes, transiciones = [], [{"estado": CARGADA, "secuencia": 0, "fecha": ahora_iso()}]
            if conservar:
                mensajes = [{**m, "secuencia": k} for k, m in
                            enumerate((m for m in b["mensajes"] if m.get("tipo") != "error"), 1)]
                transiciones = [t for t in b["transiciones"] if t.get("estado") not in (ERROR, CANCELADA)] \
                    or transiciones
            self.repo.guardar_doc(COLECCION_BITACORAS, entrevista_id, {
                "entrevista_id": entrevista_id, "proyecto_id": proyecto_id, "mensajes": mensajes,
                "transiciones": transiciones, "anteriores": anteriores[-3:]})

    # ------------------------------------------------------------ etapas (para retomar)

    def etapas(self, entrevista_id: str) -> dict | None:
        return self.repo.obtener_doc(COLECCION_ETAPAS, entrevista_id)

    def _etapas(self, entrevista_id: str, proyecto_id: str | None) -> dict:
        return self.etapas(entrevista_id) or {"entrevista_id": entrevista_id, "proyecto_id": proyecto_id,
                                              "en_curso": None, "fallo": None, "orden": [], "salidas": {}}

    def etapa_en_curso(self, entrevista_id: str, proyecto_id: str | None, nodo: str, corrida: str | None) -> None:
        with _candado:
            e = self._etapas(entrevista_id, proyecto_id)
            e.update(en_curso=nodo, corrida=corrida, actualizada=ahora_iso())
            self.repo.guardar_doc(COLECCION_ETAPAS, entrevista_id, e)

    def etapa_completada(self, entrevista_id: str, proyecto_id: str | None, nodo: str, corrida: str | None,
                         estado: dict) -> None:
        """La salida de una etapa: el estado completo del grafo al terminarla. Se retoma desde aquí."""
        with _candado:
            e = self._etapas(entrevista_id, proyecto_id)
            e["salidas"][nodo] = {"fecha": ahora_iso(), "corrida": corrida, "estado": estado}
            e["orden"] = [n for n in e["orden"] if n != nodo] + [nodo]
            e.update(en_curso=None, fallo=None, ultima=nodo, corrida=corrida, actualizada=ahora_iso())
            self.repo.guardar_doc(COLECCION_ETAPAS, entrevista_id, e)

    def etapa_fallida(self, entrevista_id: str, proyecto_id: str | None, nodo: str, mensaje: str) -> None:
        with _candado:
            e = self._etapas(entrevista_id, proyecto_id)
            e.update(en_curso=nodo, fallo={"nodo": nodo, "mensaje": mensaje[:500], "fecha": ahora_iso()},
                     actualizada=ahora_iso())
            self.repo.guardar_doc(COLECCION_ETAPAS, entrevista_id, e)

    def borrar_etapas(self, entrevista_id: str) -> None:
        self.repo.borrar_doc(COLECCION_ETAPAS, entrevista_id)

    def registrar_modelo(self, entrevista_id: str, *, corrida: str | None, rol: str, modelo: str | None,
                         respaldo: str | None = None, reintentos: int = 0) -> None:
        """Qué modelo respondió en esta corrida, por agente, y si fue el de respaldo
        (GEMINI_FALLBACK_MODEL). Solo escribe cuando hay algo nuevo."""
        if not modelo:
            return
        with _candado:
            doc = self.obtener(entrevista_id)
            if doc is None:
                return
            usados = doc.setdefault("modelos_usados", [])
            cambio = False
            fila = next((u for u in usados if u.get("corrida") == corrida and u.get("rol") == rol
                         and u.get("modelo") == modelo), None)
            if fila is None:
                fila = {"corrida": corrida, "rol": rol, "modelo": modelo, "reintentos": 0}
                usados.append(fila)
                cambio = True
            if respaldo:
                fila["respaldo_de"] = respaldo
                doc.setdefault("respaldos", []).append({"corrida": corrida, "rol": rol, "configurado": respaldo,
                                                        "usado": modelo, "fecha": ahora_iso()})
                doc["respaldos"] = doc["respaldos"][-50:]
                cambio = True
            if reintentos:
                fila["reintentos"] = fila.get("reintentos", 0) + reintentos
                cambio = True
            if cambio:
                doc["modelos_usados"] = usados[-100:]
                self.repo.guardar_doc(COLECCION, entrevista_id, doc)

    def agregar_mensaje(self, entrevista_id: str, *, emisor: str, receptor: str, tipo: str, payload: dict,
                        ronda: int = 0, modelo: str | None = None, prompt_version: str | None = None) -> dict:
        with _candado:
            b = self.bitacora(entrevista_id)
            m = {"entrevista_id": entrevista_id, "secuencia": len(b["mensajes"]) + 1, "ronda": ronda,
                 "emisor": emisor, "receptor": receptor, "tipo": tipo, "payload": payload, "modelo": modelo,
                 "prompt_version": prompt_version, "timestamp": ahora_iso()}
            b["mensajes"].append(m)
            self.repo.guardar_doc(COLECCION_BITACORAS, entrevista_id, b)
            return m
