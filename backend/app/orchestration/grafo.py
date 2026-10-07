"""Grafo de LangGraph: la máquina de estados del requisito (ADR 0005).

Cada nodo lleva el nombre de un estado y hace el trabajo que lleva a ese estado;
al terminar, registra la transición. Las aristas condicionales son las
decisiones del umbral y de las rondas. El único nodo que no es un estado es
`humano`: ahí el grafo se pausa con `interrupt` hasta que llega la validación.

    cargado → extraido → interpretado → aceptado_directo ─────────────┐
                                      └→ en_debate ⟲ → consenso ──────┤
                                                   └→ arbitrado ──────┤
                            ┌── ¿hace falta una persona? (ADR 0017) ──┘
                            │ sí                                  no │
                 pendiente_validacion → humano (interrupt)   validacion_automatica
                                  ↓                                  ↓
                     validado | rechazado            validado → formalizado
    (cualquier nodo con fallo → error)

`validacion_automatica` tampoco es un estado: aprueba la propuesta de los agentes
sin cambios y lo registra en la traza como una validación del sistema. Una
persona sigue pudiendo corregir el resultado formalizado (ADR 0017).
"""
from __future__ import annotations

import logging
from datetime import date
from functools import wraps
from typing import Any, Callable

from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.db.proyectos import Proyectos
from app.divergence import evaluar_divergencia
from app.llm import FalloEstructurado, Respuesta
from app.models import (
    PROYECTO_GENERAL,
    TIPOS_QUE_VAN_AL_LEL,
    DecisionFiltro,
    EntradaLEL,
    EntradaLELFormalizada,
    Estado,
    Interpretacion,
    Nodo,
    Objecion,
    TipoAmbiguedad,
    RondaDebate,
    TerminoCandidato,
    TerminoFiltrado,
    TipoMensaje,
    Validacion,
    ValidacionHumana,
    Via,
)
from app.nlp import normalizar

from .dependencias import Dependencias
from .estado import EstadoGrafo, TerminoEnProceso, con_interpretaciones, interpretacion_por_id

log = logging.getLogger(__name__)

# Qué decisiones de los filtros pasan al Clasificador y con qué origen
ORIGEN_POR_DECISION = {DecisionFiltro.CANDIDATO: "extractor", DecisionFiltro.REGIONAL: "regional",
                       DecisionFiltro.ALCANCE: "alcance", DecisionFiltro.ANAFORA: "anafora"}
COLECCION_FORMALIZADOS = "formalizados"
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


