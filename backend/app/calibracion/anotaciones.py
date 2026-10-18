"""Etiquetado de los términos de entrevista por varias personas anotadoras (ADR 0029).

La calibración del umbral (ADR 0026) no puede dar precisión, exhaustividad, F1 ni ROC sin saber
qué términos eran de verdad ambiguos. Aquí se construye ese ground truth con la misma disciplina
que la revisión de la prueba de modelos:

- solo los términos que **llegaron al mecanismo de divergencia** (los que tienen similitud);
- **a ciegas**: la persona ve el término, sus citas y el contexto, nunca la similitud ni la
  decisión del sistema (un 0.66 a la vista ya sesga la respuesta);
- **orden barajado** con semilla guardada (reconstruible);
- respuestas **sí / no / no sé**;
- **varias personas** por entrevista: un documento por entrevista y persona
  (`etiquetas_anotadores`, ids A01, A02…), y el acuerdo entre cada par con la kappa de Cohen.

El documento único por entrevista de la v2.2 (`etiquetas_entrevista`) se sigue leyendo como el
de una persona más; no se migra.

**Ground truth consolidado** (lo que usa la calibración): por término, el valor en el que
coinciden todas las personas que contestaron sí o no. Un desacuerdo, o solo «no sé», deja el
término fuera, y se cuenta.

Funciones puras: nada aquí llama a un LLM ni a los embeddings, ni toca el umbral.
"""
from __future__ import annotations

import random
import secrets
from collections.abc import Iterable
from datetime import UTC, datetime
from itertools import combinations

from app.fases.claves import fragmento
from app.nlp import normalizar

from .entrevistas import similitudes_de_entrevista

COLECCION_ANOTACIONES = "etiquetas_anotadores"
PREFIJO = "A"
RESPUESTAS = ("si", "no", "no_se")
CITAS_POR_TERMINO = 3


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def terminos_para_etiquetar(entrevista: dict, bitacora: dict) -> list[dict]:
    """Los términos que llegaron a la divergencia, con sus citas y SIN la similitud ni la decisión::

        [{termino, clave, citas: [{turno, hablante, fragmento}]}]
    """
    turnos = {t["n"]: t for t in entrevista.get("turnos", [])}
    filtrado = [m for m in bitacora.get("mensajes", []) if m["tipo"] == "filtrado"]
    turnos_de = {}
    for t in (filtrado[-1]["payload"].get("terminos", []) if filtrado else []):
        turnos_de.setdefault(normalizar(t.get("termino", "")), t.get("turnos") or [])
    salida, vistos = [], set()
    for v in similitudes_de_entrevista(entrevista, bitacora):
        k = normalizar(v["termino"])
        if k in vistos:
            continue
        vistos.add(k)
        citas = [{"turno": n, "hablante": turnos[n].get("hablante"), "fragmento": fragmento(turnos[n]["texto"], v["termino"])}
                 for n in turnos_de.get(k, [])[:CITAS_POR_TERMINO] if n in turnos]
        salida.append({"termino": v["termino"], "clave": k, "citas": citas})
    return salida


def nueva_anotacion(aid: str, entrevista: dict, terminos: list[dict], *, anotador: str, a_ciegas: bool,
                    semilla: int | None = None) -> dict:
    semilla = secrets.randbelow(2 ** 31) if semilla is None else semilla
    orden = [t["clave"] for t in terminos]
    random.Random(semilla).shuffle(orden)
    return {"anotacion_id": aid, "entrevista_id": entrevista["entrevista_id"], "proyecto_id": entrevista.get("proyecto_id"),
            "anotador": anotador, "a_ciegas": a_ciegas, "semilla": semilla, "orden": orden, "respuestas": {},
            "creada": ahora(), "actualizada": ahora()}


def completar_orden(doc: dict, terminos: list[dict]) -> bool:
    """Términos que aparecieron después (la entrevista se volvió a procesar) van al final, barajados
    con una semilla derivada; lo ya etiquetado no se mueve."""
    nuevos = [t["clave"] for t in terminos if t["clave"] not in doc["orden"]]
    if not nuevos:
        return False
    random.Random(f"{doc['semilla']}:{len(doc['orden'])}").shuffle(nuevos)
    doc["orden"] += nuevos
    return True


def responder(doc: dict, *, termino: str, respuesta: str | None) -> None:
    if respuesta is not None and respuesta not in RESPUESTAS:
        raise ValueError(f"respuesta desconocida: {respuesta}")
    k = normalizar(termino)
    if respuesta is None:
        doc["respuestas"].pop(k, None)
    else:
        doc["respuestas"][k] = {"termino": termino, "respuesta": respuesta, "fecha": ahora()}
    doc["actualizada"] = ahora()


