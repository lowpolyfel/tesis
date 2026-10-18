"""El informe de calibración sobre entrevistas y las corridas guardadas (ADR 0026).

`informe_entrevistas` es una función pura: recibe entrevistas, bitácoras y etiquetas ya
leídas y responde qué habría decidido «similitud >= umbral» con cada umbral de la rejilla,
cuánto separa la similitud los casos ambiguos (ROC, AUC) y con qué incertidumbre
(intervalos bootstrap). Como en ADR 0013, no cambia la configuración, no recalcula
embeddings y no elige ni recomienda un umbral.

Una **corrida** congela ese informe con la configuración, la versión de la app y una huella
de las similitudes y etiquetas de cada entrevista: es la evidencia que se cita en la tesis y
se exporta a Overleaf. Volver a calcular con los mismos datos da el mismo resultado (la
semilla del bootstrap es fija); si los datos cambiaron, la huella lo dice.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Iterable

from app.divergence.similitud import decidir

from .anotaciones import consolidar, desde_legado
from .entrevistas import similitudes_de_entrevista
from .estadistica import (
    auc,
    banda_roc,
    bootstrap,
    confusion,
    emparejar,
    por_tipo,
    rejilla_con_etiquetas,
    roc,
    separacion,
)
from .sensibilidad import distribucion, rejilla

COLECCION_CORRIDAS = "calibraciones"
MUESTRA_CHICA = 20  # pares etiquetados: por debajo, los intervalos son anchos y se avisa

NOTA = ("Análisis de sensibilidad sobre las entrevistas: qué habría decidido la regla «similitud >= umbral» con "
        "otros umbrales, sobre las similitudes iniciales (ronda 0) ya calculadas, y cuánto separa la similitud los "
        "términos que la persona anotadora marcó como ambiguos (ROC, AUC e intervalos bootstrap al 95 %). No cambia "
        "la configuración y no elige un umbral: si la similitud no separa los casos, es un hallazgo.")


def _sensibilidad(valores: list[dict], umbrales: Iterable[float], configurado: float) -> list[dict]:
    filas = []
    for u in umbrales:
        directos, cambian = 0, []
        for v in valores:
            decision = decidir(v["similitud"], u).value
            directos += decision == "aceptado_directo"
            if decision != v["decision_real"]:
                cambian.append({"entrevista_id": v["entrevista_id"], "termino": v["termino"],
                                "similitud": v["similitud"], "decision_real": v["decision_real"],
                                "decision_con_umbral": decision})
        filas.append({"umbral": u, "configurado": u == configurado, "directos": directos,
                      "debates": len(valores) - directos, "cambian": cambian})
    return filas


def _avisos(valores: list[dict], gt: dict | None, modelos: list[str], umbrales_usados: list[float],
            umbral: float) -> list[str]:
    avisos = []
    if not valores:
        avisos.append("sin similitudes: ninguna entrevista terminada tiene términos que llegaran al mecanismo de "
                      "divergencia")
    if len(modelos) > 1:
        avisos.append(f"las similitudes vienen de {len(modelos)} modelos de embeddings distintos "
                      f"({', '.join(modelos)}): no son comparables entre sí")
    otros = [u for u in umbrales_usados if u != umbral]
    if otros:
        avisos.append(f"hay términos decididos con un umbral distinto del configurado ({', '.join(map(str, otros))})")
    if gt is None:
        if valores:
            avisos.append("sin ground truth: etiqueta en cada entrevista qué términos son ambiguos para tener "
                          "precisión, exhaustividad, F1 y la curva ROC")
        return avisos
    n = gt["n_emparejados"]
    if 0 < n < MUESTRA_CHICA:
        avisos.append(f"muestra chica ({n} términos etiquetados con similitud): un solo caso mueve las proporciones "
                      "varios puntos; los intervalos lo muestran")
    if n and min(gt["n_ambiguos"], gt["n_no_ambiguos"]) < max(3, n // 5):
        avisos.append(f"clases desbalanceadas ({gt['n_ambiguos']} ambiguos y {gt['n_no_ambiguos']} no ambiguos)")
    if gt["separacion"]["separa"] is False:
        avisos.append("ningún umbral separa los casos etiquetados: la similitud inicial no basta para distinguirlos "
                      "(es un hallazgo, no un ajuste pendiente)")
    if gt.get("desacuerdos"):
        avisos.append(f"{len(gt['desacuerdos'])} términos con desacuerdo entre personas anotadoras quedan fuera del "
                      "ground truth")
    if gt.get("solo_no_se"):
        avisos.append(f"{gt['solo_no_se']} términos solo con «no sé» quedan fuera del ground truth")
    if not any(a["kappa"] is not None for a in gt.get("acuerdo", [])):
        avisos.append("acuerdo entre personas anotadoras en «---»: hace falta que dos personas etiqueten la misma "
                      "entrevista (kappa de Cohen)")
    if not gt["a_ciegas"]:
        avisos.append("hay entrevistas etiquetadas viendo la similitud o la decisión del sistema: el ground truth "
                      "puede estar sesgado hacia él")
    return avisos


def informe_entrevistas(entrevistas: Iterable[tuple[dict, dict]], docs_etiquetas: Iterable[dict], *,
                        umbral_configurado: float, max_rondas: int, desde: float, hasta: float, paso: float,
                        remuestreos: int, semilla: int, proyecto_id: str | None = None,
                        anotaciones: Iterable[dict] = ()) -> dict:
    """`entrevistas`: pares (documento de la entrevista, su bitácora). Forma::

        {proyecto_id, umbral_configurado, max_rondas, parametros{desde, hasta, paso},
         entrevistas: [{entrevista_id, titulo, estado, n_valores, n_etiquetas, anotador, a_ciegas}],
         n_valores, valores, umbrales_usados, modelos_embeddings, modelos_clasificador,
         distribucion, rejilla: [{umbral, configurado, directos, debates, cambian}],
         con_ground_truth | null: {n_etiquetas, n_emparejados, n_ambiguos, n_no_ambiguos, a_ciegas,
           etiquetas_sin_similitud, valores_sin_etiqueta, separacion, por_umbral, configurado,
           roc, roc_banda, auc, confianza, por_tipo, acuerdo, desacuerdos, solo_no_se},
         avisos, nota}

    `docs_etiquetas`: los documentos de la v2.2 (uno por entrevista); `anotaciones`: los de cada
    persona anotadora (ADR 0029). Se consolidan: cuenta el valor en el que coinciden todas.
    """
    entrevistas = list(entrevistas)
    ids = {e["entrevista_id"] for e, _ in entrevistas}
    consolidado = consolidar([desde_legado(d) for d in docs_etiquetas if d["entrevista_id"] in ids] +
                             [a for a in anotaciones if a["entrevista_id"] in ids])
    docs = {eid: {"entrevista_id": eid, "anotador": ", ".join(r["anotadores"]) or None, "a_ciegas": r["a_ciegas"],
                  "anotadores": r["anotadores"],
                  "etiquetas": [x for x in consolidado["etiquetas"] if x["entrevista_id"] == eid]}
            for eid, r in consolidado["por_entrevista"].items()}
    valores, resumen = [], []
    for e, b in entrevistas:
        vs = similitudes_de_entrevista(e, b)
        d = docs.get(e["entrevista_id"])
        valores += vs
        resumen.append({"entrevista_id": e["entrevista_id"], "titulo": e.get("titulo"), "estado": e.get("estado"),
                        "n_valores": len(vs), "n_etiquetas": len(d["etiquetas"]) if d else 0,
                        "anotador": d.get("anotador") if d else None, "a_ciegas": d.get("a_ciegas") if d else None,
                        "anotadores": d.get("anotadores", []) if d else []})
    etiquetas = consolidado["etiquetas"]
    umbrales = rejilla(desde, hasta, paso, incluir=umbral_configurado)
    umbrales_usados = sorted({v["umbral_usado"] for v in valores if v["umbral_usado"] is not None})
    modelos = sorted({v["modelo_embeddings"] for v in valores if v["modelo_embeddings"]})

    gt = None
    if etiquetas:
        e = emparejar(valores, etiquetas)
        pares = e["pares"]
        etiquetados = {d["entrevista_id"] for d in docs.values() if d.get("etiquetas")}
        gt = {
            "n_etiquetas": len(etiquetas), "n_emparejados": len(pares),
            "n_ambiguos": sum(1 for _, x in pares if x["ambiguo"]),
            "n_no_ambiguos": sum(1 for _, x in pares if not x["ambiguo"]),
            "a_ciegas": all(docs[i].get("a_ciegas") for i in etiquetados),
            "etiquetas_sin_similitud": [{k: x[k] for k in ("entrevista_id", "termino", "ambiguo", "tipo")}
                                        for x in e["etiquetas_sin_similitud"]],
            # solo cuentan como faltantes los valores de entrevistas que sí se etiquetaron
            "valores_sin_etiqueta": [{k: v[k] for k in ("entrevista_id", "termino", "similitud")}
                                     for v in e["valores_sin_etiqueta"] if v["entrevista_id"] in etiquetados],
            "separacion": separacion(pares),
            "por_umbral": rejilla_con_etiquetas(pares, umbrales, umbral_configurado),
            "configurado": confusion(pares, umbral_configurado),
            "roc": roc(pares),
            "roc_banda": banda_roc(pares, remuestreos, semilla),
            "auc": auc(pares),
            "confianza": bootstrap(pares, umbral_configurado, remuestreos, semilla),
            "por_tipo": por_tipo(pares, umbral_configurado),
            "acuerdo": consolidado["acuerdo"],
            "desacuerdos": consolidado["desacuerdos"],
            "solo_no_se": consolidado["solo_no_se"],
        }
        ambiguo = {(v["entrevista_id"], v["termino"]): x["ambiguo"] for v, x in pares}
        valores = [{**v, "ambiguo": ambiguo.get((v["entrevista_id"], v["termino"]))} for v in valores]
    else:
        valores = [{**v, "ambiguo": None} for v in valores]

    return {
        "proyecto_id": proyecto_id,
        "umbral_configurado": umbral_configurado,
        "max_rondas": max_rondas,
        "parametros": {"desde": desde, "hasta": hasta, "paso": paso},
        "entrevistas": resumen,
        "n_valores": len(valores),
        "valores": valores,
        "umbrales_usados": umbrales_usados,
        "modelos_embeddings": modelos,
        "modelos_clasificador": sorted({v["modelo_clasificador"] for v in valores if v["modelo_clasificador"]}),
        "distribucion": distribucion(valores, paso, origen=desde),
        "rejilla": _sensibilidad(valores, umbrales, umbral_configurado),
        "con_ground_truth": gt,
        "avisos": _avisos(valores, gt, modelos, umbrales_usados, umbral_configurado),
        "nota": NOTA,
    }


# ---------------------------------------------------------------- corridas guardadas

def huella(x) -> str:
    """sha256 corto de un valor JSON (ordenado): cambia si cambian los datos que entraron."""
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def nueva_corrida(calibracion_id: str, informe: dict, *, nota: str | None, version: str, configuracion: dict,
                  docs_etiquetas: Iterable[dict], anotaciones: Iterable[dict] = ()) -> dict:
    """El documento de una corrida: el informe completo más lo necesario para citarla y reproducirla.
    La huella de las etiquetas, sin anotaciones por persona, se calcula igual que en la v2.2 (las
    corridas viejas se reproducen igual); con anotaciones, entran también sus respuestas."""
    por_entrevista: dict[str, list] = {}
    for v in informe["valores"]:
        por_entrevista.setdefault(v["entrevista_id"], []).append(
            [v["termino"], v["similitud"], v["decision_real"], v["modelo_embeddings"]])
    etiquetas: dict[str, object] = {d["entrevista_id"]: d.get("etiquetas", []) for d in docs_etiquetas}
    por_persona: dict[str, list] = {}
    for a in anotaciones:
        por_persona.setdefault(a["entrevista_id"], []).append(
            [a["anotador"], a.get("a_ciegas"), sorted((k, r["respuesta"]) for k, r in a["respuestas"].items())])
    for eid, filas in por_persona.items():
        etiquetas[eid] = {"v2.2": etiquetas.get(eid, []), "anotadores": sorted(filas, key=str)}
    return {
        "calibracion_id": calibracion_id,
        "proyecto_id": informe["proyecto_id"],
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "nota": nota,
        "version_app": version,
        "configuracion": configuracion,
        "entrevistas": [{**e, "huella_similitudes": huella(por_entrevista.get(e["entrevista_id"], [])),
                         "huella_etiquetas": huella(etiquetas.get(e["entrevista_id"], []))}
                        for e in informe["entrevistas"]],
        "resultado": informe,
    }


def resumen_corrida(c: dict) -> dict:
    """Lo que se ve en la lista de corridas."""
    r = c["resultado"]
    gt = r.get("con_ground_truth") or {}
    medidas = (gt.get("confianza") or {}).get("medidas", {})
    configurado = gt.get("configurado") or {}
    return {
        "calibracion_id": c["calibracion_id"], "proyecto_id": c["proyecto_id"], "fecha": c["fecha"],
        "nota": c.get("nota"), "version_app": c.get("version_app"), "umbral": r["umbral_configurado"],
        "n_entrevistas": len(r["entrevistas"]), "n_valores": r["n_valores"],
        "n_emparejados": gt.get("n_emparejados", 0), "auc": gt.get("auc"), "auc_ic": medidas.get("auc"),
        "f1": configurado.get("f1"), "f1_ic": medidas.get("f1"),
        "separa": (gt.get("separacion") or {}).get("separa"),
        "modelos_embeddings": r["modelos_embeddings"],
    }
