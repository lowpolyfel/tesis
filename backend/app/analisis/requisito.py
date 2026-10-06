"""Vista por término de un requisito, derivada de su traza (ADR 0015).

El backend trabaja por término con N interpretaciones (I1..In); el frontend no
debe reconstruir eso a mano. `analizar` recorre los mensajes efectivos de la
traza una vez y arma, por término, sus interpretaciones con su estado, la
divergencia inicial, cada ronda de debate, la resolución, la validación y la
entrada del LEL. Funciones puras: no llaman a ningún modelo ni al repositorio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import (
    ESTADOS_TERMINALES,
    DecisionFiltro,
    Estado,
    Mensaje,
    TipoAmbiguedad,
    TipoMensaje,
    Traza,
    Via,
)
from app.orchestration.grafo import ORIGEN_POR_DECISION

from .traza import (
    alcance_formalizacion,
    clave,
    duracion_ms,
    mensajes_efectivos,
    normalizar_config,
    ultimo,
)

# De la resolución más fuerte a la más débil: con un término arbitrado el requisito quedó arbitrado
ORDEN_VIA = (Via.ARBITRAJE, Via.CONSENSO, Via.ACEPTADO_DIRECTO)
_DEBATE = (TipoMensaje.OBJECION, TipoMensaje.REFINAMIENTO, TipoMensaje.SIMILITUD, TipoMensaje.CONSENSO)
ESTRUCTURAS = (DecisionFiltro.ALCANCE, DecisionFiltro.ANAFORA)


def _plana(i: dict) -> dict:
    return {"id": i.get("id"), "significado": i.get("significado"),
            "parafrasis_del_requisito": i.get("parafrasis_del_requisito")}


def _similitud(p: dict) -> dict:
    par = p.get("par_minimo")
    return {"similitud": p.get("similitud"), "umbral": p.get("umbral"), "decision": p.get("decision"),
            "pares": p.get("pares") or {}, "par_minimo": list(par) if par else None}


def via_mas_fuerte(vias) -> str | None:
    presentes = {v for v in vias if v}
    return next((v.value for v in ORDEN_VIA if v.value in presentes), None)


@dataclass
class TerminoAnalizado:
    """Un término que pasó al Clasificador, mientras se recorre la traza."""

    termino: str
    origen: str | None = None
    detalle: str | None = None
    categoria: str | None = None
    univoco: bool | None = None
    tipo_ambiguedad: str | None = None
    iniciales: list[dict] = field(default_factory=list)
    divergencia_inicial: dict | None = None
    debate: dict[int, dict[str, dict]] = field(default_factory=dict)  # ronda → tipo → payload
    arbitraje: dict | None = None
    solicitud: dict | None = None
    validacion: dict | None = None
    entrada_lel: dict | None = None

    @property
    def ambiguo(self) -> bool:
        return self.univoco is False and bool(self.iniciales)

    def forma(self) -> dict:
        interpretaciones, rondas, todas = self._recorrer_rondas()
        resolucion = self._resolucion(todas, rondas)
        return {
            "termino": self.termino, "origen": self.origen, "detalle": self.detalle, "categoria": self.categoria,
            "univoco": self.univoco, "tipo_ambiguedad": self.tipo_ambiguedad,
            "interpretaciones": interpretaciones, "divergencia_inicial": self.divergencia_inicial,
            "rondas": rondas, "resolucion": resolucion,
            "validacion": {"final": _plana(self.validacion["final"]) if self.validacion.get("final") else None,
                           "cambio": self.validacion.get("cambio")} if self.validacion else None,
            "entrada_lel": self.entrada_lel,
        }

    def _recorrer_rondas(self) -> tuple[list[dict], list[dict], dict[str, dict]]:
        """Cada ronda: lo evaluado, objeciones, refinamiento, similitud y consenso.
        Una interpretación refinada conserva su id y queda en su última versión."""
        todas = {i["id"]: _plana(i) for i in self.iniciales if i.get("id")}
        estado = {id_: ("vigente", None, None) for id_ in todas}
        evaluadas = list(todas.values())
        rondas = []
        for n in sorted(self.debate):
            msgs = self.debate[n]
            obj = msgs.get(TipoMensaje.OBJECION, {})
            ronda: dict[str, Any] = {"ronda": n, "evaluadas": evaluadas, "evaluaciones": obj.get("evaluaciones", []),
                                     "objeciones": obj.get("objeciones", []), "refinamiento": None,
                                     "similitud": None, "consenso": None}
            if (ref := msgs.get(TipoMensaje.REFINAMIENTO)) is not None:
                vigentes = [_plana(i) for i in ref.get("interpretaciones", [])]
                retiradas = ref.get("retiradas", [])
                ronda["refinamiento"] = {"interpretaciones": vigentes, "retiradas": retiradas, "nota": ref.get("nota")}
                ids_vigentes = {i["id"] for i in vigentes}
                for i in vigentes:
                    todas[i["id"]] = i
                    estado[i["id"]] = ("vigente", None, None)
                for r in retiradas:
                    estado[r.get("interpretacion_id")] = ("retirada", n, r.get("motivo"))
                for id_, (e, _, _) in list(estado.items()):  # el Clasificador debe conservarla o retirarla
                    if e == "vigente" and id_ not in ids_vigentes:
                        estado[id_] = ("retirada", n, None)
                evaluadas = vigentes
            if (sim := msgs.get(TipoMensaje.SIMILITUD)) is not None:
                ronda["similitud"] = _similitud(sim)
            if (con := msgs.get(TipoMensaje.CONSENSO)) is not None:
                ronda["consenso"] = {k: con.get(k) for k in ("motivo", "similitud", "umbral", "propuesta")}
            rondas.append(ronda)
        interpretaciones = [{**i, "estado": estado[id_][0], "retirada_en_ronda": estado[id_][1],
                             "motivo_retiro": estado[id_][2]} for id_, i in todas.items()]
        return interpretaciones, rondas, todas

    def _resolucion(self, todas: dict[str, dict], rondas: list[dict]) -> dict | None:
        """Cómo quedó el término antes de la validación humana; None mientras se debate."""
        inicial = self.divergencia_inicial or {}
        consenso = next((r["consenso"] for r in reversed(rondas) if r["consenso"]), None)
        medidas = [inicial.get("similitud")] + [r["similitud"]["similitud"] for r in rondas if r["similitud"]]
        if self.arbitraje is not None:
            elegida = self.arbitraje.get("interpretacion_elegida")
            r = {"via": Via.ARBITRAJE.value, "decision": Estado.ARBITRADO.value, "propuesta": todas.get(elegida),
                 "motivo": "rondas_agotadas", "similitud_final": medidas[-1],
                 "arbitraje": {"interpretacion_elegida": elegida,
                               "justificacion_por_regla": self.arbitraje.get("justificacion_por_regla", [])}}
        elif consenso is not None:
            r = {"via": Via.CONSENSO.value, "decision": Estado.CONSENSO.value,
                 "propuesta": todas.get(consenso["propuesta"]), "motivo": consenso["motivo"], "similitud_final": consenso["similitud"], "arbitraje": None}
        elif inicial.get("decision") == Estado.ACEPTADO_DIRECTO.value and self.iniciales:
            r = {"via": Via.ACEPTADO_DIRECTO.value, "decision": Estado.ACEPTADO_DIRECTO.value,
                 "propuesta": _plana(self.iniciales[0]), "motivo": "umbral",
                 "similitud_final": inicial.get("similitud"), "arbitraje": None}
        else:
            return None
        if self.solicitud and self.solicitud.get("propuesta"):  # lo que de verdad se le mostró al humano
            r["propuesta"] = _plana(self.solicitud["propuesta"])
        return r


@dataclass
class Analisis:
    """Lo que se deriva de una traza; lo comparten la vista, los resúmenes y el proyecto."""

    traza: Traza
    efectivos: list[Mensaje]
    repetidos: int
    filtrado: list[dict]
    terminos: list[TerminoAnalizado]
    marcados: list[dict]
    extraccion: dict | None
    solicitud: dict | None
    validacion: dict | None
    formalizacion: dict | None
    errores: list[dict]
    estados: set[str]  # estados por los que pasó

    @property
    def en_proceso(self) -> bool:
        return self.traza.estado not in ESTADOS_TERMINALES and self.traza.estado != Estado.PENDIENTE_VALIDACION

    @property
    def ambiguos(self) -> list[TerminoAnalizado]:
        return [t for t in self.terminos if t.ambiguo]

    @property
    def rondas(self) -> int:
        """Rondas de debate del requisito (todos los términos se debaten en las mismas rondas)."""
        return max((m.ronda for m in self.efectivos if m.tipo in _DEBATE), default=0)

    def decisiones(self, decision: DecisionFiltro) -> list[str]:
        vistos, salida = set(), []
        for f in self.filtrado:
            if f.get("decision_filtro") == decision and clave(f["termino"]) not in vistos:
                vistos.add(clave(f["termino"]))
                salida.append(f["termino"])
        return salida

    def resumen(self) -> dict:
        tipos = {t.value: 0 for t in TipoAmbiguedad}
        for t in self.ambiguos:
            tipos[t.tipo_ambiguedad] = tipos.get(t.tipo_ambiguedad, 0) + 1
        iniciales = [t.divergencia_inicial["similitud"] for t in self.ambiguos
                     if t.divergencia_inicial and t.divergencia_inicial.get("similitud") is not None]
        formas = [t.forma() for t in self.ambiguos]
        return {
            "n_terminos": len(self.terminos), "n_ambiguos": len(self.ambiguos), "tipos": tipos,
            "vaguedad": self.decisiones(DecisionFiltro.VAGUEDAD),
            "regionales": self.decisiones(DecisionFiltro.REGIONAL),
            "resueltos_por_lel": self.decisiones(DecisionFiltro.RESUELTO_POR_LEL),
            "estructuras": sum(1 for f in self.filtrado if f.get("decision_filtro") in ESTRUCTURAS),
            "similitud_minima": min(iniciales) if iniciales else None,
            "via": via_mas_fuerte(f["resolucion"]["via"] for f in formas if f["resolucion"]),
            "rondas_max": max((len(f["rondas"]) for f in formas), default=0),
            "n_errores": len(self.errores),
        }


def _terminos(filtrado: list[dict], resultados: list[dict] | None) -> dict[str, TerminoAnalizado]:
    """Los candidatos que pasaron al Clasificador, uno por forma normalizada, como en el grafo."""
    por_clave: dict[str, TerminoAnalizado] = {}
    for f in filtrado:
        origen = ORIGEN_POR_DECISION.get(f.get("decision_filtro"))
        k = clave(f.get("termino"))
        if origen and k and k not in por_clave:
            por_clave[k] = TerminoAnalizado(termino=f["termino"], origen=origen, detalle=f.get("detalle"),
                                    categoria=f.get("categoria_tentativa"))
    for r in resultados or []:
        k = clave(r.get("termino"))
        if not k:
            continue
        t = por_clave.setdefault(k, TerminoAnalizado(termino=r["termino"]))
        t.univoco = bool(r.get("univoco", False))
        t.iniciales = [] if t.univoco else list(r.get("interpretaciones") or [])
        # las trazas anteriores al tipo de ambigüedad se tratan como léxicas (ADR 0010)
        t.tipo_ambiguedad = r.get("tipo_ambiguedad") or (TipoAmbiguedad.LEXICA.value if t.ambiguo else None)
    return por_clave


def _tipo_marcado(f: dict, t: TerminoAnalizado | None) -> str | None:
    decision = f.get("decision_filtro")
    if decision == DecisionFiltro.RESUELTO_POR_LEL:
        return "lel"
    if decision == DecisionFiltro.VAGUEDAD:
        return "vaguedad"
    if t is not None and t.ambiguo:
        return t.tipo_ambiguedad
    return "regional" if decision == DecisionFiltro.REGIONAL else None


def _marcados(texto: str, filtrado: list[dict], por_clave: dict[str, TerminoAnalizado]) -> list[dict]:
    salida = []
    for f in filtrado:
        pos = f.get("posicion") or {}
        inicio, fin = pos.get("inicio"), pos.get("fin")
        if inicio is None or fin is None:
            continue
        t = por_clave.get(clave(f["termino"])) if f.get("decision_filtro") in ORIGEN_POR_DECISION else None
        salida.append({"inicio": inicio, "fin": fin, "texto": texto[inicio:fin] or f["termino"],
                       "termino": f["termino"], "decision_filtro": f.get("decision_filtro"),
                       "tipo": _tipo_marcado(f, t), "detalle": f.get("detalle"), "univoco": t.univoco if t else None})
    return sorted(salida, key=lambda m: (m["inicio"], m["fin"]))


def analizar(traza: Traza) -> Analisis:
    efectivos, repetidos = mensajes_efectivos(traza)
    m_extraccion = ultimo(efectivos, TipoMensaje.EXTRACCION)
    m_filtrado = ultimo(efectivos, TipoMensaje.FILTRADO)
    m_interp = ultimo(efectivos, TipoMensaje.INTERPRETACIONES)
    m_solicitud = ultimo(efectivos, TipoMensaje.SOLICITUD_VALIDACION)
    m_validacion = ultimo(efectivos, TipoMensaje.VALIDACION)

    filtrado = (m_filtrado.payload.get("terminos") or []) if m_filtrado else []
    por_clave = _terminos(filtrado, m_interp.payload.get("resultados") if m_interp else None)

    formalizacion = None
    for m in efectivos:
        p, k = m.payload or {}, clave((m.payload or {}).get("termino"))
        t = por_clave.get(k) if k else None
        if m.tipo == TipoMensaje.SIMILITUD and m.ronda == 0 and t is not None:
            t.divergencia_inicial = {**_similitud(p), "modelo_embeddings": p.get("modelo_embeddings") or m.modelo}
        elif m.tipo in _DEBATE and m.ronda > 0 and t is not None:
            t.debate.setdefault(m.ronda, {})[m.tipo] = p
        elif m.tipo == TipoMensaje.ARBITRAJE and t is not None:
            t.arbitraje = p
        elif m.tipo == TipoMensaje.FORMALIZACION:
            if alcance_formalizacion(p) == "requisito":
                formalizacion = p
            elif t is not None:
                t.entrada_lel = p.get("entrada_lel")
    for p_termino in (m_solicitud.payload.get("terminos") or []) if m_solicitud else []:
        if (t := por_clave.get(clave(p_termino.get("termino")))) is not None:
            t.solicitud = p_termino
    for v in (m_validacion.payload.get("terminos") or []) if m_validacion else []:
        if (t := por_clave.get(clave(v.get("termino")))) is not None:
            t.validacion = v

    extraccion = None
    if m_extraccion:
        p = m_extraccion.payload
        extraccion = {"terminos": p.get("terminos") or [], "descartados": p.get("descartados") or [],
                      "modelo": m_extraccion.modelo, "prompt_version": m_extraccion.prompt_version,
                      "intentos": p.get("intentos"), "duracion_ms": duracion_ms(traza, m_extraccion)}
    validacion = None
    if m_validacion:
        p = m_validacion.payload
        validacion = {"decision": p.get("decision"), "comentario": p.get("comentario"),
                      "terminos": p.get("terminos") or [],
                      "timestamp": m_validacion.model_dump(mode="json")["timestamp"]}
    errores = [{"secuencia": m.secuencia, "nodo": m.payload.get("nodo"), "excepcion": m.payload.get("excepcion"),
                "mensaje": m.payload.get("mensaje"),
                "prompt_version": m.prompt_version or m.payload.get("prompt_version")}
               for m in efectivos if m.tipo == TipoMensaje.ERROR]
    return Analisis(
        traza=traza, efectivos=efectivos, repetidos=repetidos, filtrado=filtrado, terminos=list(por_clave.values()),
        marcados=_marcados(traza.texto, filtrado, por_clave), extraccion=extraccion,
        solicitud=m_solicitud.payload if m_solicitud else None, validacion=validacion, formalizacion=formalizacion,
        errores=errores, estados={t.estado.value for t in traza.transiciones} | {traza.estado.value},
    )


_CABECERA = ("req_id", "proyecto_id", "ciclo", "texto", "origen", "estado", "creado", "actualizado")


def vista_requisito(traza: Traza, formalizado: dict | None = None) -> dict:
    """Vista completa de un requisito para el frontend, por término.

    `formalizado` es el documento de la colección `formalizados` (si ya existe);
    si falta, se usa el mensaje `formalizacion` con alcance `requisito`.
    Tolera trazas en proceso, en error, anteriores al tipo de ambigüedad y con
    mensajes repetidos tras un reinicio. Forma exacta: `formas.VistaRequisito`::

        {req_id, proyecto_id, ciclo, texto, origen, estado, creado, actualizado,
         en_proceso, terminal,
         config: {umbral, max_rondas, modelos{extractor, clasificador, critico, modelador},
                  modelo_embeddings, temperatura, semilla, significado_max_palabras,
                  spacy_model, catalogos, persistencia, otros},
         transiciones: [{estado, secuencia, timestamp}],
         marcados: [{inicio, fin, texto, termino, decision_filtro, tipo, detalle, univoco}],
         extraccion: {terminos, descartados, modelo, prompt_version, intentos, duracion_ms} | null,
         terminos: [{termino, origen, detalle, categoria, univoco, tipo_ambiguedad,
                     interpretaciones: [{id, significado, parafrasis_del_requisito,
                                         estado, retirada_en_ronda, motivo_retiro}],
                     divergencia_inicial: {similitud, umbral, decision, pares, par_minimo,
                                           modelo_embeddings} | null,
                     rondas: [{ronda, evaluadas, evaluaciones, objeciones,
                               refinamiento: {interpretaciones, retiradas, nota} | null,
                               similitud: {similitud, umbral, decision, pares, par_minimo} | null,
                               consenso: {motivo, similitud, umbral, propuesta} | null}],
                     resolucion: {via, decision, propuesta, motivo, similitud_final,
                                  arbitraje: {interpretacion_elegida, justificacion_por_regla} | null} | null,
                     validacion: {final, cambio} | null,
                     entrada_lel: {...} | null}],
         resumen: {n_terminos, n_ambiguos, tipos, vaguedad, regionales, resueltos_por_lel,
                   estructuras, similitud_minima, via, rondas_max, n_errores},
         solicitud, validacion: {decision, comentario, terminos, timestamp} | null,
         formalizacion, errores: [{secuencia, nodo, excepcion, mensaje, prompt_version}],
         n_mensajes, n_repetidos, ultima_secuencia}
    """
    a = analizar(traza)
    cabecera = traza.model_dump(mode="json", include=set(_CABECERA))
    return {
        **{k: cabecera[k] for k in _CABECERA},
        "en_proceso": a.en_proceso,
        "terminal": traza.estado in ESTADOS_TERMINALES,
        "config": normalizar_config(traza.config),
        "transiciones": [t.model_dump(mode="json") for t in traza.transiciones],
        "marcados": a.marcados,
        "extraccion": a.extraccion,
        "terminos": [t.forma() for t in a.terminos],
        "resumen": a.resumen(),
        "solicitud": a.solicitud,
        "validacion": a.validacion,
        "formalizacion": formalizado if formalizado is not None else a.formalizacion,
        "errores": a.errores,
        "n_mensajes": len(traza.mensajes),
        "n_repetidos": a.repetidos,
        "ultima_secuencia": max((m.secuencia for m in traza.mensajes), default=0),
    }


def resumen_de(a: Analisis) -> dict:
    cabecera = a.traza.model_dump(mode="json", include=set(_CABECERA))
    r = a.resumen()
    return {**{k: cabecera[k] for k in _CABECERA},
            **{k: r[k] for k in ("similitud_minima", "via", "rondas_max", "n_ambiguos", "tipos", "vaguedad")},
            "en_proceso": a.en_proceso}


def resumen_requisito(traza: Traza) -> dict:
    """Versión ligera para listas: {req_id, proyecto_id, ciclo, texto, origen, estado,
    creado, actualizado, similitud_minima, via, rondas_max, n_ambiguos, tipos, vaguedad,
    en_proceso}. Forma exacta: `formas.ResumenRequisito`."""
    return resumen_de(analizar(traza))
