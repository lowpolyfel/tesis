"""Grafo de LangGraph: la máquina de estados del requisito (ADR 0005).

Cada nodo lleva el nombre de un estado y hace el trabajo que lleva a ese estado;
al terminar, registra la transición. Las aristas condicionales son las
decisiones del umbral y de las rondas. El único nodo que no es un estado es
`humano`: ahí el grafo se pausa con `interrupt` hasta que llega la validación.

    cargado → extraido → interpretado → aceptado_directo ─────────────┐
                                      └→ en_debate ⟲ → consenso ──────┤
                                                   └→ arbitrado ──────┤
                                                 pendiente_validacion ┘
                                                          ↓ humano (interrupt)
                                          validado → formalizado | rechazado
    (cualquier nodo con fallo → error)
"""
from __future__ import annotations

import logging
from datetime import date
from functools import wraps
from typing import Any, Callable

from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.divergence import evaluar_divergencia
from app.llm import FalloEstructurado, Respuesta
from app.models import (
    PROYECTO_GENERAL,
    DecisionFiltro,
    EntradaLEL,
    EntradaLELFormalizada,
    Estado,
    Interpretacion,
    Nodo,
    Objecion,
    RondaDebate,
    TerminoCandidato,
    TerminoFiltrado,
    TipoMensaje,
    Validacion,
    Via,
)
from app.nlp import normalizar

from .dependencias import Dependencias
from .estado import EstadoGrafo, TerminoEnProceso, con_interpretaciones, interpretacion_por_id

log = logging.getLogger(__name__)

PASA_AL_CLASIFICADOR = {DecisionFiltro.REGIONAL, DecisionFiltro.CANDIDATO}
_EMISOR_POR_PROMPT = {"extractor": Nodo.EXTRACTOR, "clasificador": Nodo.CLASIFICADOR,
                      "critico": Nodo.CRITICO, "modelador": Nodo.MODELADOR}


def meta_llm(r: Respuesta) -> dict:
    """Cuántos intentos hubo y, si hubo reintento, la salida que no validó."""
    meta: dict[str, Any] = {"intentos": len(r.intentos)}
    fallidos = [{"salida_cruda": i.salida_cruda, "error": i.error} for i in r.intentos if i.error]
    if fallidos:
        meta["intentos_fallidos"] = fallidos
    return meta


def _dump(modelos) -> list[dict]:
    return [m.model_dump(mode="json") for m in modelos]


def _interps(dicts: list[dict]) -> list[Interpretacion]:
    return [Interpretacion.model_validate(d) for d in dicts]


