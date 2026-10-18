"""Medidas del contraste entre la similitud inicial y el ground truth (ADR 0026).

La clase positiva es «debate» (similitud < umbral) y la verdad es `ambiguo`, como en
ADR 0013. Además de la rejilla de umbrales:

- **ROC y AUC**: cuánto separa la similitud los casos ambiguos de los que no lo son,
  sin elegir ningún umbral. AUC = probabilidad de que un término ambiguo tenga menor
  similitud que uno que no lo es (los empates cuentan la mitad); 0.5 es el azar.
- **Intervalos bootstrap** (percentiles, remuestreo de los pares con reemplazo y semilla
  fija): con 15–40 términos un solo caso mueve varios puntos, y el intervalo lo dice.
- **Desglose por tipo** de ambigüedad (el tipo que puso la persona anotadora).

Nada de esto elige ni recomienda un umbral: solo describe.
"""
from __future__ import annotations

import random
from typing import Iterable

from app.divergence.similitud import decidir
from app.models import Estado

from .entrevistas import clave
from .ground_truth import metricas
from .sensibilidad import redondear

NIVEL = 0.95


def emparejar(valores: list[dict], etiquetas: list[dict]) -> dict:
    """Pares (valor, etiqueta) por entrevista y término normalizado, y lo que quedó sin pareja."""
    por_clave = {clave(e["entrevista_id"], e["termino"]): e for e in etiquetas}
    claves_valores = {clave(v["entrevista_id"], v["termino"]) for v in valores}
    pares = [(v, por_clave[k]) for v in valores if (k := clave(v["entrevista_id"], v["termino"])) in por_clave]
    return {
        "pares": pares,
        "etiquetas_sin_similitud": [e for k, e in por_clave.items() if k not in claves_valores],
        "valores_sin_etiqueta": [v for v in valores if clave(v["entrevista_id"], v["termino"]) not in por_clave],
    }


def confusion(pares: list[tuple[dict, dict]], umbral: float) -> dict:
    """VP, FP, VN, FN y sus métricas con un umbral, y los casos mal separados."""
    vp = fp = vn = fn = 0
    mal = []
    for v, e in pares:
        debate = decidir(v["similitud"], umbral) == Estado.EN_DEBATE
        if debate and e["ambiguo"]:
            vp += 1
        elif not debate and not e["ambiguo"]:
            vn += 1
        else:
            fp, fn = (fp + 1, fn) if debate else (fp, fn + 1)
            mal.append({"entrevista_id": v["entrevista_id"], "termino": v["termino"], "similitud": v["similitud"],
                        "ambiguo": e["ambiguo"], "tipo_error": "falso_positivo" if debate else "falso_negativo"})
    return {**metricas(vp, fp, vn, fn), "mal_separados": mal}


def auc(pares: list[tuple[dict, dict]]) -> float | None:
    """Área bajo la curva ROC (Mann–Whitney): null si falta una de las dos clases."""
    amb = [v["similitud"] for v, e in pares if e["ambiguo"]]
    no = [v["similitud"] for v, e in pares if not e["ambiguo"]]
    if not amb or not no:
        return None
    ganadas = sum((a < b) + 0.5 * (a == b) for a in amb for b in no)
    return redondear(ganadas / (len(amb) * len(no)))


def roc(pares: list[tuple[dict, dict]]) -> list[dict]:
    """Puntos de la curva ROC, de (0, 0) a (1, 1): para cada umbral que cambia algo, la tasa de
    falsos positivos (no ambiguos a debate) y la de verdaderos positivos (ambiguos a debate)::

        [{hasta, fpr, tpr}]   (hasta: la similitud hasta la que se va a debate, inclusive;
                               null en los extremos)
    """
    amb = sum(1 for _, e in pares if e["ambiguo"])
    no = len(pares) - amb
    if not amb or not no:
        return []
    puntos = [{"hasta": None, "fpr": 0.0, "tpr": 0.0}]
    # con «debate si similitud < umbral», cada similitud distinta (más un poco) abre un escalón
    for s in sorted({v["similitud"] for v, _ in pares}):
        u = s + 1e-9
        vp = sum(1 for v, e in pares if e["ambiguo"] and v["similitud"] < u)
        fp = sum(1 for v, e in pares if not e["ambiguo"] and v["similitud"] < u)
        puntos.append({"hasta": redondear(s), "fpr": redondear(fp / no), "tpr": redondear(vp / amb)})
    if (puntos[-1]["fpr"], puntos[-1]["tpr"]) != (1.0, 1.0):
        puntos.append({"hasta": None, "fpr": 1.0, "tpr": 1.0})
    return puntos


def _percentil(ordenados: list[float], q: float) -> float:
    """Percentil con interpolación lineal (el método por omisión de numpy)."""
    i = (len(ordenados) - 1) * q
    a, b = int(i), min(int(i) + 1, len(ordenados) - 1)
    return redondear(ordenados[a] + (ordenados[b] - ordenados[a]) * (i - a))


