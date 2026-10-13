"""El documento de cada fase después del LEL y en qué va el proyecto (ADR 0024).

El mapa conceptual, las metas y los requisitos se guardan como un documento por proyecto
(colecciones `fase_mapa`, `fase_metas`, `fase_requisitos`, con el id del proyecto):

    {proyecto_id, fase, estado: propuesto|validado, contenido, huella_origen, avisos,
     historial, modelo, prompt_version, generado, actualizado}

`huella_origen` es la huella de lo validado en las fases anteriores cuando se generó (o
cuando la persona decidió conservarlo). Si lo de atrás cambia —alguien corrige el LEL
después de generar el mapa—, el documento ya no está «al día»: se puede volver a generar
o conservar tal cual.

Las fases van en orden y cada una se abre cuando la anterior quedó validada:

    entrevista → léxico → mapa → metas → requisitos
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from app.db.repositorio import Repositorio
from app.entrevistas import almacen as ea

from .lexico import huella_lexico, resumen as resumen_lexico

FASES = ("entrevista", "lexico", "mapa", "metas", "requisitos")
COLECCIONES = {"mapa": "fase_mapa", "metas": "fase_metas", "requisitos": "fase_requisitos"}
MAX_HISTORIAL = 200


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha(datos) -> str:
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def huella_contenido(fase: str, contenido: dict) -> str:
    """Lo que hereda la fase siguiente: el contenido sin posiciones ni marcas de validación."""
    if fase == "mapa":
        return _sha([contenido["proposito"], contenido["central"],
                     sorted((c["id"], c["etiqueta"], c.get("simbolo")) for c in contenido["conceptos"]),
                     sorted((r["origen"], r["enlace"], r["destino"]) for r in contenido["relaciones"])])
    if fase == "metas":
        return _sha(sorted((m["id"], m["nivel"], m["enunciado"], m.get("contribuye_a"), m.get("indicador"))
                           for m in contenido["metas"]))
    return _sha(sorted((r["id"], r["texto"], r["tipo"], tuple(r["metas"])) for r in contenido["requisitos"]))


def validado(fase: str, contenido: dict) -> bool:
    """Un documento queda validado cuando la persona validó cada uno de sus componentes."""
    if fase == "mapa":
        return bool(contenido.get("proposito_validado")) and all(c["validado"] for c in contenido["conceptos"]) \
            and all(r["validado"] for r in contenido["relaciones"])
    if fase == "metas":
        return all(m["validada"] for m in contenido["metas"])
    return all(r["validado"] for r in contenido["requisitos"])


def pendientes(fase: str, contenido: dict) -> int:
    if fase == "mapa":
        return (0 if contenido.get("proposito_validado") else 1) + sum(not c["validado"] for c in contenido["conceptos"]) \
            + sum(not r["validado"] for r in contenido["relaciones"])
    if fase == "metas":
        return sum(not m["validada"] for m in contenido["metas"])
    return sum(not r["validado"] for r in contenido["requisitos"])


class DocumentosDeFase:
    def __init__(self, repo: Repositorio):
        self.repo = repo

    def obtener(self, fase: str, proyecto_id: str) -> dict | None:
        return self.repo.obtener_doc(COLECCIONES[fase], proyecto_id)

    def guardar(self, fase: str, doc: dict) -> dict:
        doc["historial"] = doc.get("historial", [])[-MAX_HISTORIAL:]
        doc["estado"] = "validado" if validado(fase, doc["contenido"]) else "propuesto"
        doc["pendientes"] = pendientes(fase, doc["contenido"])
        self.repo.guardar_doc(COLECCIONES[fase], doc["proyecto_id"], doc)
        return doc

    def borrar(self, fase: str, proyecto_id: str) -> bool:
        return self.repo.borrar_doc(COLECCIONES[fase], proyecto_id)

    def borrar_de_proyecto(self, proyecto_id: str) -> None:
        for coleccion in COLECCIONES.values():
            self.repo.borrar_doc(coleccion, proyecto_id)

    # ------------------------------------------------------------ huellas en cadena

    def huellas(self, proyecto_id: str, entradas: list[dict], acuerdos: list[dict]) -> dict[str, str]:
        """La huella de lo que hereda cada fase: el mapa hereda el LEL; las metas, el LEL y el mapa;
        los requisitos, los tres."""
        lex = huella_lexico(entradas, acuerdos)
        mapa = self.obtener("mapa", proyecto_id)
        metas = self.obtener("metas", proyecto_id)
        hm = huella_contenido("mapa", mapa["contenido"]) if mapa else ""
        hmt = huella_contenido("metas", metas["contenido"]) if metas else ""
        return {"mapa": lex, "metas": _sha([lex, hm]), "requisitos": _sha([lex, hm, hmt])}


def estado_del_proyecto(repo: Repositorio, proyecto_id: str, entrevistas: list[dict], entradas: list[dict],
                        acuerdos: list[dict], ocupadas: set[str]) -> dict:
    """En qué va cada fase y cuál sigue. `ocupadas`: entrevistas en la cola o procesándose."""
    docs = DocumentosDeFase(repo)
    en_proceso = sum(1 for e in entrevistas if e["entrevista_id"] in ocupadas or e["estado"] not in ea.TERMINALES)
    listas = sum(1 for e in entrevistas if e["estado"] == ea.LISTA)
    ent = {"total": len(entrevistas), "en_proceso": en_proceso, "listas": listas,
           "con_error": sum(1 for e in entrevistas if e["estado"] == ea.ERROR),
           "canceladas": sum(1 for e in entrevistas if e["estado"] == ea.CANCELADA)}
    lex = {**resumen_lexico(entradas), "aprendidos": len(acuerdos)}
    huellas = docs.huellas(proyecto_id, entradas, acuerdos)

    fases = []
    hecho_previo = True

    def agregar(fid: str, disponible: bool, hecho: bool, motivo: str | None, **extra) -> None:
        nonlocal hecho_previo
        fases.append({"id": fid, "disponible": disponible, "hecho": hecho, "motivo": None if disponible else motivo,
                      **extra})
        hecho_previo = hecho

    agregar("entrevista", True, listas > 0 and en_proceso == 0, None, **ent)
    agregar("lexico", listas > 0, hecho_previo and lex["completo"],
            "Primero procesa una entrevista.", **lex)
    for fid, previa in (("mapa", "el léxico"), ("metas", "el mapa conceptual"), ("requisitos", "las metas")):
        d = docs.obtener(fid, proyecto_id)
        al_dia = bool(d) and d.get("huella_origen") == huellas[fid]
        info = {"existe": bool(d), "estado": d["estado"] if d else None, "al_dia": al_dia,
                "pendientes": d.get("pendientes") if d else None, "generado": d.get("generado") if d else None}
        disponible = hecho_previo
        agregar(fid, disponible, disponible and bool(d) and d["estado"] == "validado" and al_dia,
                f"Primero valida {previa}.", **info)
    siguiente = next((f["id"] for f in fases if not f["hecho"]), None)
    return {"proyecto_id": proyecto_id, "fases": fases, "siguiente": siguiente, "entrevistas": ent, "lexico": lex}
