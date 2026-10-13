"""El LEL interactivo del proyecto (ADR 0024).

Cada término del dominio que los agentes encontraron en las entrevistas es una entrada
(colección `lexico`, S01, S02…) con su símbolo, tipo, noción, impacto e **intención**,
las citas que la respaldan y, si el término admitía más de una interpretación, las intenciones
que se consideraron y cómo se resolvió (aceptado directo, consenso o arbitraje).

La persona experta valida cada entrada:

- **validar**: la confirma tal cual;
- **corregir**: cambia lo que haga falta (puede partir de otra intención de las que
  propusieron los agentes, `alternativa`);
- **descartar**: no es un término del dominio; **restaurar** lo regresa.

Cada acción queda en el `historial` de la entrada. Corregir, confirmar un término que
era ambiguo y descartar enseñan al sistema: se guardan como acuerdos del proyecto
(`memoria.py`). Una persona también puede agregar un término a mano.

Estados: `propuesto` (lo dejaron los agentes) → `validado` | `corregido` | `descartado`.
El LEL está completo cuando no queda ninguna entrada `propuesta`.
"""
from __future__ import annotations

import hashlib
import json

from app.db.repositorio import Repositorio
from app.models import CambiosEntradaLexico, EntradaLexicoNueva

from .claves import clave as clave_de
from .memoria import Memoria

COLECCION = "lexico"
MAX_CITAS = 12
VIAS_SIN_AMBIGUEDAD = {"univoco", "memoria", "persona"}


class ErrorLexico(ValueError):
    """La acción no corresponde a la entrada (p. ej. elegir una intención que no existe)."""


def claves_de(simbolo: str, sinonimos: list[str] | None = None, terminos: list[str] | None = None) -> list[str]:
    return sorted({k for k in (clave_de(x) for x in [simbolo, *(sinonimos or []), *(terminos or [])]) if k})


def vigentes(entradas: list[dict]) -> list[dict]:
    """Las que forman el LEL: todas menos las descartadas."""
    return [e for e in entradas if e["estado"] != "descartado"]


def huella_lexico(entradas: list[dict], acuerdos: list[dict]) -> str:
    """Lo que hereda el mapa conceptual: el LEL vigente y los acuerdos. Si cambia, el mapa ya no está al día."""
    lel = sorted((e["clave"], e["simbolo"], e["tipo"], e["intencion"], tuple(e["nocion"]), tuple(e["impacto"]))
                 for e in vigentes(entradas))
    memoria = sorted((a["clave"], a.get("significa"), bool(a.get("descartado"))) for a in acuerdos)
    return hashlib.sha256(json.dumps([lel, memoria], ensure_ascii=False).encode()).hexdigest()


def resumen(entradas: list[dict]) -> dict:
    cuenta = {e: sum(x["estado"] == e for x in entradas) for e in ("propuesto", "validado", "corregido", "descartado")}
    ambiguos = sum(1 for x in entradas if x.get("ambiguedad") and x["estado"] != "descartado")
    return {**cuenta, "total": len(entradas), "vigentes": len(entradas) - cuenta["descartado"], "ambiguos": ambiguos,
            "completo": bool(entradas) and cuenta["propuesto"] == 0 and len(entradas) > cuenta["descartado"]}