def desde_legado(doc: dict) -> dict:
    """El documento de la v2.2 (uno por entrevista) como si fuera el de una persona más."""
    return {"anotacion_id": None, "entrevista_id": doc["entrevista_id"], "proyecto_id": doc.get("proyecto_id"),
            "anotador": doc.get("anotador") or "(v2.2)", "a_ciegas": bool(doc.get("a_ciegas")), "legado": True,
            "respuestas": {normalizar(e["termino"]): {"termino": e["termino"], "respuesta": "si" if e["ambiguo"] else "no",
                                                      "tipo": e.get("tipo")}
                           for e in doc.get("etiquetas", [])}}


# ---------------------------------------------------------------- acuerdo

def kappa(a: dict[str, bool], b: dict[str, bool]) -> dict:
    """Kappa de Cohen entre dos personas sobre los términos que las dos contestaron con sí o no::

        {n, acuerdo_observado, kappa}

    kappa es null si no hay términos en común o si las dos contestaron todo igual con una sola
    clase (el acuerdo esperado es 1 y la fórmula no se define)."""
    comunes = [k for k in a if k in b]
    n = len(comunes)
    if not n:
        return {"n": 0, "acuerdo_observado": None, "kappa": None}
    po = sum(a[k] == b[k] for k in comunes) / n
    pa, pb = sum(a[k] for k in comunes) / n, sum(b[k] for k in comunes) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return {"n": n, "acuerdo_observado": po, "kappa": None if pe == 1 else (po - pe) / (1 - pe)}


def _binarias(doc: dict) -> dict[str, bool]:
    return {k: r["respuesta"] == "si" for k, r in doc["respuestas"].items() if r["respuesta"] in ("si", "no")}


def acuerdo(docs: list[dict]) -> list[dict]:
    """Kappa por cada par de personas de una misma entrevista."""
    salida = []
    for x, y in combinations(docs, 2):
        salida.append({"entrevista_id": x["entrevista_id"], "a": x["anotador"], "b": y["anotador"],
                       **kappa(_binarias(x), _binarias(y))})
    return salida


def consolidar(docs: Iterable[dict]) -> dict:
    """El ground truth de todas las personas, por entrevista y término::

        {etiquetas: [{entrevista_id, termino, ambiguo, tipo, a_ciegas, anotador}],
         desacuerdos: [{entrevista_id, termino, respuestas: {anotador: respuesta}}],
         solo_no_se: n, por_entrevista: {eid: {anotadores, a_ciegas, n_etiquetas}}, acuerdo: [...]}

    `etiquetas` tiene la forma de `entrevistas.etiquetas_planas`, para que la calibración no cambie.
    """
    por_entrevista: dict[str, list[dict]] = {}
    for d in docs:
        por_entrevista.setdefault(d["entrevista_id"], []).append(d)
    etiquetas, desacuerdos, solo_no_se, resumen, pares_kappa = [], [], 0, {}, []
    for eid, ds in por_entrevista.items():
        claves = []
        for d in ds:
            claves += [k for k in d["respuestas"] if k not in claves]
        a_ciegas = all(d.get("a_ciegas") for d in ds)
        n = 0
        for k in claves:
            resp = {d["anotador"]: d["respuestas"][k] for d in ds if k in d["respuestas"]}
            decididas = {a: r["respuesta"] for a, r in resp.items() if r["respuesta"] in ("si", "no")}
            if not decididas:
                solo_no_se += 1
                continue
            if len(set(decididas.values())) > 1:
                desacuerdos.append({"entrevista_id": eid, "termino": next(iter(resp.values()))["termino"],
                                    "respuestas": {a: r["respuesta"] for a, r in resp.items()}})
                continue
            primera = next(r for r in resp.values() if r["respuesta"] in ("si", "no"))
            etiquetas.append({"entrevista_id": eid, "termino": primera["termino"], "ambiguo": primera["respuesta"] == "si",
                              "tipo": primera.get("tipo"), "a_ciegas": a_ciegas,
                              "anotador": ", ".join(sorted(decididas))})
            n += 1
        resumen[eid] = {"anotadores": [d["anotador"] for d in ds], "a_ciegas": a_ciegas, "n_etiquetas": n}
        pares_kappa += acuerdo(ds)
    return {"etiquetas": etiquetas, "desacuerdos": desacuerdos, "solo_no_se": solo_no_se, "por_entrevista": resumen,
            "acuerdo": pares_kappa}