def bootstrap(pares: list[tuple[dict, dict]], umbral: float, remuestreos: int, semilla: int) -> dict:
    """Intervalos de confianza percentil al 95 % para AUC, precisión, exhaustividad y F1 con el
    umbral dado. Un remuestreo sin las dos clases no tiene AUC, y uno sin debates no tiene
    precisión: se descartan para esa medida y se dice cuántos quedaron::

        {nivel, remuestreos, semilla, medidas: {auc|precision|exhaustividad|f1: {bajo, alto, validos}}}
    """
    rng = random.Random(semilla)
    muestras: dict[str, list[float]] = {"auc": [], "precision": [], "exhaustividad": [], "f1": []}
    n = len(pares)
    for _ in range(remuestreos if n else 0):
        m = [pares[rng.randrange(n)] for _ in range(n)]
        a = auc(m)
        if a is not None:
            muestras["auc"].append(a)
        c = confusion(m, umbral)
        for k in ("precision", "exhaustividad", "f1"):
            if c[k] is not None:
                muestras[k].append(c[k])
    cola = (1 - NIVEL) / 2
    medidas = {}
    for k, xs in muestras.items():
        xs.sort()
        medidas[k] = ({"bajo": _percentil(xs, cola), "alto": _percentil(xs, 1 - cola), "validos": len(xs)}
                      if xs else {"bajo": None, "alto": None, "validos": 0})
    return {"nivel": NIVEL, "remuestreos": remuestreos, "semilla": semilla, "medidas": medidas}


def por_tipo(pares: list[tuple[dict, dict]], umbral: float) -> list[dict]:
    """Por tipo de ambigüedad (el de la etiqueta; si no lo puso, el del Clasificador): cuántos
    términos ambiguos hay, cuántos manda a debate el umbral y la exhaustividad. Los no ambiguos
    van en su propia fila, con cuántos irían a debate de más (falsos positivos)::

        [{tipo, ambiguo, n, a_debate, proporcion}]
    """
    grupos: dict[tuple[str, bool], list[float]] = {}
    for v, e in pares:
        tipo = (e.get("tipo") or v.get("tipo_ambiguedad") or "lexica") if e["ambiguo"] else "no_ambiguo"
        grupos.setdefault((tipo, e["ambiguo"]), []).append(v["similitud"])
    filas = []
    for (tipo, ambiguo), sims in sorted(grupos.items(), key=lambda x: (not x[0][1], x[0][0])):
        a_debate = sum(1 for s in sims if decidir(s, umbral) == Estado.EN_DEBATE)
        filas.append({"tipo": tipo, "ambiguo": ambiguo, "n": len(sims), "a_debate": a_debate,
                      "proporcion": redondear(a_debate / len(sims))})
    return filas


def separacion(pares: list[tuple[dict, dict]]) -> dict:
    """Si existe un umbral que manda a debate todos los ambiguos y ninguno de los otros."""
    amb = [v["similitud"] for v, e in pares if e["ambiguo"]]
    no = [v["similitud"] for v, e in pares if not e["ambiguo"]]
    max_amb, min_no = (max(amb) if amb else None), (min(no) if no else None)
    return {"max_ambiguos": max_amb, "min_no_ambiguos": min_no, "separa": (max_amb < min_no) if amb and no else None}


def rejilla_con_etiquetas(pares: list[tuple[dict, dict]], umbrales: Iterable[float], configurado: float) -> list[dict]:
    """La matriz de confusión y las métricas en cada umbral de la rejilla."""
    return [{"umbral": u, "configurado": u == configurado, **confusion(pares, u)} for u in umbrales]


def _tpr_en(curva: list[dict], fpr: float) -> float:
    """La tasa de verdaderos positivos de una curva ROC escalonada en una tasa de falsos positivos."""
    return max(p["tpr"] for p in curva if p["fpr"] <= fpr + 1e-12)


def banda_roc(pares: list[tuple[dict, dict]], remuestreos: int, semilla: int, pasos: int = 20) -> list[dict]:
    """Banda bootstrap (percentil, puntual) de la curva ROC: en cada tasa de falsos positivos de una
    rejilla de `pasos` + 1 puntos, los percentiles de la tasa de verdaderos positivos sobre los
    remuestreos que tienen las dos clases. Usa la misma semilla que los intervalos::

        [{fpr, bajo, alto, validos}]   ([] si falta una clase)
    """
    if not roc(pares):
        return []
    rng = random.Random(semilla)
    n = len(pares)
    rejilla_fpr = [k / pasos for k in range(pasos + 1)]
    muestras: list[list[float]] = [[] for _ in rejilla_fpr]
    for _ in range(remuestreos):
        curva = roc([pares[rng.randrange(n)] for _ in range(n)])
        if curva:
            for j, f in enumerate(rejilla_fpr):
                muestras[j].append(_tpr_en(curva, f))
    cola = (1 - NIVEL) / 2
    banda = []
    for f, xs in zip(rejilla_fpr, muestras):
        xs.sort()
        banda.append({"fpr": f, "bajo": _percentil(xs, cola) if xs else None,
                      "alto": _percentil(xs, 1 - cola) if xs else None, "validos": len(xs)})
    return banda
