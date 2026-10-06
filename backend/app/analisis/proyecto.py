"""Vistas de un proyecto completo: resumen, ambigüedades por término y flujo
KMoS-SSA por ciclo (ADR 0015). Funciones puras sobre las trazas y el LEL del
proyecto; no llaman a ningún modelo.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from app.models import (
    DecisionFiltro,
    EntradaLELFormalizada,
    Estado,
    Nodo,
    Proyecto,
    TipoAmbiguedad,
    TipoMensaje,
    Traza,
    Via,
)

from .requisito import ESTRUCTURAS, Analisis, analizar, resumen_de
from .traza import clave, utc

# Fases del marco (CONTEXTO §5): tipos de mensaje que produce cada una y estados
# que marcan que un requisito entró a ella.
FASES = (
    (1, "Enriquecimiento de conocimiento", (Nodo.EXTRACTOR, Nodo.FILTROS),
     {TipoMensaje.EXTRACCION, TipoMensaje.FILTRADO}, {Estado.EXTRAIDO}),
    (2, "Generación de modelo", (Nodo.CLASIFICADOR,),
     {TipoMensaje.INTERPRETACIONES}, {Estado.INTERPRETADO}),
    (3, "Discusión de modelo", (Nodo.DIVERGENCIA, Nodo.CRITICO, Nodo.CLASIFICADOR),
     {TipoMensaje.SIMILITUD, TipoMensaje.OBJECION, TipoMensaje.REFINAMIENTO, TipoMensaje.CONSENSO,
      TipoMensaje.ARBITRAJE},
     {Estado.ACEPTADO_DIRECTO, Estado.EN_DEBATE, Estado.CONSENSO, Estado.ARBITRADO}),
    (4, "Validación de modelo", (Nodo.HUMANO,),
     {TipoMensaje.SOLICITUD_VALIDACION, TipoMensaje.VALIDACION}, {Estado.PENDIENTE_VALIDACION}),
    (5, "Enriquecimiento (cierre)", (Nodo.MODELADOR,),
     {TipoMensaje.FORMALIZACION}, {Estado.FORMALIZADO}),
)
PREFIJO_SIMBOLO_LEL = "símbolo del LEL: "  # detalle que escriben los filtros (app/nlp/filtros.py)


def _por_estado(analisis: Iterable[Analisis]) -> dict[str, int]:
    conteo = Counter(a.traza.estado.value for a in analisis)
    return {e.value: conteo.get(e.value, 0) for e in Estado}


def _numero(req_id: str) -> int:
    return int(req_id[1:]) if req_id[1:].isdigit() else 0


def _ordenadas(trazas: list[Traza]) -> list[Analisis]:
    return [analizar(t) for t in sorted(trazas, key=lambda t: (_numero(t.req_id), t.req_id))]


# ---------------------------------------------------------------- resumen

def resumen_proyecto(proyecto: Proyecto, trazas: list[Traza], lel: list[EntradaLELFormalizada]) -> dict:
    """{proyecto, contadores{requisitos, ciclos, en_proceso, por_validar, formalizados,
    rechazados, errores, ambiguos, lel}, por_estado{estado: n}, por_ciclo[{ciclo,
    requisitos, por_estado}], requisitos[resumen_requisito]}. Forma: `formas.ResumenProyecto`."""
    todos = _ordenadas(trazas)
    por_estado = _por_estado(todos)
    ciclos = sorted({a.traza.ciclo for a in todos})
    return {
        "proyecto": proyecto.model_dump(mode="json"),
        "contadores": {
            "requisitos": len(todos), "ciclos": len(ciclos),
            "en_proceso": sum(a.en_proceso for a in todos),
            "por_validar": por_estado[Estado.PENDIENTE_VALIDACION.value],
            "formalizados": por_estado[Estado.FORMALIZADO.value],
            "rechazados": por_estado[Estado.RECHAZADO.value],
            "errores": por_estado[Estado.ERROR.value],
            "ambiguos": sum(len(a.ambiguos) for a in todos),
            "lel": len(lel),
        },
        "por_estado": por_estado,
        "por_ciclo": [{"ciclo": c, "requisitos": sum(a.traza.ciclo == c for a in todos),
                       "por_estado": _por_estado(a for a in todos if a.traza.ciclo == c)} for c in ciclos],
        "requisitos": [resumen_de(a) for a in todos],
    }


# ---------------------------------------------------------------- ambigüedades

def _significado(i: dict | None) -> str | None:
    return i.get("significado") if i else None


def _aparicion(a: Analisis, **campos) -> dict:
    return {"req_id": a.traza.req_id, "ciclo": a.traza.ciclo, "estado": a.traza.estado.value, **campos}


def _simbolo_del_detalle(f: dict) -> str:
    detalle = f.get("detalle") or ""
    return detalle[len(PREFIJO_SIMBOLO_LEL):] if detalle.startswith(PREFIJO_SIMBOLO_LEL) else f["termino"]


def _agrupar(a: Analisis, decision: DecisionFiltro, destino: dict[str, dict]) -> None:
    for termino in a.decisiones(decision):
        g = destino.setdefault(clave(termino), {"termino": termino, "req_ids": []})
        if a.traza.req_id not in g["req_ids"]:
            g["req_ids"].append(a.traza.req_id)


def _inconsistencia(g: dict, relacionadas: list[EntradaLELFormalizada]) -> dict | None:
    """Significados validados distintos entre requisitos, o entradas del LEL del mismo
    símbolo con nociones distintas. La comparación es literal (minúsculas, sin acentos)."""
    significados: dict[str, dict] = {}
    for ap in g["apariciones"]:
        if ap["interpretacion_final"]:
            s = significados.setdefault(clave(ap["interpretacion_final"]),
                                        {"significado": ap["interpretacion_final"], "req_ids": []})
            s["req_ids"].append(ap["req_id"])
    partes, conflictos = [], []
    if len(significados) > 1:
        detalle = "; ".join(f"{', '.join(s['req_ids'])}: {s['significado']}" for s in significados.values())
        partes.append(f"«{g['termino']}» quedó validado con {len(significados)} significados distintos ({detalle})")
    por_simbolo: dict[str, list[EntradaLELFormalizada]] = {}
    for e in relacionadas:
        por_simbolo.setdefault(clave(e.simbolo), []).append(e)
    for entradas in por_simbolo.values():
        nociones = {tuple(clave(n) for n in e.nocion) for e in entradas}
        if len(nociones) > 1:
            partes.append(f"el LEL tiene {len(entradas)} entradas «{entradas[0].simbolo}» "
                          f"con {len(nociones)} nociones distintas")
            conflictos += [{"simbolo": e.simbolo, "nocion": e.nocion, "req_id": e.req_id} for e in entradas]
    if not partes:
        return None
    return {"texto": "; ".join(partes),
            "significados": list(significados.values()) if len(significados) > 1 else [], "lel": conflictos}


def ambiguedades_proyecto(trazas: list[Traza], lel: list[EntradaLELFormalizada]) -> dict:
    """Ambigüedades del proyecto agrupadas por término normalizado. Forma: `formas.AmbiguedadesProyecto`::

        {terminos: [{clave, termino, tipos, origenes,
                     apariciones: [{req_id, ciclo, estado, tipo_ambiguedad, decision_filtro, via,
                                    similitud_inicial, rondas, interpretacion_final, propuesta}],
                     inconsistente, detalle_inconsistencia: {texto, significados, lel} | null}],
         vaguedad: [{termino, req_ids}], regionales: [{termino, req_ids}],
         estructuras: [{termino, decision_filtro, detalle, req_id}],
         totales: {por_tipo, por_via, inconsistentes}}

    Una aparición es un término con interpretaciones en un requisito, o uno que los
    filtros dieron por `resuelto_por_lel` (la memoria funcionando). `interpretacion_final`
    es el significado que aprobó el humano; `propuesta`, el que se le propuso.
    """
    grupos: dict[str, dict] = {}
    vaguedad: dict[str, dict] = {}
    regionales: dict[str, dict] = {}
    estructuras = []

    def grupo(k: str, termino: str) -> dict:
        return grupos.setdefault(k, {"clave": k, "termino": termino, "origenes": set(), "apariciones": []})

    for a in _ordenadas(trazas):
        decision_por_clave: dict[str, str] = {}
        for f in a.filtrado:
            decision_por_clave.setdefault(clave(f["termino"]), f.get("decision_filtro"))
        aprobado = (a.validacion or {}).get("decision") == "aprobar"
        for t in a.ambiguos:
            forma = t.forma()
            res, val = forma["resolucion"] or {}, forma["validacion"] or {}
            g = grupo(clave(t.termino), t.termino)
            if t.origen:
                g["origenes"].add(t.origen)
            g["apariciones"].append(_aparicion(
                a, tipo_ambiguedad=t.tipo_ambiguedad, decision_filtro=decision_por_clave.get(clave(t.termino)),
                via=res.get("via"), similitud_inicial=(t.divergencia_inicial or {}).get("similitud"),
                rondas=len(forma["rondas"]), interpretacion_final=_significado(val.get("final")) if aprobado else None,
                propuesta=_significado(res.get("propuesta"))))
        for f in a.filtrado:
            if f.get("decision_filtro") == DecisionFiltro.RESUELTO_POR_LEL:
                simbolo = _simbolo_del_detalle(f)
                g = grupo(clave(simbolo), simbolo)
                if all(ap["req_id"] != a.traza.req_id for ap in g["apariciones"]):
                    g["apariciones"].append(_aparicion(
                        a, tipo_ambiguedad=None, decision_filtro=DecisionFiltro.RESUELTO_POR_LEL.value, via=None,
                        similitud_inicial=None, rondas=0, interpretacion_final=None, propuesta=None))
            elif f.get("decision_filtro") in ESTRUCTURAS:
                estructuras.append({"termino": f["termino"], "decision_filtro": f["decision_filtro"],
                                    "detalle": f.get("detalle"), "req_id": a.traza.req_id})
        _agrupar(a, DecisionFiltro.VAGUEDAD, vaguedad)
        _agrupar(a, DecisionFiltro.REGIONAL, regionales)

    # una entrada del LEL cuyo requisito ya no está también cuenta para las inconsistencias
    for e in lel:
        if clave(e.termino) not in grupos:
            grupo(clave(e.simbolo), e.simbolo)

    salida = []
    for k, g in grupos.items():
        detalle = _inconsistencia(g, [e for e in lel if k in (clave(e.simbolo), clave(e.termino))])
        if not g["apariciones"] and detalle is None:
            continue
        salida.append({
            "clave": k, "termino": g["termino"],
            "tipos": sorted({ap["tipo_ambiguedad"] for ap in g["apariciones"] if ap["tipo_ambiguedad"]}),
            "origenes": sorted(g["origenes"]), "apariciones": g["apariciones"],
            "inconsistente": detalle is not None, "detalle_inconsistencia": detalle,
        })
    salida.sort(key=lambda g: (not g["inconsistente"], -len(g["apariciones"]), g["clave"]))

    ambiguas = [ap for g in salida for ap in g["apariciones"] if ap["tipo_ambiguedad"]]
    por_via = Counter(ap["via"] or "sin_resolver" for ap in ambiguas)
    return {
        "terminos": salida,
        "vaguedad": list(vaguedad.values()),
        "regionales": list(regionales.values()),
        "estructuras": estructuras,
        "totales": {
            "por_tipo": {t.value: sum(ap["tipo_ambiguedad"] == t.value for ap in ambiguas) for t in TipoAmbiguedad},
            "por_via": {v: por_via.get(v, 0) for v in [*(x.value for x in Via), "sin_resolver"]},
            "inconsistentes": sum(g["inconsistente"] for g in salida),
        },
    }


# ---------------------------------------------------------------- flujo KMoS-SSA

def _flujo(ciclo: int | None, analisis: list[Analisis], lel: list[EntradaLELFormalizada]) -> dict:
    mensajes = [m for a in analisis for m in a.efectivos]
    por_agente = Counter(m.emisor.value for m in mensajes)
    por_tipo = Counter(m.tipo.value for m in mensajes)

    def pasaron(estados: set[Estado]) -> int:
        return sum(1 for a in analisis if a.estados & {e.value for e in estados})

    req_ids = {a.traza.req_id for a in analisis}
    inicios = [utc(a.traza.transiciones[0].timestamp if a.traza.transiciones else a.traza.creado) for a in analisis]
    finales = [utc(t) for a in analisis
               for t in [*(m.timestamp for m in a.traza.mensajes), *(x.timestamp for x in a.traza.transiciones)]]
    return {
        "ciclo": ciclo,
        "requisitos": len(analisis),
        "por_estado": _por_estado(analisis),
        "mensajes_por_agente": {n.value: por_agente.get(n.value, 0) for n in Nodo},
        "mensajes_por_tipo": {t.value: por_tipo.get(t.value, 0) for t in TipoMensaje},
        "fases": [{"fase": n, "nombre": nombre, "agentes": [x.value for x in agentes],
                   "mensajes": sum(por_tipo.get(t.value, 0) for t in tipos), "requisitos_que_pasaron": pasaron(estados)}
                  for n, nombre, agentes, tipos, estados in FASES],
        "debates": pasaron({Estado.EN_DEBATE}),
        "rondas_totales": sum(a.rondas for a in analisis),
        "consensos": pasaron({Estado.CONSENSO}),
        "arbitrajes": pasaron({Estado.ARBITRADO}),
        "directos": pasaron({Estado.ACEPTADO_DIRECTO}),
        "validados": pasaron({Estado.VALIDADO}),
        "rechazados": pasaron({Estado.RECHAZADO}),
        "formalizados": pasaron({Estado.FORMALIZADO}),
        "lel_nuevas": sum(1 for e in lel if e.req_id in req_ids),
        "duracion_s": round((max(finales) - min(inicios)).total_seconds(), 3) if inicios and finales else None,
    }


def flujo_proyecto(trazas: list[Traza], lel: list[EntradaLELFormalizada]) -> dict:
    """Métricas del ciclo KMoS-SSA (CONTEXTO §5) por ciclo y del proyecto completo.
    Forma: `formas.FlujoProyecto`::

        {ciclos: [{ciclo, requisitos, por_estado, mensajes_por_agente, mensajes_por_tipo,
                   fases: [{fase, nombre, agentes, mensajes, requisitos_que_pasaron}],
                   debates, rondas_totales, consensos, arbitrajes, directos, validados,
                   rechazados, formalizados, lel_nuevas, duracion_s}],
         total: {... lo mismo, con ciclo: null}}

    Los mensajes se cuentan sin repetidos; los conteos de camino (`debates`,
    `consensos`…) son requisitos que pasaron por ese estado; `duracion_s` va del
    primer `cargado` al último evento del ciclo e incluye la espera del humano.
    """
    todos = _ordenadas(trazas)
    ciclos = sorted({a.traza.ciclo for a in todos})
    return {"ciclos": [_flujo(c, [a for a in todos if a.traza.ciclo == c], lel) for c in ciclos],
            "total": _flujo(None, todos, lel)}
