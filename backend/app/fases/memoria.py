"""Memoria del proyecto: lo que el sistema aprende de la persona experta (ADR 0024).

Cuando la persona corrige la intención de un término del LEL, elige otra de las que
propusieron los agentes, confirma la elección en un término que era ambiguo o descarta
un término que no es del dominio, el sistema lo guarda como un **acuerdo del proyecto**:

    «consulta» significa «cita médica en la que el doctor atiende a un paciente»;
    no significa «búsqueda en la base de datos».

Los acuerdos valen solo dentro de su proyecto (la memoria no se mezcla entre dominios,
como el LEL en la versión 1, ADR 0008) y se usan de dos formas:

1. En las entrevistas siguientes del proyecto, un término con acuerdo ya no se
   interpreta ni se debate: queda resuelto por la memoria (como `resuelto_por_lel`), y
   un término descartado ya no se propone.
2. Los agentes reciben los acuerdos en sus prompts (Clasificador, Modelador en el LEL,
   el mapa, las metas y los requisitos), para leer los demás términos en ese sentido.

Colección `memoria` (A01, A02…), un acuerdo por término y proyecto.
"""
from __future__ import annotations

from app.db.repositorio import Repositorio

from .claves import clave as clave_de

COLECCION = "memoria"
SIN_ACUERDOS = "(todavía no hay acuerdos: nadie ha corregido ni confirmado términos en este proyecto)"


class Memoria:
    def __init__(self, repo: Repositorio):
        self.repo = repo

    def listar(self, proyecto_id: str) -> list[dict]:
        return self.repo.listar_docs(COLECCION, proyecto_id=proyecto_id)

    def obtener(self, aprendizaje_id: str) -> dict | None:
        return self.repo.obtener_doc(COLECCION, aprendizaje_id)

    def por_clave(self, proyecto_id: str) -> dict[str, dict]:
        """{clave: acuerdo}, también por las claves de sus sinónimos."""
        salida: dict[str, dict] = {}
        for a in self.listar(proyecto_id):
            for k in a.get("claves") or [a["clave"]]:
                salida.setdefault(k, a)
        return salida

    def aprender(self, proyecto_id: str, *, simbolo: str, tipo: str | None, significa: str | None,
                 nocion: list[str] | None = None, no_significa: list[str] | None = None, descartado: bool = False,
                 sinonimos: list[str] | None = None, entrada_id: str | None = None, accion: str, fecha: str) -> dict:
        """Crea o actualiza el acuerdo del término. `no_significa` se acumula (sin repetir y sin
        lo que ahora sí significa)."""
        k = clave_de(simbolo)
        claves = sorted({k, *(clave_de(s) for s in (sinonimos or []) if clave_de(s))})
        actual = next((a for a in self.listar(proyecto_id) if a["clave"] == k), None)
        previos = (actual or {}).get("no_significa", [])
        negados = []
        for x in [*previos, *(no_significa or [])]:
            x = (x or "").strip()
            if x and x != (significa or "").strip() and x not in negados:
                negados.append(x)
        datos = {"proyecto_id": proyecto_id, "clave": k, "claves": claves, "simbolo": simbolo, "tipo": tipo,
                 "significa": significa, "nocion": nocion or [], "no_significa": negados[-6:],
                 "descartado": descartado, "origen": {"entrada_id": entrada_id, "accion": accion},
                 "actualizado": fecha}
        if actual:
            actual.update(datos, veces=actual.get("veces", 1) + 1)
            self.repo.guardar_doc(COLECCION, actual["aprendizaje_id"], actual)
            return actual
        return self.repo.crear_doc(COLECCION, "A", lambda aid: {"aprendizaje_id": aid, **datos, "fecha": fecha,
                                                                 "veces": 1})

    def olvidar(self, aprendizaje_id: str) -> bool:
        return self.repo.borrar_doc(COLECCION, aprendizaje_id)

    def olvidar_clave(self, proyecto_id: str, clave: str) -> int:
        return self.repo.borrar_docs(COLECCION, proyecto_id=proyecto_id, clave=clave)

    def borrar_de_proyecto(self, proyecto_id: str) -> int:
        return self.repo.borrar_docs(COLECCION, proyecto_id=proyecto_id)


def acuerdos_en_texto(acuerdos: list[dict]) -> str:
    """Los acuerdos como van en los prompts, uno por renglón."""
    if not acuerdos:
        return SIN_ACUERDOS
    lineas = []
    for a in sorted(acuerdos, key=lambda x: x["simbolo"].lower()):
        if a.get("descartado"):
            lineas.append(f"- «{a['simbolo']}»: no es un término del dominio en este proyecto.")
            continue
        linea = f"- «{a['simbolo']}» significa: {a.get('significa') or '; '.join(a.get('nocion') or [])}"
        if a.get("no_significa"):
            linea += f". NO significa: {'; '.join(a['no_significa'])}"
        lineas.append(linea + ".")
    return "\n".join(lineas)
