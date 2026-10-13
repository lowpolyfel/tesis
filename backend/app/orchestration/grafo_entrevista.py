"""Grafo de LangGraph de la fase del LEL (ADR 0024): de una entrevista a su LEL propuesto.

La versión 1 procesaba un requisito a la vez (`grafo.py`). Ahora se procesa la
entrevista completa, una sola vez, para proponer el Léxico Extendido del Lenguaje del
dominio con la **intención** de cada término. Los mismos agentes y el mismo mecanismo de
divergencia, con prompts para la entrevista:

    cargada → leida → extraida → interpretada ──────────────→ modelada → lista
                                     └→ en_debate ⟲ → arbitrada ─┘
    (cualquier nodo con fallo → error)

- **leida**: el Revisor anota quién participa, el objetivo, los problemas, las
  necesidades y las reglas, con sus turnos (la ficha de la entrevista; la usan las
  metas y los requisitos).
- **extraida**: el Extractor separa los términos del dominio por partes; el código los
  ubica en todos los turnos donde aparecen, suma los regionales del catálogo, marca
  los vagos y los filtra contra la memoria del proyecto: un término que ya está en el
  LEL o tiene un acuerdo no se vuelve a interpretar (como `resuelto_por_lel`), uno que
  la persona descartó ya no se propone.
- **interpretada**: el Clasificador propone la intención de cada término; si ve más de
  una interpretación, las da como intenciones candidatas. La divergencia compara sus
  paráfrasis (embeddings + coseno, umbral calibrable).
- **en_debate / arbitrada**: si divergen, el Crítico objeta (R1, R2 en código; R3 el
  LLM), el Clasificador refina o retira, se recalcula la similitud; al agotar las
  rondas, el Crítico arbitra. Igual que en la versión 1.
- **modelada**: el Modelador formaliza cada término como entrada del LEL (símbolo,
  tipo, noción, impacto, intención, sinónimos). Las entradas quedan `propuestas`: las
  valida una persona experta (`app/fases/lexico.py`).

Los mensajes van a la bitácora de la entrevista con el mismo sobre y los mismos tipos
que la traza de un requisito: la escena en vivo los anima con la misma coreografía.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Callable, TypedDict

from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph

from app.artefactos.terminos import Comparador
from app.contexto import COLECCION_FICHAS, ficha_al_dia
from app.db.proyectos import Proyectos
from app.divergence import evaluar_divergencia
from app.entrevistas import almacen as ea
from app.entrevistas.almacen import Entrevistas
from app.fases.claves import clave as clave_de
from app.fases.claves import fragmento
from app.fases.lexico import Lexico, claves_de
from app.fases.memoria import acuerdos_en_texto
from app.llm import FalloEstructurado, Respuesta
from app.models import EntradaLEL, Estado, Interpretacion, Nodo, Objecion, RondaDebate, TipoMensaje, Via
from app.nlp import normalizar

from .dependencias import Dependencias
from .grafo import Cancelado, meta_llm

log = logging.getLogger(__name__)

_EMISOR_POR_PROMPT = {"extractor": Nodo.EXTRACTOR, "clasificador": Nodo.CLASIFICADOR, "critico": Nodo.CRITICO,
                      "modelador": Nodo.MODELADOR, "revisor": Nodo.REVISOR}
SIN_LEL = "(el LEL del proyecto todavía no tiene términos validados)"


class EstadoEntrevista(TypedDict, total=False):
    entrevista_id: str
    proyecto_id: str
    estado: str
    corrida: str  # «E01#2»: marca las entradas que crea esta ejecución
    contexto: str | None
    acuerdos: list[dict]  # la memoria del proyecto al empezar
    lel: list[dict]  # EntradaLEL de las entradas vigentes (vocabulario de R1 y R2)
    lel_texto: str  # las validadas, como van en los prompts
    conocidos: dict[str, str | None]  # clave → entrada_id (None: solo hay acuerdo en la memoria)
    descartados: list[str]  # claves que la persona descartó
    terminos: dict[str, dict]  # clave → término en proceso
    ronda: int
    fallo: dict | None


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def turnos_en_texto(turnos: list[dict]) -> str:
    return "\n".join(f"[T{t['n']}] {t['hablante'] + ': ' if t.get('hablante') else ''}{t['texto']}" for t in turnos)


def tandas(turnos: list[dict], limite: int) -> list[list[dict]]:
    """Turnos seguidos en partes de a lo más `limite` caracteres (un turno largo va solo)."""
    salida: list[list[dict]] = []
    actual: list[dict] = []
    largo = 0
    for t in turnos:
        n = len(t["texto"]) + 12
        if actual and largo + n > limite:
            salida.append(actual)
            actual, largo = [], 0
        actual.append(t)
        largo += n
    if actual:
        salida.append(actual)
    return salida


def en_lotes(xs: list, n: int) -> list[list]:
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def _interp(i: dict) -> Interpretacion:
    """Una intención candidata con el sobre de la versión 1: el Crítico y la divergencia la leen igual."""
    return Interpretacion(id=i["id"], significado=i["significado"], parafrasis_del_requisito=i["parafrasis"])


def _a_dict(i: dict) -> dict:
    """Intención con las dos claves de la paráfrasis: la coreografía y la vista leen las de la versión 1."""
    return {**i, "parafrasis_del_requisito": i["parafrasis"]}


def construir_grafo_entrevista(deps: Dependencias, checkpointer,
                               cancelado: Callable[[str], bool] = lambda _e: False):
    s = deps.settings
    entrevistas = Entrevistas(deps.repo)
    lexico = Lexico(deps.repo)
    comparador = Comparador(deps.analizador)
    clasificador = deps.clasificador_entrevista or deps.clasificador
    critico = deps.critico_entrevista or deps.critico

    # ------------------------------------------------------------ utilidades

    def emitir(st: EstadoEntrevista, *, emisor: Nodo, receptor: Nodo, tipo: TipoMensaje, payload: dict,
               ronda: int = 0, respuesta: Respuesta | None = None, modelo: str | None = None) -> None:
        if respuesta is not None:
            payload = {**payload, **meta_llm(respuesta)}
        entrevistas.agregar_mensaje(st["entrevista_id"], emisor=emisor.value, receptor=receptor.value, tipo=tipo.value,
                                    payload=payload, ronda=ronda, modelo=respuesta.modelo if respuesta else modelo,
                                    prompt_version=respuesta.prompt_version if respuesta else None)

    def entrar(st: EstadoEntrevista, estado: str, **cambios) -> dict:
        entrevistas.cambiar_estado(st["entrevista_id"], estado, **cambios)
        return {"estado": estado}

    def nodo(fn: Callable[[EstadoEntrevista], dict]) -> Callable[[EstadoEntrevista], dict]:
        @wraps(fn)
        def envuelto(st: EstadoEntrevista) -> dict:
            if cancelado(st.get("entrevista_id")):
                raise Cancelado(st.get("entrevista_id"))
            try:
                return fn(st)
            except GraphBubbleUp:
                raise
            except Exception as e:
                log.exception("Falla en el nodo %s (%s)", fn.__name__, st.get("entrevista_id"))
                fallo: dict[str, Any] = {"nodo": fn.__name__, "excepcion": type(e).__name__, "mensaje": str(e)}
                emisor, modelo = Nodo.SISTEMA, None
                if isinstance(e, FalloEstructurado):
                    fallo.update(e.payload())
                    emisor = _EMISOR_POR_PROMPT.get(e.prompt_version.split("_")[0], Nodo.SISTEMA)
                    modelo = e.modelo
                entrevistas.agregar_mensaje(st["entrevista_id"], emisor=emisor.value, receptor=Nodo.SISTEMA.value,
                                            tipo=TipoMensaje.ERROR.value, payload=fallo, ronda=st.get("ronda", 0),
                                            modelo=modelo, prompt_version=fallo.get("prompt_version"))
                return {"fallo": fallo}

        return envuelto

    def doc(st: EstadoEntrevista) -> dict:
        d = entrevistas.obtener(st["entrevista_id"])
        if d is None:
            raise Cancelado(st["entrevista_id"])  # se borró mientras corría
        return d

    def lel_de(st: EstadoEntrevista) -> list[EntradaLEL]:
        return [EntradaLEL.model_validate(e) for e in st.get("lel", [])]

    def citas(t: dict, turnos: dict[int, dict], n: int | None = None) -> list[dict]:
        return [{"entrevista": None, "turno": k, "hablante": turnos[k].get("hablante"),
                 "fragmento": fragmento(turnos[k]["texto"], t["termino"])}
                for k in t["turnos"][: n or len(t["turnos"])] if k in turnos]

    def citas_texto(t: dict, turnos: dict[int, dict]) -> str:
        return "\n".join(f"[T{c['turno']}] {(c['hablante'] + ': ') if c['hablante'] else ''}«{c['fragmento']}»"
                         for c in citas(t, turnos, s.lel_citas_por_termino))

    def por_numero(st: EstadoEntrevista) -> dict[int, dict]:
        return {t["n"]: t for t in doc(st)["turnos"]}

    # ------------------------------------------------------------ nodos

    @nodo
    def cargada(st: EstadoEntrevista) -> dict:
        d = doc(st)
        proyecto = Proyectos(deps.repo).obtener(d["proyecto_id"])
        ficha = deps.repo.obtener_doc(COLECCION_FICHAS, d["proyecto_id"])
        if proyecto and ficha_al_dia(ficha, proyecto.nombre, proyecto.contexto):
            contexto = ficha["markdown"]
        else:
            contexto = (proyecto.contexto if proyecto else None) or None
        acuerdos = lexico.memoria.listar(d["proyecto_id"])
        entradas = lexico.listar(d["proyecto_id"])
        vigentes = [e for e in entradas if e["estado"] != "descartado"]
        conocidos: dict[str, str | None] = {a["clave"]: None for a in acuerdos if not a.get("descartado")}
        for a in acuerdos:
            if not a.get("descartado"):
                for k in a.get("claves", []):
                    conocidos.setdefault(k, None)
        for e in vigentes:
            for k in e.get("claves") or [e["clave"]]:
                conocidos[k] = e["entrada_id"]
        descartados = sorted({e["clave"] for e in entradas if e["estado"] == "descartado"}
                             | {k for a in acuerdos if a.get("descartado") for k in a.get("claves", [a["clave"]])})
        lel = [{"simbolo": e["simbolo"], "tipo": e["tipo"], "nocion": e["nocion"],
                "impacto": e["impacto"] or e["nocion"]} for e in vigentes]
        validadas = [e for e in vigentes if e["estado"] in ("validado", "corregido")]
        lel_texto = "\n".join(f"- {e['simbolo']} ({e['tipo']}): {e['intencion']}" for e in validadas) or SIN_LEL
        return {"estado": ea.CARGADA, "proyecto_id": d["proyecto_id"], "contexto": contexto, "acuerdos": acuerdos,
                "lel": lel, "lel_texto": lel_texto, "conocidos": conocidos, "descartados": descartados,
                "terminos": {}, "ronda": 0, "fallo": None,
                "corrida": f"{st['entrevista_id']}#{d.get('corrida', 1)}"}

    @nodo
    def leida(st: EstadoEntrevista) -> dict:
        d = doc(st)
        turnos = d["turnos"]
        validos = {t["n"] for t in turnos}
        partes = tandas(turnos, s.revisor_tanda_caracteres)
        ficha = {"participantes": [], "objetivo": None, "problemas": [], "necesidades": [], "reglas": []}
        vistos: dict[str, set[str]] = {k: set() for k in ficha if k != "objetivo"}
        avisos, ultimo = [], None
        for i, parte in enumerate(partes, 1):
            try:
                r = deps.revisor.leer_entrevista(d["titulo"], turnos_en_texto(parte), i, len(partes), st.get("contexto"))
            except Exception as e:  # noqa: BLE001 — sin la ficha el LEL se puede armar igual
                avisos.append(f"El Revisor no pudo leer la parte {i} ({type(e).__name__}).")
                continue
            ultimo = r
            v = r.valor
            for p in v.participantes:
                k = normalizar(p.nombre)
                if k not in vistos["participantes"]:
                    vistos["participantes"].add(k)
                    ficha["participantes"].append(p.model_dump())
            ficha["objetivo"] = ficha["objetivo"] or v.objetivo
            for campo in ("problemas", "necesidades", "reglas"):
                for h in getattr(v, campo):
                    k = normalizar(h.texto)
                    if k in vistos[campo]:
                        continue
                    vistos[campo].add(k)
                    ficha[campo].append({"texto": h.texto, "turnos": sorted({n for n in h.turnos if n in validos})})
        ficha["avisos"] = avisos
        entrevistas.actualizar(st["entrevista_id"], ficha=ficha)
        emitir(st, emisor=Nodo.REVISOR, receptor=Nodo.EXTRACTOR, tipo=TipoMensaje.FICHA, respuesta=ultimo,
               modelo=None if ultimo else deps.revisor.cliente.modelo,
               payload={"partes": len(partes), "turnos": len(turnos), "participantes": ficha["participantes"],
                        "objetivo": ficha["objetivo"], "problemas": len(ficha["problemas"]),
                        "necesidades": len(ficha["necesidades"]), "reglas": len(ficha["reglas"]), "avisos": avisos})
        return entrar(st, ea.LEIDA)

    @nodo
    def extraida(st: EstadoEntrevista) -> dict:
        d = doc(st)
        turnos = d["turnos"]
        partes = tandas(turnos, s.entrevista_tanda_caracteres)
        encontrados: dict[str, dict] = {}
        respuestas, no_ubicados = [], []
        for i, parte in enumerate(partes, 1):
            r = deps.extractor.extraer_entrevista(turnos_en_texto(parte), i, len(partes), st.get("contexto"))
            respuestas.append(r)
            for t in r.valor.terminos:
                k = clave_de(t.termino)
                if not k:
                    continue
                if k not in encontrados:
                    encontrados[k] = {"termino": t.termino, "clave": k, "categoria": t.categoria.value,
                                      "formas": {t.termino}, "origen": "extractor", "detalle": None,
                                      "regional": False, "vago": False}
                else:
                    encontrados[k]["formas"].add(t.termino)

        # dónde aparece cada término: lo busca el código en toda la entrevista (no confía en el LLM),
        # por lema con spaCy y, además, por su clave en singular, palabra por palabra
        claves_turno = {x["n"]: f" {clave_de(x['texto'])} " for x in turnos}
        for k, t in list(encontrados.items()):
            t["turnos"] = [x["n"] for x in turnos
                           if any(f" {clave_de(f)} " in claves_turno[x["n"]] or comparador.aparece(f, x["texto"])
                                  for f in t["formas"])]
            if not t["turnos"]:
                no_ubicados.append(t["termino"])
                del encontrados[k]

        # catálogos: regionales (siempre a interpretar) y vaguedad (se marca, no se debate)
        vaguedad: dict[str, dict] = {}
        if deps.analizador is not None:
            catalogos = deps.filtros.catalogos
            for x in turnos:
                docx = deps.analizador.doc(x["texto"])
                for c in catalogos.regionales.buscar(docx):
                    k = clave_de(c.expresion)
                    t = encontrados.setdefault(k, {
                        "termino": c.texto, "clave": k, "categoria": "verbo" if len(c.expresion.split()) > 1
                        or c.expresion.endswith(("ar", "er", "ir")) else "objeto", "formas": {c.texto},
                        "origen": "regional", "turnos": [], "regional": True, "vago": False,
                        "detalle": None})
                    t["regional"], t["origen"] = True, "regional"
                    t["detalle"] = "sentidos comunes en el habla de trabajo: " + ", ".join(
                        c.entrada.get("significados_posibles", []))
                    if x["n"] not in t["turnos"]:
                        t["turnos"] = sorted([*t["turnos"], x["n"]])
                for c in catalogos.vaguedad.buscar(docx):
                    v = vaguedad.setdefault(clave_de(c.expresion), {"expresion": c.expresion, "turnos": []})
                    if x["n"] not in v["turnos"]:
                        v["turnos"].append(x["n"])
        for t in encontrados.values():
            t["vago"] = t["clave"] in vaguedad

        # filtros contra la memoria del proyecto
        conocidos, descartados = st.get("conocidos", {}), set(st.get("descartados", []))
        for t in encontrados.values():
            ks = {t["clave"], *(clave_de(f) for f in t["formas"])}
            if ks & descartados:
                t["decision_filtro"] = "descartado_por_persona"
            elif ks & set(conocidos):
                t["decision_filtro"] = "resuelto_por_lel"
                t["entrada_id"] = next((conocidos[k] for k in ks if conocidos.get(k)), None)
                t["clave_conocida"] = next(k for k in ks if k in conocidos)
            else:
                t["decision_filtro"] = "regional" if t["regional"] else "candidato"
        nuevos = sorted((t for t in encontrados.values() if t["decision_filtro"] in ("candidato", "regional")),
                        key=lambda t: (not t["regional"], -len(t["turnos"])))
        fuera = {t["clave"] for t in nuevos[s.lel_max_terminos:]}
        for t in encontrados.values():
            if t["clave"] in fuera:
                t["decision_filtro"] = "fuera_del_limite"
            t["formas"] = sorted(t["formas"])

        entrevistas.actualizar(st["entrevista_id"], vaguedad=list(vaguedad.values()))
        emitir(st, emisor=Nodo.EXTRACTOR, receptor=Nodo.FILTROS, tipo=TipoMensaje.EXTRACCION,
               respuesta=respuestas[-1] if respuestas else None,
               payload={"partes": len(partes), "descartados": no_ubicados,
                        "terminos": [{"termino": t["termino"], "categoria_tentativa": t["categoria"],
                                      "turnos": t["turnos"]} for t in encontrados.values() if t["origen"] == "extractor"],
                        "intentos_por_parte": [len(r.intentos) for r in respuestas]})
        filtrados = [{"termino": t["termino"], "decision_filtro": t["decision_filtro"], "categoria_tentativa": t["categoria"],
                      "detalle": t["detalle"], "turnos": t["turnos"]} for t in encontrados.values()]
        filtrados += [{"termino": v["expresion"], "decision_filtro": "vaguedad", "categoria_tentativa": "estado",
                       "detalle": "expresión vaga: se marca, no se debate", "turnos": v["turnos"]}
                      for v in vaguedad.values()]
        emitir(st, emisor=Nodo.FILTROS, receptor=Nodo.CLASIFICADOR, tipo=TipoMensaje.FILTRADO,
               payload={"terminos": filtrados, "entradas_lel": len({v for v in conocidos.values() if v}),
                        "acuerdos": len(st.get("acuerdos", [])), "catalogos": deps.filtros.catalogos.versiones()
                        if deps.analizador is not None else None})
        return {**entrar(st, ea.EXTRAIDA), "terminos": encontrados}

    @nodo
    def interpretada(st: EstadoEntrevista) -> dict:
        turnos = por_numero(st)
        terminos = {k: dict(t) for k, t in st["terminos"].items()}
        candidatos = [t for t in terminos.values() if t["decision_filtro"] in ("candidato", "regional")]
        acuerdos = acuerdos_en_texto(st.get("acuerdos", []))
        for lote in en_lotes(candidatos, s.lel_tanda_terminos):
            entrada = [{"termino": t["termino"], "categoria_tentativa": t["categoria"], "origen": t["origen"],
                        "detalle": t["detalle"], "citas": citas_texto(t, turnos).split("\n")} for t in lote]
            r = clasificador.intenciones(entrada, st.get("lel_texto", SIN_LEL), acuerdos, st.get("contexto"))
            por_termino = {normalizar(x.termino): x for x in r.valor.resultados}
            resultados = []
            for t in lote:
                res = por_termino[normalizar(t["termino"])]
                t["intenciones"] = [i.model_dump(mode="json") for i in res.intenciones]
                t["todas"] = {i["id"]: i for i in t["intenciones"]}
                t["tipo_ambiguedad"] = res.tipo_ambiguedad.value if res.tipo_ambiguedad else None
                t["univoco"] = res.univoco
                t.update(retiradas=[], historial=[], similitud=None, decision=None, justificacion=None)
                if res.univoco:
                    t["via"], t["propuesta"] = "univoco", t["intenciones"][0]["id"]
                resultados.append({"termino": t["termino"], "univoco": res.univoco,
                                   "tipo_ambiguedad": t["tipo_ambiguedad"],
                                   "interpretaciones": [] if res.univoco else [_a_dict(i) for i in t["intenciones"]],
                                   "intencion": t["intenciones"][0] if res.univoco else None})
            emitir(st, emisor=Nodo.CLASIFICADOR, receptor=Nodo.DIVERGENCIA, tipo=TipoMensaje.INTERPRETACIONES,
                   payload={"resultados": resultados}, respuesta=r)
        if not candidatos:
            emitir(st, emisor=Nodo.SISTEMA, receptor=Nodo.DIVERGENCIA, tipo=TipoMensaje.INTERPRETACIONES,
                   payload={"resultados": [], "nota": "sin términos nuevos: todos ya estaban en el LEL o la memoria"})

        ambiguos = [t for t in candidatos if not t.get("univoco")]
        if not ambiguos:
            emitir(st, emisor=Nodo.DIVERGENCIA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.SIMILITUD,
                   payload={"similitud": None, "umbral": s.similarity_threshold, "motivo": "sin_interpretaciones",
                            "decision": Estado.ACEPTADO_DIRECTO.value})
        for t in ambiguos:
            dv = evaluar_divergencia(t["termino"], [_interp(i) for i in t["intenciones"]], deps.embeddings,
                                     s.similarity_threshold)
            t["similitud"], t["decision"] = dv.similitud, dv.decision.value
            if dv.decision == Estado.ACEPTADO_DIRECTO:
                t["via"], t["propuesta"] = Via.ACEPTADO_DIRECTO.value, t["intenciones"][0]["id"]
            emitir(st, emisor=Nodo.DIVERGENCIA,
                   receptor=Nodo.CRITICO if dv.decision == Estado.EN_DEBATE else Nodo.SISTEMA,
                   tipo=TipoMensaje.SIMILITUD, payload=dv.payload(), modelo=dv.modelo_embeddings)
        return {**entrar(st, ea.INTERPRETADA), "terminos": terminos}

    @nodo
    def en_debate(st: EstadoEntrevista) -> dict:
        turnos, lel = por_numero(st), lel_de(st)
        ronda = st.get("ronda", 0) + 1
        terminos = {k: dict(t) for k, t in st["terminos"].items()}
        for t in terminos.values():
            if t.get("decision") != Estado.EN_DEBATE.value:
                continue
            texto, termino = citas_texto(t, turnos), t["termino"]
            interps = [_interp(i) for i in t["intenciones"]]
            ev = critico.evaluar(texto, termino, interps, lel)
            objeciones: list[Objecion] = ev.valor.objeciones
            emitir(st, ronda=ronda, emisor=Nodo.CRITICO, receptor=Nodo.CLASIFICADOR, tipo=TipoMensaje.OBJECION,
                   payload={"termino": termino, "evaluaciones": [x.model_dump(mode="json") for x in ev.valor.evaluaciones],
                            "objeciones": [o.model_dump(mode="json") for o in objeciones]}, respuesta=ev)
            if objeciones:
                rf = clasificador.refinar(texto, termino, interps, objeciones)
                vigentes_ = rf.valor.interpretaciones
                retiradas = rf.valor.retiradas
                previas = {i["id"]: i for i in t["intenciones"]}
                t["intenciones"] = [{**previas[i.id], "significado": i.significado,
                                     "parafrasis": i.parafrasis_del_requisito} for i in vigentes_]
                emitir(st, ronda=ronda, emisor=Nodo.CLASIFICADOR, receptor=Nodo.DIVERGENCIA,
                       tipo=TipoMensaje.REFINAMIENTO, respuesta=rf,
                       payload={"termino": termino, "interpretaciones": [_a_dict(i) for i in t["intenciones"]],
                                "retiradas": [x.model_dump(mode="json") for x in retiradas]})
            else:
                retiradas = []
                emitir(st, ronda=ronda, emisor=Nodo.SISTEMA, receptor=Nodo.DIVERGENCIA, tipo=TipoMensaje.REFINAMIENTO,
                       payload={"termino": termino, "interpretaciones": [_a_dict(i) for i in t["intenciones"]],
                                "retiradas": [], "nota": "sin objeciones del Crítico: no se consultó al Clasificador"})
            t["todas"] = {**t["todas"], **{i["id"]: i for i in t["intenciones"]}}
            t["retiradas"] = t["retiradas"] + [{**x.model_dump(mode="json"), "ronda": ronda} for x in retiradas]

            motivo = None
            if len(t["intenciones"]) == 1:
                t["similitud"], motivo = None, "una_interpretacion"
            else:
                dv = evaluar_divergencia(termino, [_interp(i) for i in t["intenciones"]], deps.embeddings,
                                         s.similarity_threshold)
                t["similitud"] = dv.similitud
                if dv.decision == Estado.ACEPTADO_DIRECTO:
                    motivo = "umbral"
                emitir(st, ronda=ronda, emisor=Nodo.DIVERGENCIA, receptor=Nodo.SISTEMA if motivo else Nodo.CRITICO,
                       tipo=TipoMensaje.SIMILITUD, modelo=dv.modelo_embeddings,
                       payload={**dv.payload(), "decision": (Estado.CONSENSO if motivo else Estado.EN_DEBATE).value})
            t["historial"] = t["historial"] + [RondaDebate(
                ronda=ronda, interpretaciones=[_interp(i) for i in t["intenciones"]], objeciones=objeciones,
                retiradas=retiradas, similitud=t["similitud"]).model_dump(mode="json")]
            if motivo:
                t["decision"], t["via"], t["propuesta"] = Estado.CONSENSO.value, Via.CONSENSO.value, t["intenciones"][0]["id"]
                emitir(st, ronda=ronda, emisor=Nodo.SISTEMA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.CONSENSO,
                       payload={"termino": termino, "motivo": motivo, "similitud": t["similitud"],
                                "umbral": s.similarity_threshold, "propuesta": t["propuesta"],
                                "interpretaciones": [_a_dict(i) for i in t["intenciones"]]})
        entrevistas.cambiar_estado(st["entrevista_id"], ea.EN_DEBATE)
        return {"estado": ea.EN_DEBATE, "ronda": ronda, "terminos": terminos}

    @nodo
    def arbitrada(st: EstadoEntrevista) -> dict:
        turnos, lel, ronda = por_numero(st), lel_de(st), st.get("ronda", 0)
        terminos = {k: dict(t) for k, t in st["terminos"].items()}
        for t in terminos.values():
            if t.get("decision") != Estado.EN_DEBATE.value:
                continue
            historial = [RondaDebate.model_validate(h) for h in t["historial"]]
            a = critico.arbitrar(citas_texto(t, turnos), t["termino"], [_interp(i) for i in t["intenciones"]], lel,
                                 historial, st.get("contexto"))
            t["decision"], t["via"] = Estado.ARBITRADO.value, Via.ARBITRAJE.value
            t["propuesta"] = a.valor.interpretacion_elegida
            t["justificacion"] = [j.model_dump(mode="json") for j in a.valor.justificacion_por_regla]
            emitir(st, ronda=ronda, emisor=Nodo.CRITICO, receptor=Nodo.SISTEMA, tipo=TipoMensaje.ARBITRAJE,
                   payload={"termino": t["termino"], **a.valor.model_dump(mode="json"),
                            "interpretaciones": [_a_dict(i) for i in t["intenciones"]]}, respuesta=a)
        return {**entrar(st, ea.ARBITRADA), "terminos": terminos}

    @nodo
    def modelada(st: EstadoEntrevista) -> dict:
        eid, pid, corrida = st["entrevista_id"], st["proyecto_id"], st["corrida"]
        turnos = por_numero(st)
        terminos = st["terminos"]
        fecha = ahora()
        acuerdos = acuerdos_en_texto(st.get("acuerdos", []))
        candidatos = [t for t in terminos.values() if t["decision_filtro"] in ("candidato", "regional")]

        def elegida(t: dict) -> dict:
            return t["todas"].get(t["propuesta"]) or t["intenciones"][0]

        hechas: list[tuple[dict, dict, Respuesta]] = []  # (término, entrada del LLM, respuesta)
        for lote in en_lotes(candidatos, s.lel_tanda_terminos):
            entrada = [{"termino": t["termino"], "categoria_tentativa": t["categoria"],
                        "intencion": {k: elegida(t)[k] for k in ("significado", "intencion")},
                        "citas": citas_texto(t, turnos).split("\n")} for t in lote]
            r = deps.modelador.lexico(entrada, acuerdos, st.get("contexto"))
            por_termino = {normalizar(x.termino): x for x in r.valor.entradas}
            for t in lote:
                hechas.append((t, por_termino[normalizar(t["termino"])].model_dump(mode="json"), r))
            emitir(st, emisor=Nodo.MODELADOR, receptor=Nodo.SISTEMA, tipo=TipoMensaje.FORMALIZACION, respuesta=r,
                   payload={"alcance": "lexico", "entradas": [
                       {"termino": x.termino, "simbolo": x.simbolo, "tipo": x.tipo.value} for x in r.valor.entradas]})

        # todo o nada: se guarda cuando el Modelador terminó con todo. Si el proceso se cae
        # después de aquí y el nodo se repite, lo que creó esta corrida se borra primero.
        deps.repo.borrar_docs("lexico", proyecto_id=pid, corrida=corrida)
        existentes = {e["entrada_id"]: e for e in lexico.listar(pid)}
        por_clave = {k: e for e in existentes.values() for k in (e.get("claves") or [e["clave"]])}
        nuevas, sumadas = [], []

        def citas_de(t: dict) -> list[dict]:
            return [{**c, "entrevista": eid} for c in citas(t, turnos, 12)]

        for t, x, r in hechas:
            k = clave_de(x["simbolo"])
            ya = por_clave.get(k) or por_clave.get(t["clave"])
            if ya is not None:  # dos términos de la entrevista con el mismo símbolo, o uno que ya estaba
                lexico.agregar_citas(ya, citas_de(t), eid, t["formas"], fecha)
                sumadas.append(ya["entrada_id"])
                continue
            amb = None
            if len(t["todas"]) > 1:
                retiradas = {x_["interpretacion_id"]: x_ for x_ in t.get("retiradas", [])}
                amb = {"tipo": t.get("tipo_ambiguedad"), "similitud": t.get("similitud"), "umbral": s.similarity_threshold,
                       "rondas": len(t.get("historial", [])), "via": t.get("via"), "elegida": t.get("propuesta"),
                       "justificacion": t.get("justificacion"),
                       "alternativas": [{**i, "retirada": retiradas.get(i["id"], {}).get("motivo")}
                                        for i in t["todas"].values()]}
            datos = {"proyecto_id": pid, "clave": k, "claves": claves_de(x["simbolo"], x["sinonimos"], t["formas"]),
                     "simbolo": x["simbolo"], "tipo": x["tipo"], "nocion": x["nocion"], "impacto": x["impacto"],
                     "intencion": x["intencion"], "sinonimos": x["sinonimos"], "terminos": t["formas"],
                     "citas": citas_de(t), "entrevistas": [eid],
                     "marcas": {"regional": t["regional"], "vago": t["vago"]}, "ambiguedad": amb,
                     "via": t.get("via") or "univoco", "estado": "propuesto", "aprendida": False,
                     "historial": [{"fecha": fecha, "accion": "proponer", "autor": "agentes", "entrevista": eid}],
                     "modelo": r.modelo, "prompt_version": r.prompt_version, "corrida": corrida,
                     "creada": fecha, "actualizada": fecha}
            e = lexico.crear(datos)
            nuevas.append(e["entrada_id"])
            for kk in e["claves"]:
                por_clave.setdefault(kk, e)

        # los que ya conocía el proyecto: se les suman las citas de esta entrevista
        memoria = {a["clave"]: a for a in st.get("acuerdos", [])}
        for t in terminos.values():
            if t["decision_filtro"] != "resuelto_por_lel":
                continue
            ya = existentes.get(t.get("entrada_id")) if t.get("entrada_id") else None
            ya = ya or por_clave.get(t["clave"])
            if ya is not None:
                lexico.agregar_citas(ya, citas_de(t), eid, t["formas"], fecha)
                sumadas.append(ya["entrada_id"])
                continue
            a = memoria.get(t.get("clave_conocida") or t["clave"])
            if a is None:
                continue
            e = lexico.crear({  # el acuerdo existe pero su entrada no (se borró la entrevista de donde salió)
                "proyecto_id": pid, "clave": a["clave"], "claves": a.get("claves") or [a["clave"]],
                "simbolo": a["simbolo"], "tipo": a.get("tipo") or t["categoria"], "nocion": a.get("nocion") or [a["significa"]],
                "impacto": a.get("nocion") or [a["significa"]], "intencion": a["significa"], "sinonimos": [],
                "terminos": t["formas"], "citas": citas_de(t), "entrevistas": [eid],
                "marcas": {"regional": t["regional"], "vago": t["vago"]}, "ambiguedad": None, "via": "memoria",
                "estado": "validado", "aprendida": True,
                "historial": [{"fecha": fecha, "accion": "recordar", "autor": "sistema", "entrevista": eid}],
                "modelo": None, "prompt_version": None, "corrida": corrida, "creada": fecha, "actualizada": fecha})
            nuevas.append(e["entrada_id"])
            por_clave[e["clave"]] = e

        resumen = {
            "terminos": len(terminos), "nuevas": len(nuevas), "conocidas": len(set(sumadas)),
            "ambiguas": sum(1 for t in candidatos if len(t.get("todas", {})) > 1),
            "debatidas": sum(1 for t in candidatos if t.get("historial")),
            "arbitradas": sum(1 for t in candidatos if t.get("via") == Via.ARBITRAJE.value),
            "descartadas_por_persona": sum(1 for t in terminos.values() if t["decision_filtro"] == "descartado_por_persona"),
            "fuera_del_limite": sum(1 for t in terminos.values() if t["decision_filtro"] == "fuera_del_limite"),
            "regionales": sum(1 for t in terminos.values() if t["regional"]),
        }
        if not candidatos:
            emitir(st, emisor=Nodo.SISTEMA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.FORMALIZACION,
                   payload={"alcance": "lexico", "entradas": [], "nota": "sin términos nuevos para el LEL"})
        return {**entrar(st, ea.LISTA, resumen=resumen, error=None), "fallo": None}

    def error(st: EstadoEntrevista) -> dict:
        fallo = st.get("fallo") or {}
        return entrar(st, ea.ERROR, error=f"{fallo.get('nodo') or ''}: {fallo.get('mensaje') or 'falla'}".strip(": "))

    # ------------------------------------------------------------ aristas

    def o_error(siguiente: str):
        def ruta(st: EstadoEntrevista) -> str:
            return "error" if st.get("fallo") else siguiente
        return ruta

    def hay_debate(st: EstadoEntrevista) -> bool:
        return any(t.get("decision") == Estado.EN_DEBATE.value for t in st["terminos"].values())

    def tras_interpretada(st: EstadoEntrevista) -> str:
        if st.get("fallo"):
            return "error"
        return "en_debate" if hay_debate(st) else "modelada"

    def tras_ronda(st: EstadoEntrevista) -> str:
        if st.get("fallo"):
            return "error"
        if not hay_debate(st):
            return "modelada"
        return "en_debate" if st["ronda"] < s.max_debate_rounds else "arbitrada"

    g = StateGraph(EstadoEntrevista)
    for fn in (cargada, leida, extraida, interpretada, en_debate, arbitrada, modelada, error):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "cargada")
    g.add_conditional_edges("cargada", o_error("leida"), ["leida", "error"])
    g.add_conditional_edges("leida", o_error("extraida"), ["extraida", "error"])
    g.add_conditional_edges("extraida", o_error("interpretada"), ["interpretada", "error"])
    g.add_conditional_edges("interpretada", tras_interpretada, ["en_debate", "modelada", "error"])
    g.add_conditional_edges("en_debate", tras_ronda, ["en_debate", "arbitrada", "modelada", "error"])
    g.add_conditional_edges("arbitrada", o_error("modelada"), ["modelada", "error"])
    g.add_conditional_edges("modelada", o_error(END), [END, "error"])
    g.add_edge("error", END)
    return g.compile(checkpointer=checkpointer)