def construir_grafo(deps: Dependencias, checkpointer):
    s = deps.settings
    repo = deps.repo

    # ------------------------------------------------------------ utilidades

    def emitir(st: EstadoGrafo, *, emisor: Nodo, receptor: Nodo, tipo: TipoMensaje, payload: dict,
               ronda: int = 0, respuesta: Respuesta | None = None, modelo: str | None = None) -> None:
        if respuesta is not None:
            payload = {**payload, **meta_llm(respuesta)}
        repo.agregar_mensaje(
            st["req_id"], ronda=ronda, emisor=emisor, receptor=receptor, tipo=tipo, payload=payload,
            modelo=respuesta.modelo if respuesta else modelo,
            prompt_version=respuesta.prompt_version if respuesta else None,
        )

    def entrar(st: EstadoGrafo, estado: Estado) -> dict:
        repo.cambiar_estado(st["req_id"], estado)
        return {"estado": estado.value}

    def nodo(fn: Callable[[EstadoGrafo], dict]) -> Callable[[EstadoGrafo], dict]:
        """Cualquier excepción de un nodo se registra como mensaje `error` y desvía a `error`."""

        @wraps(fn)
        def envuelto(st: EstadoGrafo) -> dict:
            try:
                return fn(st)
            except GraphBubbleUp:  # interrupt y control interno de LangGraph
                raise
            except Exception as e:
                log.exception("Falla en el nodo %s (%s)", fn.__name__, st.get("req_id"))
                fallo: dict[str, Any] = {"nodo": fn.__name__, "excepcion": type(e).__name__, "mensaje": str(e)}
                emisor, modelo = Nodo.SISTEMA, None
                if isinstance(e, FalloEstructurado):
                    fallo.update(e.payload())
                    emisor = _EMISOR_POR_PROMPT.get(e.prompt_version.split("_")[0], Nodo.SISTEMA)
                    modelo = e.modelo
                repo.agregar_mensaje(st["req_id"], ronda=st.get("ronda", 0), emisor=emisor, receptor=Nodo.SISTEMA,
                                     tipo=TipoMensaje.ERROR, payload=fallo, modelo=modelo,
                                     prompt_version=fallo.get("prompt_version"))
                return {"fallo": fallo}

        return envuelto

    def lel_de(st: EstadoGrafo) -> list[EntradaLEL]:
        return [EntradaLEL.model_validate(d) for d in st.get("lel", [])]

    # ------------------------------------------------------------ nodos-estado

    @nodo
    def cargado(st: EstadoGrafo) -> dict:
        # La traza ya existe en `cargado`; aquí se fija el LEL del proyecto contra el que se procesa.
        proyecto_id = st.get("proyecto_id") or PROYECTO_GENERAL
        lel = [EntradaLEL.model_validate(e.model_dump(include=set(EntradaLEL.model_fields))).model_dump(mode="json")
               for e in repo.listar_lel(proyecto_id)]
        return {"estado": Estado.CARGADO.value, "proyecto_id": proyecto_id, "ronda": 0, "lel": lel,
                "candidatos": {}, "fallo": None}

    @nodo
    def extraido(st: EstadoGrafo) -> dict:
        texto, lel = st["texto"], lel_de(st)
        r = deps.extractor.extraer(texto)
        emitir(st, emisor=Nodo.EXTRACTOR, receptor=Nodo.FILTROS, tipo=TipoMensaje.EXTRACCION,
               payload={"terminos": _dump(r.salida.terminos), "descartados": r.descartados}, respuesta=r.respuesta)

        filtrados: list[TerminoFiltrado] = deps.filtros.aplicar(texto, r.salida.terminos, lel)
        emitir(st, emisor=Nodo.FILTROS, receptor=Nodo.CLASIFICADOR, tipo=TipoMensaje.FILTRADO,
               payload={"terminos": _dump(filtrados), "catalogos": deps.filtros.catalogos.versiones(),
                        "entradas_lel": len(lel)})

        candidatos: dict[str, TerminoEnProceso] = {}
        vistos: set[str] = set()
        for f in filtrados:
            if f.decision_filtro in PASA_AL_CLASIFICADOR and normalizar(f.termino) not in vistos:
                vistos.add(normalizar(f.termino))
                candidatos[f.termino] = TerminoEnProceso(
                    termino=f.termino, categoria_tentativa=f.categoria_tentativa.value,
                    origen="regional" if f.decision_filtro == DecisionFiltro.REGIONAL else "extractor",
                    univoco=False, interpretaciones=[], todas={}, retiradas=[], historial=[],
                    similitud=None, decision=None, via=None, propuesta=None, justificacion=None,
                    final=None, cambio=None,
                )
        return {**entrar(st, Estado.EXTRAIDO), "terminos": _dump(filtrados), "candidatos": candidatos}

    @nodo
    def interpretado(st: EstadoGrafo) -> dict:
        texto, candidatos = st["texto"], {k: dict(c) for k, c in st["candidatos"].items()}
        if candidatos:
            entrada = [TerminoCandidato(termino=c["termino"], categoria_tentativa=c["categoria_tentativa"],
                                        origen=c["origen"]) for c in candidatos.values()]
            r = deps.clasificador.clasificar(texto, entrada, lel_de(st))
            emitir(st, emisor=Nodo.CLASIFICADOR, receptor=Nodo.DIVERGENCIA, tipo=TipoMensaje.INTERPRETACIONES,
                   payload={"resultados": _dump(r.valor.resultados)}, respuesta=r)
            por_termino = {normalizar(x.termino): x for x in r.valor.resultados}
            for c in candidatos.values():
                res = por_termino[normalizar(c["termino"])]
                c["univoco"] = res.univoco
                c["interpretaciones"] = _dump(res.interpretaciones)
                c["todas"] = {i["id"]: i for i in c["interpretaciones"]}
        else:
            emitir(st, emisor=Nodo.SISTEMA, receptor=Nodo.DIVERGENCIA, tipo=TipoMensaje.INTERPRETACIONES,
                   payload={"resultados": [], "nota": "sin términos candidatos: no se consultó al Clasificador"})

        ambiguos = con_interpretaciones(candidatos)
        if not ambiguos:
            emitir(st, emisor=Nodo.DIVERGENCIA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.SIMILITUD,
                   payload={"similitud": None, "umbral": s.similarity_threshold, "motivo": "sin_interpretaciones",
                            "decision": Estado.ACEPTADO_DIRECTO.value})
        for c in ambiguos.values():
            d = evaluar_divergencia(c["termino"], _interps(c["interpretaciones"]), deps.embeddings, s.similarity_threshold)
            c["similitud"] = d.similitud
            c["decision"] = d.decision.value
            if d.decision == Estado.ACEPTADO_DIRECTO:
                c["via"], c["propuesta"] = Via.ACEPTADO_DIRECTO.value, c["interpretaciones"][0]["id"]
            emitir(st, emisor=Nodo.DIVERGENCIA,
                   receptor=Nodo.CRITICO if d.decision == Estado.EN_DEBATE else Nodo.SISTEMA,
                   tipo=TipoMensaje.SIMILITUD, payload=d.payload(), modelo=d.modelo_embeddings)
        return {**entrar(st, Estado.INTERPRETADO), "candidatos": candidatos}

    @nodo
    def aceptado_directo(st: EstadoGrafo) -> dict:
        return entrar(st, Estado.ACEPTADO_DIRECTO)

    @nodo
    def en_debate(st: EstadoGrafo) -> dict:
        texto, lel = st["texto"], lel_de(st)
        ronda = st.get("ronda", 0) + 1
        repo.cambiar_estado(st["req_id"], Estado.EN_DEBATE)
        candidatos = {k: dict(c) for k, c in st["candidatos"].items()}
        for c in candidatos.values():
            if c.get("decision") != Estado.EN_DEBATE.value:
                continue
            termino, interps = c["termino"], _interps(c["interpretaciones"])

            # 1. El Crítico evalúa contra R1–R3 y objeta. No propone interpretaciones.
            ev = deps.critico.evaluar(texto, termino, interps, lel)
            objeciones: list[Objecion] = ev.valor.objeciones
            emitir(st, ronda=ronda, emisor=Nodo.CRITICO, receptor=Nodo.CLASIFICADOR, tipo=TipoMensaje.OBJECION,
                   payload={"termino": termino, "evaluaciones": _dump(ev.valor.evaluaciones),
                            "objeciones": _dump(objeciones)}, respuesta=ev)

            # 2. El Clasificador refina o retira ante las objeciones.
            if objeciones:
                rf = deps.clasificador.refinar(texto, termino, interps, objeciones)
                vigentes, retiradas = rf.valor.interpretaciones, rf.valor.retiradas
                emitir(st, ronda=ronda, emisor=Nodo.CLASIFICADOR, receptor=Nodo.DIVERGENCIA,
                       tipo=TipoMensaje.REFINAMIENTO, respuesta=rf,
                       payload={"termino": termino, "interpretaciones": _dump(vigentes), "retiradas": _dump(retiradas)})
            else:
                vigentes, retiradas = interps, []
                emitir(st, ronda=ronda, emisor=Nodo.SISTEMA, receptor=Nodo.DIVERGENCIA, tipo=TipoMensaje.REFINAMIENTO,
                       payload={"termino": termino, "interpretaciones": _dump(vigentes), "retiradas": [],
                                "nota": "sin objeciones del Crítico: no se consultó al Clasificador"})
            c["interpretaciones"] = _dump(vigentes)
            c["todas"] = {**c["todas"], **{i["id"]: i for i in c["interpretaciones"]}}
            c["retiradas"] = c["retiradas"] + [{**r.model_dump(mode="json"), "ronda": ronda} for r in retiradas]

            # 3. Se recalcula la similitud; 4. consenso si llega al umbral o queda una.
            motivo = None
            if len(vigentes) == 1:
                c["similitud"], motivo = None, "una_interpretacion"
            else:
                d = evaluar_divergencia(termino, vigentes, deps.embeddings, s.similarity_threshold)
                c["similitud"] = d.similitud
                if d.decision == Estado.ACEPTADO_DIRECTO:
                    motivo = "umbral"
                emitir(st, ronda=ronda, emisor=Nodo.DIVERGENCIA,
                       receptor=Nodo.SISTEMA if motivo else Nodo.CRITICO, tipo=TipoMensaje.SIMILITUD,
                       payload={**d.payload(), "decision": (Estado.CONSENSO if motivo else Estado.EN_DEBATE).value},
                       modelo=d.modelo_embeddings)
            c["historial"] = c["historial"] + [RondaDebate(
                ronda=ronda, interpretaciones=vigentes, objeciones=objeciones, retiradas=retiradas,
                similitud=c["similitud"]).model_dump(mode="json")]
            if motivo:
                c["decision"], c["via"], c["propuesta"] = Estado.CONSENSO.value, Via.CONSENSO.value, vigentes[0].id
                emitir(st, ronda=ronda, emisor=Nodo.SISTEMA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.CONSENSO,
                       payload={"termino": termino, "motivo": motivo, "similitud": c["similitud"],
                                "umbral": s.similarity_threshold, "propuesta": vigentes[0].id,
                                "interpretaciones": c["interpretaciones"]})
        return {"estado": Estado.EN_DEBATE.value, "ronda": ronda, "candidatos": candidatos}

    @nodo
    def consenso(st: EstadoGrafo) -> dict:
        return entrar(st, Estado.CONSENSO)

    @nodo
    def arbitrado(st: EstadoGrafo) -> dict:
        texto, lel, ronda = st["texto"], lel_de(st), st.get("ronda", 0)
        candidatos = {k: dict(c) for k, c in st["candidatos"].items()}
        for c in candidatos.values():
            if c.get("decision") != Estado.EN_DEBATE.value:
                continue
            historial = [RondaDebate.model_validate(h) for h in c["historial"]]
            a = deps.critico.arbitrar(texto, c["termino"], _interps(c["interpretaciones"]), lel, historial)
            c["decision"], c["via"] = Estado.ARBITRADO.value, Via.ARBITRAJE.value
            c["propuesta"] = a.valor.interpretacion_elegida
            c["justificacion"] = _dump(a.valor.justificacion_por_regla)
            emitir(st, ronda=ronda, emisor=Nodo.CRITICO, receptor=Nodo.SISTEMA, tipo=TipoMensaje.ARBITRAJE,
                   payload={"termino": c["termino"], **a.valor.model_dump(mode="json"),
                            "interpretaciones": c["interpretaciones"]}, respuesta=a)
        return {**entrar(st, Estado.ARBITRADO), "candidatos": candidatos}

    @nodo
    def pendiente_validacion(st: EstadoGrafo) -> dict:
        emitir(st, emisor=Nodo.SISTEMA, receptor=Nodo.HUMANO, tipo=TipoMensaje.SOLICITUD_VALIDACION,
               payload=solicitud(st))
        return entrar(st, Estado.PENDIENTE_VALIDACION)

    @nodo
    def humano(st: EstadoGrafo) -> dict:
        # Se pausa aquí. Al reanudar, LangGraph vuelve a ejecutar el nodo desde el
        # inicio y `interrupt` devuelve la validación; por eso no hay efectos antes.
        v: Validacion = interrupt({"req_id": st["req_id"], "solicitud": solicitud(st)}, response_schema=Validacion)
        candidatos = {k: dict(c) for k, c in st["candidatos"].items()}
        detalle = []
        for termino, c in con_interpretaciones(candidatos).items():
            propuesta = interpretacion_por_id(c, c["propuesta"])
            editada = v.interpretaciones_editadas.get(termino)
            if editada is None:
                final, cambio = propuesta, "ninguno"
            else:
                final = editada.model_dump(mode="json")
                existente = c["todas"].get(final["id"])
                if existente == final:
                    cambio = "ninguno" if final["id"] == c["propuesta"] else "eleccion"
                else:
                    cambio = "edicion"
            c["final"], c["cambio"] = final, cambio
            detalle.append({"termino": termino, "propuesta": c["propuesta"], "final": final, "cambio": cambio})
        emitir(st, emisor=Nodo.HUMANO, receptor=Nodo.MODELADOR if v.decision == "aprobar" else Nodo.SISTEMA,
               tipo=TipoMensaje.VALIDACION,
               payload={"decision": v.decision, "comentario": v.comentario, "terminos": detalle})
        return {"validacion": v.model_dump(mode="json"), "candidatos": candidatos}

    @nodo
    def validado(st: EstadoGrafo) -> dict:
        return entrar(st, Estado.VALIDADO)

    @nodo
    def rechazado(st: EstadoGrafo) -> dict:
        return entrar(st, Estado.RECHAZADO)

    @nodo
    def formalizado(st: EstadoGrafo) -> dict:
        # Solo los términos resueltos entran al LEL; los unívocos no (ADR 0007).
        texto, req_id = st["texto"], st["req_id"]
        resueltos = con_interpretaciones(st["candidatos"])
        univocos = [c["termino"] for c in st["candidatos"].values() if c.get("univoco")]
        hechas = []
        for termino, c in resueltos.items():
            interp = Interpretacion.model_validate(c["final"])
            m = deps.modelador.modelar(texto, termino, interp)
            entrada = EntradaLELFormalizada(
                **m.valor.entrada_lel.model_dump(), proyecto_id=st.get("proyecto_id") or PROYECTO_GENERAL,
                req_id=req_id, termino=termino, via=c["via"],
                interpretacion=interp, editada_por_humano=c.get("cambio") == "edicion", fecha=date.today().isoformat())
            hechas.append((entrada, m))
        repo.guardar_lel([e for e, _ in hechas])  # todas o ninguna: se guarda después de modelar todas
        for entrada, m in hechas:
            emitir(st, emisor=Nodo.MODELADOR, receptor=Nodo.SISTEMA, tipo=TipoMensaje.FORMALIZACION, respuesta=m,
                   payload={"termino": entrada.termino, "entrada_lel": entrada.model_dump(mode="json"),
                            "metas": m.valor.metas, "big_picture": m.valor.big_picture})
        if not hechas:
            emitir(st, emisor=Nodo.SISTEMA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.FORMALIZACION,
                   payload={"entradas": [], "univocos": univocos,
                            "nota": "sin términos resueltos: el requisito se formaliza sin entradas nuevas en el LEL"})
        return entrar(st, Estado.FORMALIZADO)

    def error(st: EstadoGrafo) -> dict:
        return entrar(st, Estado.ERROR)

    # ------------------------------------------------------------ resumen para el humano

    def solicitud(st: EstadoGrafo) -> dict:
        candidatos = st["candidatos"]
        por_decision = lambda d: [t["termino"] for t in st.get("terminos", []) if t["decision_filtro"] == d]  # noqa: E731
        return {
            "estado_previo": st.get("estado"),
            "terminos": [
                {"termino": k, "decision": c["decision"], "via": c["via"], "similitud": c["similitud"],
                 "umbral": s.similarity_threshold, "propuesta": interpretacion_por_id(c, c["propuesta"]),
                 "interpretaciones": c["interpretaciones"], "retiradas": c["retiradas"],
                 "todas": c["todas"], "justificacion": c.get("justificacion"), "rondas": len(c["historial"])}
                for k, c in con_interpretaciones(candidatos).items()
            ],
            "univocos": [c["termino"] for c in candidatos.values() if c.get("univoco")],
            "vaguedad": por_decision(DecisionFiltro.VAGUEDAD.value),
            "resueltos_por_lel": por_decision(DecisionFiltro.RESUELTO_POR_LEL.value),
            "regionales": por_decision(DecisionFiltro.REGIONAL.value),
        }

    # ------------------------------------------------------------ aristas

    def o_error(siguiente: str):
        def ruta(st: EstadoGrafo) -> str:
            return "error" if st.get("fallo") else siguiente
        return ruta

    def tras_interpretado(st: EstadoGrafo) -> str:
        if st.get("fallo"):
            return "error"
        hay_debate = any(c.get("decision") == Estado.EN_DEBATE.value for c in st["candidatos"].values())
        return "en_debate" if hay_debate else "aceptado_directo"

    def tras_ronda(st: EstadoGrafo) -> str:
        if st.get("fallo"):
            return "error"
        if not any(c.get("decision") == Estado.EN_DEBATE.value for c in st["candidatos"].values()):
            return "consenso"
        return "en_debate" if st["ronda"] < s.max_debate_rounds else "arbitrado"

    def tras_humano(st: EstadoGrafo) -> str:
        if st.get("fallo"):
            return "error"
        return "validado" if st["validacion"]["decision"] == "aprobar" else "rechazado"

    g = StateGraph(EstadoGrafo)
    for fn in (cargado, extraido, interpretado, aceptado_directo, en_debate, consenso, arbitrado,
               pendiente_validacion, humano, validado, rechazado, formalizado, error):
        g.add_node(fn.__name__, fn)

    g.add_edge(START, "cargado")
    g.add_conditional_edges("cargado", o_error("extraido"), ["extraido", "error"])
    g.add_conditional_edges("extraido", o_error("interpretado"), ["interpretado", "error"])
    g.add_conditional_edges("interpretado", tras_interpretado, ["aceptado_directo", "en_debate", "error"])
    g.add_conditional_edges("en_debate", tras_ronda, ["consenso", "en_debate", "arbitrado", "error"])
    for origen in ("aceptado_directo", "consenso", "arbitrado"):
        g.add_conditional_edges(origen, o_error("pendiente_validacion"), ["pendiente_validacion", "error"])
    g.add_conditional_edges("pendiente_validacion", o_error("humano"), ["humano", "error"])
    g.add_conditional_edges("humano", tras_humano, ["validado", "rechazado", "error"])
    g.add_conditional_edges("validado", o_error("formalizado"), ["formalizado", "error"])
    g.add_conditional_edges("formalizado", o_error(END), [END, "error"])
    g.add_edge("rechazado", END)
    g.add_edge("error", END)
    return g.compile(checkpointer=checkpointer)