def va_al_lel(c: TerminoEnProceso) -> bool:
    """Solo la ambigüedad léxica produce una entrada del LEL; los términos de
    trazas anteriores al tipo de ambigüedad se tratan como léxicos."""
    tipo = c.get("tipo_ambiguedad")
    return tipo is None or TipoAmbiguedad(tipo) in TIPOS_QUE_VAN_AL_LEL


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
        # La traza ya existe en `cargado`; aquí se fijan el LEL y el contexto del proyecto contra
        # los que se procesa. El contexto es el que se copió en la traza al cargar el requisito.
        proyecto_id = st.get("proyecto_id") or PROYECTO_GENERAL
        lel = [EntradaLEL.model_validate(e.model_dump(include=set(EntradaLEL.model_fields))).model_dump(mode="json")
               for e in repo.listar_lel(proyecto_id)]
        proyecto = Proyectos(repo).obtener(proyecto_id)
        traza = repo.obtener_traza(st["req_id"])
        config = traza.config if traza else {}
        contexto = config["contexto_proyecto"] if "contexto_proyecto" in config else (proyecto.contexto if proyecto else None)
        return {"estado": Estado.CARGADO.value, "proyecto_id": proyecto_id, "ronda": 0, "lel": lel,
                "contexto": (contexto or "").strip() or None,
                "evaluacion": bool(proyecto and proyecto.tipo == "evaluacion"),
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
            if f.decision_filtro in ORIGEN_POR_DECISION and normalizar(f.termino) not in vistos:
                vistos.add(normalizar(f.termino))
                candidatos[f.termino] = TerminoEnProceso(
                    termino=f.termino, categoria_tentativa=f.categoria_tentativa.value,
                    origen=ORIGEN_POR_DECISION[f.decision_filtro], detalle=f.detalle, tipo_ambiguedad=None,
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
                                        origen=c["origen"], detalle=c.get("detalle")) for c in candidatos.values()]
            r = deps.clasificador.clasificar(texto, entrada, lel_de(st), st.get("contexto"))
            emitir(st, emisor=Nodo.CLASIFICADOR, receptor=Nodo.DIVERGENCIA, tipo=TipoMensaje.INTERPRETACIONES,
                   payload={"resultados": _dump(r.valor.resultados)}, respuesta=r)
            por_termino = {normalizar(x.termino): x for x in r.valor.resultados}
            for c in candidatos.values():
                res = por_termino[normalizar(c["termino"])]
                c["univoco"] = res.univoco
                c["tipo_ambiguedad"] = res.tipo_ambiguedad.value if res.tipo_ambiguedad else None
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
            a = deps.critico.arbitrar(texto, c["termino"], _interps(c["interpretaciones"]), lel, historial,
                                      st.get("contexto"))
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
    def validacion_automatica(st: EstadoGrafo) -> dict:
        """Aprueba la propuesta de cada término sin cambios cuando no hace falta una persona."""
        candidatos = {k: dict(c) for k, c in st["candidatos"].items()}
        detalle = []
        for termino, c in con_interpretaciones(candidatos).items():
            final = interpretacion_por_id(c, c["propuesta"])
            c["final"], c["cambio"] = final, "ninguno"
            detalle.append({"termino": termino, "propuesta": c["propuesta"], "final": final, "cambio": "ninguno"})
        emitir(st, emisor=Nodo.SISTEMA, receptor=Nodo.MODELADOR, tipo=TipoMensaje.VALIDACION,
               payload={"decision": "aprobar", "comentario": None, "terminos": detalle, "automatica": True,
                        "motivo": motivo_automatica(st)})
        return {"validacion": {"decision": "aprobar", "interpretaciones_editadas": {}, "comentario": None,
                               "automatica": True}, "candidatos": candidatos}

    @nodo
    def validado(st: EstadoGrafo) -> dict:
        return entrar(st, Estado.VALIDADO)

    @nodo
    def rechazado(st: EstadoGrafo) -> dict:
        return entrar(st, Estado.RECHAZADO)

    @nodo
    def formalizado(st: EstadoGrafo) -> dict:
        """Solo lo validado se formaliza (ADR 0007, 0010):
        - términos con ambigüedad léxica → una entrada del LEL cada uno;
        - alcance, anafórica, sintáctica → se resuelven en el requisito reescrito;
        - el requisito completo → reescrito y sus metas (modelo de metas).
        Los unívocos no entran al LEL."""
        texto, req_id, contexto = st["texto"], st["req_id"], st.get("contexto")
        proyecto_id = st.get("proyecto_id") or PROYECTO_GENERAL
        resueltos = con_interpretaciones(st["candidatos"])
        univocos = [c["termino"] for c in st["candidatos"].values() if c.get("univoco")]
        vaguedad = [t["termino"] for t in st.get("terminos", []) if t["decision_filtro"] == DecisionFiltro.VAGUEDAD.value]
        regionales = [t["termino"] for t in st.get("terminos", []) if t["decision_filtro"] == DecisionFiltro.REGIONAL.value]

        hechas = []
        for termino, c in resueltos.items():
            if not va_al_lel(c):
                continue
            interp = Interpretacion.model_validate(c["final"])
            m = deps.modelador.modelar(texto, termino, interp, contexto)
            entrada = EntradaLELFormalizada(
                **m.valor.entrada_lel.model_dump(), proyecto_id=proyecto_id,
                req_id=req_id, termino=termino, via=c["via"],
                interpretacion=interp, editada_por_humano=c.get("cambio") == "edicion", cambio=c.get("cambio"),
                fecha=date.today().isoformat())
            hechas.append((entrada, m))

        resoluciones = [{"termino": k, "tipo_ambiguedad": c.get("tipo_ambiguedad") or TipoAmbiguedad.LEXICA.value,
                         "interpretacion": c["final"], "via": c["via"], "cambio": c.get("cambio")}
                        for k, c in resueltos.items()]
        simbolos = sorted({e["simbolo"] for e in st.get("lel", [])} | {e.simbolo for e, _ in hechas})
        mr = deps.modelador.modelar_requisito(
            texto, [{k: r[k] for k in ("termino", "tipo_ambiguedad", "interpretacion")} for r in resoluciones],
            vaguedad, simbolos, contexto, regionales)

        # todo o nada: se guarda después de que el Modelador terminó con todo. Si el proceso
        # cae después de aquí, el nodo se reejecuta: guardar_lel reemplaza las de este req_id.
        repo.guardar_lel([e for e, _ in hechas])
        formalizado_doc = {
            "req_id": req_id, "proyecto_id": proyecto_id, "requisito_original": texto,
            "requisito_reescrito": mr.valor.requisito_reescrito,
            "tipo_requisito": mr.valor.tipo_requisito.value,
            "categoria": mr.valor.categoria.value if mr.valor.categoria else None,
            "supuestos": mr.valor.supuestos, "resoluciones": resoluciones,
            "metas": [m.model_dump(mode="json") for m in mr.valor.metas],
            "entradas_lel": [e.simbolo for e, _ in hechas], "univocos": univocos, "vaguedad": vaguedad,
            "fecha": date.today().isoformat(), "modelo": mr.modelo, "prompt_version": mr.prompt_version,
        }
        repo.guardar_doc(COLECCION_FORMALIZADOS, req_id, formalizado_doc)

        for entrada, m in hechas:
            emitir(st, emisor=Nodo.MODELADOR, receptor=Nodo.SISTEMA, tipo=TipoMensaje.FORMALIZACION, respuesta=m,
                   payload={"alcance": "termino", "termino": entrada.termino,
                            "tipo_ambiguedad": TipoAmbiguedad.LEXICA.value, "entrada_lel": entrada.model_dump(mode="json")})
        emitir(st, emisor=Nodo.MODELADOR, receptor=Nodo.SISTEMA, tipo=TipoMensaje.FORMALIZACION, respuesta=mr,
               payload={"alcance": "requisito", **{k: v for k, v in formalizado_doc.items()
                                                   if k not in ("modelo", "prompt_version", "fecha")},
                        "nota": None if hechas else "sin términos léxicos resueltos: no hay entradas nuevas en el LEL"})
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
                {"termino": k, "tipo_ambiguedad": c.get("tipo_ambiguedad"), "origen": c.get("origen"),
                 "detalle": c.get("detalle"), "decision": c["decision"], "via": c["via"], "similitud": c["similitud"],
                 "umbral": s.similarity_threshold, "propuesta": interpretacion_por_id(c, c["propuesta"]),
                 "interpretaciones": c["interpretaciones"], "retiradas": c["retiradas"],
                 "todas": c["todas"], "justificacion": c.get("justificacion"), "rondas": len(c["historial"])}
                for k, c in con_interpretaciones(candidatos).items()
            ],
            "univocos": [c["termino"] for c in candidatos.values() if c.get("univoco")],
            "vaguedad": por_decision(DecisionFiltro.VAGUEDAD.value),
            "resueltos_por_lel": por_decision(DecisionFiltro.RESUELTO_POR_LEL.value),
            "regionales": por_decision(DecisionFiltro.REGIONAL.value),
            "estructuras": [{"termino": t["termino"], "decision_filtro": t["decision_filtro"], "detalle": t.get("detalle")}
                            for t in st.get("terminos", [])
                            if t["decision_filtro"] in (DecisionFiltro.ALCANCE.value, DecisionFiltro.ANAFORA.value)],
        }

    # ------------------------------------------------------------ ¿hace falta una persona?

    def arbitrados(st: EstadoGrafo) -> list[str]:
        return [c["termino"] for c in con_interpretaciones(st["candidatos"]).values()
                if c.get("via") == Via.ARBITRAJE.value]

    def necesita_persona(st: EstadoGrafo) -> bool:
        """ADR 0017. Un proyecto de evaluación se detiene siempre antes de validar (ADR 0014)."""
        modo = ValidacionHumana(s.validacion_humana)
        if st.get("evaluacion") or modo == ValidacionHumana.SIEMPRE:
            return True
        if modo == ValidacionHumana.NUNCA:
            return False
        return bool(arbitrados(st))

    def motivo_automatica(st: EstadoGrafo) -> str:
        if ValidacionHumana(s.validacion_humana) == ValidacionHumana.NUNCA:
            return "validacion_desactivada"
        return "sin_ambiguedad" if not con_interpretaciones(st["candidatos"]) else "sin_arbitraje"

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
               pendiente_validacion, humano, validacion_automatica, validado, rechazado, formalizado, error):
        g.add_node(fn.__name__, fn)

    g.add_edge(START, "cargado")
    g.add_conditional_edges("cargado", o_error("extraido"), ["extraido", "error"])
    g.add_conditional_edges("extraido", o_error("interpretado"), ["interpretado", "error"])
    g.add_conditional_edges("interpretado", tras_interpretado, ["aceptado_directo", "en_debate", "error"])
    g.add_conditional_edges("en_debate", tras_ronda, ["consenso", "en_debate", "arbitrado", "error"])
    def tras_resolucion(st: EstadoGrafo) -> str:
        if st.get("fallo"):
            return "error"
        return "pendiente_validacion" if necesita_persona(st) else "validacion_automatica"

    for origen in ("aceptado_directo", "consenso", "arbitrado"):
        g.add_conditional_edges(origen, tras_resolucion, ["pendiente_validacion", "validacion_automatica", "error"])
    g.add_conditional_edges("pendiente_validacion", o_error("humano"), ["humano", "error"])
    g.add_conditional_edges("humano", tras_humano, ["validado", "rechazado", "error"])
    g.add_conditional_edges("validacion_automatica", o_error("validado"), ["validado", "error"])
    g.add_conditional_edges("validado", o_error("formalizado"), ["formalizado", "error"])
    g.add_conditional_edges("formalizado", o_error(END), [END, "error"])
    g.add_edge("rechazado", END)
    g.add_edge("error", END)
    return g.compile(checkpointer=checkpointer)
