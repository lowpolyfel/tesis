"""Análisis de sensibilidad del umbral sobre similitudes ya calculadas (ADR 0013).

Funciones puras: no llaman a los embeddings ni a ningún LLM y no cambian la
configuración. Responden «qué habría decidido la regla `similitud >= umbral`
con otro umbral», usando la misma función `decidir` que el grafo.
"""
from __future__ import annotations

import math
import statistics
from bisect import bisect_right
from typing import Iterable

from app.divergence.similitud import decidir
from app.models import Estado, TipoAmbiguedad, TipoMensaje, Traza, Via
from app.nlp import normalizar

DECIMALES = 6  # redondeo de umbrales y bordes: 0.5 + 5 * 0.05 debe ser 0.75 y no 0.7500000000000001
_TOLERANCIA = 1e-9  # para contar los puntos de la rejilla sin perder el último por error de punto flotante
_DECISIONES_INICIALES = {Estado.ACEPTADO_DIRECTO.value, Estado.EN_DEBATE.value}


def redondear(x: float) -> float:
    return round(x, DECIMALES)


def puntos_rejilla(desde: float, hasta: float, paso: float) -> int:
    """Cuántos umbrales tiene la rejilla de `desde` a `hasta` inclusive."""
    if paso <= 0:
        raise ValueError("el paso debe ser positivo")
    return 0 if hasta < desde else math.floor((hasta - desde) / paso + _TOLERANCIA) + 1


def rejilla(desde: float, hasta: float, paso: float, incluir: float | None = None) -> list[float]:
    """Umbrales `desde, desde + paso, …` hasta `hasta` inclusive, redondeados.

    `incluir` (el umbral configurado) se agrega tal cual aunque no caiga en la
    rejilla ni dentro del intervalo: es la fila que reproduce lo que pasó.
    """
    umbrales = {redondear(desde + i * paso) for i in range(puntos_rejilla(desde, hasta, paso))}
    if incluir is not None:
        umbrales.add(incluir)
    return sorted(umbrales)


# ---------------------------------------------------------------- similitudes de las trazas

def _orden_req(req_id: str) -> tuple[int, str]:
    return len(req_id), req_id


def _paso_por_divergencia(traza: Traza) -> bool:
    return any(m.tipo == TipoMensaje.SIMILITUD and m.ronda == 0 for m in traza.mensajes)


def reprocesados(trazas: Iterable[Traza]) -> set[str]:
    """req_id de las trazas que otra traza vuelve a procesar (`origen.reproceso_de`)
    cuando el reproceso ya pasó por el mecanismo de divergencia: contar ambas
    duplicaría el mismo requisito. Si el reproceso sigue en cola o falló antes de
    llegar, la traza anterior es la única similitud que hay y se conserva."""
    return {t.origen.reproceso_de for t in trazas
            if t.origen and t.origen.reproceso_de and _paso_por_divergencia(t)}


def _similitudes_de(traza: Traza) -> list[dict]:
    """Similitud inicial (ronda 0) de cada término de una traza, en orden de aparición.

    Un nodo reejecutado tras un reinicio repite sus mensajes (ADR 0008): cuenta la
    última clasificación y, por término, la última similitud inicial posterior a ella.
    """
    mensajes = sorted(traza.mensajes, key=lambda m: m.secuencia)
    ultima = next((m for m in reversed(mensajes) if m.tipo == TipoMensaje.INTERPRETACIONES), None)
    desde = ultima.secuencia if ultima else 0
    resultados = (ultima.payload.get("resultados") if ultima else None) or []
    tipos = {normalizar(r["termino"]): r.get("tipo_ambiguedad") for r in resultados if r.get("termino")}

    iniciales: dict[str, dict] = {}
    vias: dict[str, str] = {}
    for m in mensajes:
        p = m.payload or {}
        if m.secuencia <= desde or not p.get("termino"):
            continue
        clave = normalizar(p["termino"])
        if m.tipo == TipoMensaje.SIMILITUD and m.ronda == 0 and p.get("similitud") is not None:
            iniciales.pop(clave, None)  # la repetida queda en la posición de la última
            iniciales[clave] = {**p, "modelo_embeddings": p.get("modelo_embeddings") or m.modelo}
        elif m.tipo == TipoMensaje.CONSENSO:
            vias[clave] = Via.CONSENSO.value
        elif m.tipo == TipoMensaje.ARBITRAJE:
            vias[clave] = Via.ARBITRAJE.value

    salida = []
    for clave, p in iniciales.items():
        similitud, umbral = float(p["similitud"]), p.get("umbral")
        decision = p.get("decision")
        if decision not in _DECISIONES_INICIALES:
            decision = decidir(similitud, umbral).value if umbral is not None else None
        if decision is None:  # sin decisión ni umbral registrados no hay contra qué comparar
            continue
        salida.append({
            "req_id": traza.req_id,
            "proyecto_id": traza.proyecto_id,
            "ciclo": traza.ciclo,
            "termino": p["termino"],
            "similitud": similitud,
            "umbral_usado": umbral,
            "decision_real": decision,
            # Las trazas anteriores al tipo de ambigüedad se tratan como léxicas (ADR 0010 §5)
            "tipo_ambiguedad": tipos.get(clave) or TipoAmbiguedad.LEXICA.value,
            "via": Via.ACEPTADO_DIRECTO.value if decision == Estado.ACEPTADO_DIRECTO.value else vias.get(clave),
            "estado_requisito": traza.estado.value,
            "modelo_embeddings": p.get("modelo_embeddings"),
        })
    return salida