class Lexico:
    def __init__(self, repo: Repositorio):
        self.repo = repo
        self.memoria = Memoria(repo)

    # ------------------------------------------------------------ consultas

    def listar(self, proyecto_id: str) -> list[dict]:
        return self.repo.listar_docs(COLECCION, proyecto_id=proyecto_id)

    def obtener(self, entrada_id: str) -> dict | None:
        return self.repo.obtener_doc(COLECCION, entrada_id)

    def por_clave(self, proyecto_id: str) -> dict[str, dict]:
        salida: dict[str, dict] = {}
        for e in self.listar(proyecto_id):
            for k in e.get("claves") or [e["clave"]]:
                salida.setdefault(k, e)
        return salida

    # ------------------------------------------------------------ escritura

    def crear(self, datos: dict) -> dict:
        return self.repo.crear_doc(COLECCION, "S", lambda sid: {"entrada_id": sid, **datos})

    def guardar(self, entrada: dict) -> None:
        self.repo.guardar_doc(COLECCION, entrada["entrada_id"], entrada)

    def agregar_citas(self, entrada: dict, citas: list[dict], entrevista_id: str, terminos: list[str],
                      fecha: str) -> dict:
        """Una entrevista nueva vuelve a usar un término que ya está en el LEL: se le suman sus citas
        (sin repetir) y la forma en que se dijo, sin tocar lo que la persona validó. Se relee la entrada
        justo antes de escribir: la persona pudo validarla mientras la entrevista se procesaba."""
        entrada = self.obtener(entrada["entrada_id"]) or entrada
        vistas = {(c["entrevista"], c["turno"]) for c in entrada["citas"]}
        nuevas = [c for c in citas if (c["entrevista"], c["turno"]) not in vistas]
        entrada["citas"] = (entrada["citas"] + nuevas)[:MAX_CITAS]
        if entrevista_id not in entrada["entrevistas"]:
            entrada["entrevistas"].append(entrevista_id)
        entrada["terminos"] = sorted({*entrada.get("terminos", []), *terminos})
        entrada["claves"] = claves_de(entrada["simbolo"], entrada.get("sinonimos"), entrada["terminos"])
        if nuevas:
            entrada["historial"].append({"fecha": fecha, "accion": "citas", "autor": "sistema",
                                         "detalle": f"{len(nuevas)} cita(s) de {entrevista_id}"})
        entrada["actualizada"] = fecha
        self.guardar(entrada)
        return entrada

    def quitar_entrevista(self, proyecto_id: str, entrevista_id: str) -> dict:
        """Al borrar una entrevista: sus citas salen del LEL. Una entrada que solo tenía citas de ella
        se borra si nadie la había validado; si ya se validó, se conserva (es conocimiento del
        proyecto) sin esas citas. {borradas, conservadas}."""
        borradas, conservadas = 0, 0
        for e in self.listar(proyecto_id):
            if entrevista_id not in e["entrevistas"]:
                continue
            e["citas"] = [c for c in e["citas"] if c["entrevista"] != entrevista_id]
            e["entrevistas"] = [x for x in e["entrevistas"] if x != entrevista_id]
            if not e["entrevistas"] and e["estado"] == "propuesto":
                self.repo.borrar_doc(COLECCION, e["entrada_id"])
                borradas += 1
            else:
                self.guardar(e)
                conservadas += 1
        return {"borradas": borradas, "conservadas": conservadas}

    def borrar_de_proyecto(self, proyecto_id: str) -> int:
        return self.repo.borrar_docs(COLECCION, proyecto_id=proyecto_id)

    # ------------------------------------------------------------ la persona experta

    def _registrar(self, e: dict, accion: str, fecha: str, **detalle) -> None:
        e["historial"].append({"fecha": fecha, "accion": accion, "autor": "persona", **detalle})
        e["actualizada"] = fecha

    @staticmethod
    def _foto(e: dict) -> dict:
        return {k: e.get(k) for k in ("simbolo", "tipo", "nocion", "impacto", "intencion", "sinonimos")}

    def validar(self, e: dict, fecha: str) -> dict:
        if e["estado"] == "descartado":
            raise ErrorLexico("Un término descartado no se valida: primero restáuralo.")
        if e["estado"] == "propuesto":
            e["estado"] = "validado"
        self._registrar(e, "validar", fecha)
        amb = e.get("ambiguedad")
        if amb and amb.get("alternativas"):  # confirmó una interpretación entre varias: el sistema la recuerda
            otras = [a["significado"] for a in amb["alternativas"] if a["id"] != amb.get("elegida")]
            self.memoria.aprender(e["proyecto_id"], simbolo=e["simbolo"], tipo=e["tipo"], significa=e["intencion"],
                                  nocion=e["nocion"], no_significa=otras, sinonimos=e.get("sinonimos"),
                                  entrada_id=e["entrada_id"], accion="confirmar", fecha=fecha)
            e["aprendida"] = True
        self.guardar(e)
        return e

    def corregir(self, e: dict, cambios: CambiosEntradaLexico, fecha: str, alternativa: str | None = None) -> dict:
        if e["estado"] == "descartado":
            raise ErrorLexico("Un término descartado no se corrige: primero restáuralo.")
        amb = e.get("ambiguedad") or {}
        elegida = None
        if alternativa is not None:
            elegida = next((a for a in amb.get("alternativas", []) if a["id"] == alternativa), None)
            if elegida is None:
                raise ErrorLexico(f"«{e['simbolo']}» no tiene la intención {alternativa}")
        antes = self._foto(e)
        nuevos = cambios.model_dump(exclude_none=True)
        if elegida is not None:  # partir de otra intención de los agentes; lo que la persona escribió manda
            nuevos = {"intencion": elegida["intencion"], "nocion": [elegida["significado"]], **nuevos}
        if not nuevos:
            raise ErrorLexico("No hay nada que corregir.")
        e.update(nuevos)
        e["clave"] = clave_de(e["simbolo"])
        e["claves"] = claves_de(e["simbolo"], e.get("sinonimos"), e.get("terminos"))
        e["estado"] = "corregido"
        if elegida is not None:
            amb["elegida_por_persona"] = alternativa
        self._registrar(e, "corregir", fecha, antes=antes, despues=self._foto(e), alternativa=alternativa)
        # lo que deja de significar: la intención anterior (si la persona la reescribió o eligió otra
        # distinta de la de los agentes) y las demás interpretaciones que se habían considerado
        elegida_final = alternativa or amb.get("elegida")
        negadas = []
        if antes["intencion"] != e["intencion"] and (alternativa is None or alternativa != amb.get("elegida")):
            negadas.append(antes["intencion"])
        negadas += [a["significado"] for a in amb.get("alternativas", [])
                    if a["id"] != elegida_final and a["significado"] not in e["nocion"]]
        self.memoria.aprender(e["proyecto_id"], simbolo=e["simbolo"], tipo=e["tipo"], significa=e["intencion"],
                              nocion=e["nocion"], no_significa=negadas, sinonimos=e.get("sinonimos"),
                              entrada_id=e["entrada_id"], accion="corregir", fecha=fecha)
        if antes["simbolo"] != e["simbolo"] and clave_de(antes["simbolo"]) != e["clave"]:
            self.memoria.olvidar_clave(e["proyecto_id"], clave_de(antes["simbolo"]))  # el acuerdo sigue al nombre nuevo
        e["aprendida"] = True
        self.guardar(e)
        return e

    def descartar(self, e: dict, fecha: str, motivo: str | None = None) -> dict:
        e["estado"] = "descartado"
        self._registrar(e, "descartar", fecha, motivo=motivo)
        self.memoria.aprender(e["proyecto_id"], simbolo=e["simbolo"], tipo=e["tipo"], significa=None,
                              descartado=True, sinonimos=e.get("sinonimos"), entrada_id=e["entrada_id"],
                              accion="descartar", fecha=fecha)
        e["aprendida"] = True
        self.guardar(e)
        return e

    def restaurar(self, e: dict, fecha: str) -> dict:
        if e["estado"] != "descartado":
            raise ErrorLexico("Solo se restaura un término descartado.")
        e["estado"] = "propuesto"
        self._registrar(e, "restaurar", fecha)
        self.memoria.olvidar_clave(e["proyecto_id"], e["clave"])
        e["aprendida"] = False
        self.guardar(e)
        return e

    def agregar(self, proyecto_id: str, nueva: EntradaLexicoNueva, fecha: str) -> dict:
        k = clave_de(nueva.simbolo)
        existente = self.por_clave(proyecto_id).get(k)
        if existente is not None:
            raise ErrorLexico(f"«{nueva.simbolo}» ya está en el LEL como «{existente['simbolo']}» ({existente['entrada_id']}).")
        datos = {**nueva.model_dump(mode="json"), "proyecto_id": proyecto_id, "clave": k,
                 "claves": claves_de(nueva.simbolo, nueva.sinonimos), "terminos": [nueva.simbolo], "citas": [],
                 "entrevistas": [], "marcas": {"regional": False, "vago": False}, "ambiguedad": None,
                 "via": "persona", "estado": "validado", "aprendida": True,
                 "historial": [{"fecha": fecha, "accion": "agregar", "autor": "persona"}],
                 "modelo": None, "prompt_version": None, "creada": fecha, "actualizada": fecha}
        e = self.crear(datos)
        self.memoria.aprender(proyecto_id, simbolo=e["simbolo"], tipo=e["tipo"], significa=e["intencion"],
                              nocion=e["nocion"], sinonimos=e["sinonimos"], entrada_id=e["entrada_id"],
                              accion="agregar", fecha=fecha)
        return e

    def validar_sin_ambiguedad(self, proyecto_id: str, fecha: str) -> list[str]:
        """Valida de una vez las propuestas en las que los agentes no vieron más de una interpretación."""
        hechas = []
        for e in self.listar(proyecto_id):
            if e["estado"] == "propuesto" and not e.get("ambiguedad") and e.get("via") in VIAS_SIN_AMBIGUEDAD:
                e["estado"] = "validado"
                self._registrar(e, "validar", fecha, en_bloque=True)
                self.guardar(e)
                hechas.append(e["entrada_id"])
        return hechas