def extraer_similitudes(trazas: Iterable[Traza]) -> list[dict]:
    """Una fila por término que llegó al mecanismo de divergencia, con su similitud inicial::

        {req_id, proyecto_id, ciclo, termino, similitud, umbral_usado, decision_real,
         tipo_ambiguedad, via, estado_requisito, modelo_embeddings}

    Se ignoran las similitudes `null` (requisitos sin interpretaciones), las de
    rondas de debate (ya dependen del umbral real) y las trazas que un reproceso
    ya sustituyó (`reprocesados`).
    `via` es `null` mientras el término se debate o si el requisito falló.
    """
    trazas = list(trazas)
    excluidas = reprocesados(trazas)
    salida = []
    for t in sorted(trazas, key=lambda t: _orden_req(t.req_id)):
        if t.req_id not in excluidas:
            salida.extend(_similitudes_de(t))
    return salida


# ---------------------------------------------------------------- sensibilidad y distribución

def sensibilidad(valores: list[dict], umbrales: Iterable[float]) -> list[dict]:
    """Por umbral, cuántos términos se habrían aceptado directo y cuántos debatido,
    y cuáles cambian respecto de la decisión que se tomó de verdad::

        [{umbral, directos, debates,
          cambian: [{req_id, termino, similitud, decision_real, decision_con_umbral}]}]
    """
    filas = []
    for u in umbrales:
        directos, cambian = 0, []
        for v in valores:
            decision = decidir(v["similitud"], u).value
            directos += decision == Estado.ACEPTADO_DIRECTO.value
            if decision != v["decision_real"]:
                cambian.append({"req_id": v["req_id"], "termino": v["termino"], "similitud": v["similitud"],
                                "decision_real": v["decision_real"], "decision_con_umbral": decision})
        filas.append({"umbral": u, "directos": directos, "debates": len(valores) - directos, "cambian": cambian})
    return filas


def distribucion(valores: list[dict], ancho_bin: float, origen: float = 0.0) -> dict:
    """Histograma y estadísticos de las similitudes::

        {ancho_bin, origen, n, min, max, media, mediana, bins: [{desde, hasta, n}]}

    Los bordes son `origen + k * ancho_bin` (con `origen` = inicio de la rejilla
    coinciden con sus umbrales) y cada bin es [desde, hasta): un valor igual a un
    borde cae a la derecha, como en la regla `>=`. Así, para un umbral que sea
    borde, los bins a su izquierda suman exactamente los debates. Van todos los
    bins entre el mínimo y el máximo, también los vacíos.
    """
    if ancho_bin < 10 ** -DECIMALES:  # con menos, el redondeo juntaría bordes
        raise ValueError(f"el ancho del bin debe ser al menos {10 ** -DECIMALES}")
    sims = sorted(v["similitud"] for v in valores)
    base = {"ancho_bin": ancho_bin, "origen": origen, "n": len(sims)}
    if not sims:
        return {**base, "min": None, "max": None, "media": None, "mediana": None, "bins": []}

    def borde(k: int) -> float:
        return redondear(origen + k * ancho_bin)

    def bin_de(x: float) -> int:
        k = math.floor((x - origen) / ancho_bin)
        while borde(k) > x:
            k -= 1
        while borde(k + 1) <= x:
            k += 1
        return k

    primero, ultimo = bin_de(sims[0]), bin_de(sims[-1])
    bordes = [borde(k) for k in range(primero, ultimo + 2)]
    conteo = [0] * (len(bordes) - 1)
    for x in sims:
        conteo[bisect_right(bordes, x) - 1] += 1
    return {**base, "min": sims[0], "max": sims[-1], "media": statistics.fmean(sims),
            "mediana": statistics.median(sims),
            "bins": [{"desde": bordes[i], "hasta": bordes[i + 1], "n": n} for i, n in enumerate(conteo)]}
