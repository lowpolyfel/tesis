"""Corrida de una comparación: documento en `comparaciones`, por la cola o en el mismo hilo.

Orden de la corrida (cada paso se guarda para que la API muestre el avance):
1. bases de comparación e inconsistencias de vocabulario (deterministas);
2. embeddings, matriz de similitud, selección de pares y casi duplicados;
3. juez LLM por par seleccionado. Si el LLM falla en un par, el par queda con
   `error` y la comparación sigue.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import get_args

from app.llm import FalloEstructurado
from app.models import ahora
from app.orchestration.grafo import COLECCION_FORMALIZADOS

from .bases import bases_de_comparacion, significados_validados
from .juez import PROMPT, Juez, cita_literal
from .modelos import (
    HALLAZGO_POR_RELACION,
    Avance,
    Comparacion,
    ConfigComparacion,
    ErrorComparacion,
    ErrorPar,
    Hallazgo,
    ParFuera,
    RelacionPar,
    RequisitoBase,
    ResumenComparacion,
    TipoHallazgo,
)
from .pares import (
    Par,
    analizar_simbolos,
    casi_duplicados,
    clave_par,
    compartidos,
    matriz_similitud,
    perfil,
    seleccionar_pares,
)
from .vocabulario import inconsistencias_vocabulario

log = logging.getLogger(__name__)

COLECCION = "comparaciones"
PREFIJO = "C"
PENDIENTES = ("en_cola", "en_proceso")


class RequisitosInsuficientes(ValueError):
    """El proyecto no tiene al menos dos requisitos que se puedan comparar."""


class SinComparador(RuntimeError):
    """El servicio no tiene cliente LLM para el juez (`llm_comparador`)."""


def _bases(srv, proyecto_id: str):
    trazas = srv.repo.trazas_completas(proyecto_id)
    formalizados = {t.req_id: d for t in trazas if (d := srv.repo.obtener_doc(COLECCION_FORMALIZADOS, t.req_id))}
    requisitos, excluidos = bases_de_comparacion(trazas, formalizados)
    return requisitos, excluidos, trazas, formalizados


def _exigir_dos(requisitos: list, proyecto_id: str) -> None:
    if len(requisitos) < 2:
        raise RequisitosInsuficientes(
            f"El proyecto {proyecto_id} tiene {len(requisitos)} requisito(s) comparable(s); se necesitan al menos 2 "
            "(no cuentan los que están en error, rechazados o reprocesados)")


def _modelos(srv) -> dict:
    """Modelos con los que se corre ahora: se vuelven a leer al ejecutar, porque una
    comparación recuperada tras un reinicio puede correr con otros."""
    cliente = srv.deps.llm_comparador
    return {"modelo": cliente.modelo if cliente else None, "modelo_embeddings": getattr(srv.deps.embeddings, "modelo", None)}


def _config(srv) -> ConfigComparacion:
    s = srv.deps.settings
    return ConfigComparacion(
        umbral_relacion=s.comparacion_relacion_umbral, umbral_duplicado=s.comparacion_duplicado_umbral,
        max_pares=s.comparacion_max_pares, prompt_version=PROMPT, **_modelos(srv))


def _guardar(srv, c: Comparacion) -> None:
    srv.repo.guardar_doc(COLECCION, c.comparacion_id, c.model_dump(mode="json"))


# ---------------------------------------------------------------- operaciones

def preparar(srv, proyecto_id: str) -> Comparacion:
    """Crea el documento `en_cola`. KeyError si el proyecto no existe; SinComparador si
    no hay cliente para el juez; RequisitosInsuficientes si no hay al menos dos
    requisitos comparables."""
    if srv.proyectos.obtener(proyecto_id) is None:
        raise KeyError(proyecto_id)
    if srv.deps.llm_comparador is None:
        raise SinComparador("No hay cliente LLM para el comparador (llm_comparador)")
    _exigir_dos(_bases(srv, proyecto_id)[0], proyecto_id)
    config = _config(srv)
    datos = srv.repo.crear_doc(COLECCION, PREFIJO, lambda cid: Comparacion(
        comparacion_id=cid, proyecto_id=proyecto_id, config=config).model_dump(mode="json"))
    return Comparacion.model_validate(datos)


def solicitar(srv, proyecto_id: str) -> Comparacion:
    """Preparar y encolar (API). Va en la prioridad de análisis: después de los requisitos."""
    c = preparar(srv, proyecto_id)
    srv.cola.encolar("analisis", c.comparacion_id, lambda: ejecutar(srv, c.comparacion_id))
    return c


def comparar(srv, proyecto_id: str) -> Comparacion:
    """Preparar y ejecutar en el mismo hilo (scripts y pruebas)."""
    return ejecutar(srv, preparar(srv, proyecto_id).comparacion_id)


def obtener(srv, comparacion_id: str) -> Comparacion | None:
    datos = srv.repo.obtener_doc(COLECCION, comparacion_id)
    return Comparacion.model_validate(datos) if datos else None


def resumen(c: Comparacion) -> ResumenComparacion:
    conteo = Counter(h.tipo for h in c.hallazgos)
    return ResumenComparacion(
        comparacion_id=c.comparacion_id, proyecto_id=c.proyecto_id, estado=c.estado, creado=c.creado,
        terminado=c.terminado, config=c.config, n_requisitos=len(c.requisitos), pares_evaluados=c.pares_evaluados,
        pares_fuera_por_limite=c.pares_fuera_por_limite, pares_con_error=c.pares_con_error,
        hallazgos_por_tipo={t: conteo.get(t, 0) for t in get_args(TipoHallazgo)}, error=c.error)


def listar(srv, proyecto_id: str) -> list[ResumenComparacion]:
    """Resúmenes del proyecto, la más reciente primero."""
    docs = srv.repo.listar_docs(COLECCION, proyecto_id=proyecto_id)
    return [resumen(Comparacion.model_validate(d)) for d in reversed(docs)]


def _en_la_cola(srv) -> set[str]:
    estado = srv.cola.estado()
    trabajos = estado["pendientes"] + ([estado["en_proceso"]] if estado["en_proceso"] else [])
    return {t["clave"] for t in trabajos if t["tipo"] == "analisis"}


def recuperar(srv) -> list[str]:
    """Tras un reinicio, vuelve a encolar las comparaciones que quedaron en cola o a medias
    (se corren desde el principio). La API lo llama al arrancar (lifespan del router);
    las que ya están en la cola no se encolan dos veces."""
    ya = _en_la_cola(srv)
    ids = [d["comparacion_id"] for d in srv.repo.listar_docs(COLECCION)
           if d.get("estado") in PENDIENTES and d.get("comparacion_id") not in ya]
    for cid in ids:
        srv.cola.encolar("analisis", cid, lambda cid=cid: ejecutar(srv, cid))
    return ids


def ejecutar(srv, comparacion_id: str) -> Comparacion:
    """Corre la comparación desde el principio y deja el documento `terminada` o `error`."""
    previa = obtener(srv, comparacion_id)
    if previa is None:
        raise KeyError(comparacion_id)
    # umbrales y límite: los de la solicitud; modelos: los que de verdad se usan en esta corrida
    c = Comparacion(comparacion_id=previa.comparacion_id, proyecto_id=previa.proyecto_id, creado=previa.creado,
                    config=previa.config.model_copy(update=_modelos(srv)), estado="en_proceso")
    _guardar(srv, c)
    try:
        _correr(srv, c)
        c.estado = "terminada"
    except Exception as e:
        log.exception("Falló la comparación %s", comparacion_id)
        c.estado, c.error = "error", ErrorComparacion(excepcion=type(e).__name__, mensaje=str(e))
    c.terminado = ahora()
    _guardar(srv, c)
    return c


# ---------------------------------------------------------------- corrida

def _hallazgo(hallazgos: list[Hallazgo], datos: dict) -> None:
    hallazgos.append(Hallazgo(id=f"H{len(hallazgos) + 1}", **datos))


def _juzgar(juez: Juez, a: RequisitoBase, b: RequisitoBase, par: Par) -> tuple[RelacionPar, dict | None]:
    base = {"par": par.clave, "requisitos": [par.a, par.b], "similitud": par.similitud,
            "motivos": list(par.motivos), "compartidos": list(par.compartidos)}
    try:
        r = juez.juzgar(a, b)
    except FalloEstructurado as e:
        return RelacionPar(**base, error=ErrorPar(excepcion=type(e).__name__, mensaje=str(e),
                                                  intentos=e.payload()["intentos"])), None
    except Exception as e:  # p. ej. el servidor del modelo no responde: el par queda con error y se sigue
        log.warning("El juez falló en el par %s: %s", par.clave, e)
        return RelacionPar(**base, error=ErrorPar(excepcion=type(e).__name__, mensaje=str(e))), None
    v = r.valor
    relacion = RelacionPar(**base, relacion=v.relacion, explicacion=v.explicacion)
    tipo = HALLAZGO_POR_RELACION.get(v.relacion)
    if tipo is None:
        return relacion, None
    return relacion, {
        "tipo": tipo, "requisitos": [a.req_id, b.req_id], "terminos": list(par.compartidos), "similitud": par.similitud,
        "explicacion": v.explicacion,
        "evidencia": [{"req_id": a.req_id, "cita": v.cita_a, "verificada": cita_literal(v.cita_a, a.texto)},
                      {"req_id": b.req_id, "cita": v.cita_b, "verificada": cita_literal(v.cita_b, b.texto)}],
        "fuente": "llm", "modelo": r.modelo, "prompt_version": r.prompt_version}


def _correr(srv, c: Comparacion) -> None:
    deps, cfg = srv.deps, c.config
    if deps.llm_comparador is None or deps.analizador is None:
        raise RuntimeError("la comparación necesita el cliente LLM del comparador y el analizador de spaCy")

    # 1. bases e inconsistencias de vocabulario
    requisitos, excluidos, trazas, formalizados = _bases(srv, c.proyecto_id)
    c.requisitos, c.excluidos = requisitos, excluidos
    _exigir_dos(requisitos, c.proyecto_id)
    ids = [r.req_id for r in requisitos]
    lel = srv.repo.listar_lel(c.proyecto_id)
    incluidos = set(ids)
    significados = [s for t in trazas if t.req_id in incluidos for s in significados_validados(t, formalizados.get(t.req_id))]
    for h in inconsistencias_vocabulario(lel, significados):
        _hallazgo(c.hallazgos, h)
    c.pares_totales = len(ids) * (len(ids) - 1) // 2
    _guardar(srv, c)

    # 2. similitud, selección y casi duplicados
    c.matriz_similitud = matriz_similitud(ids, deps.embeddings.vectorizar([r.texto for r in requisitos]))
    for h in c.hallazgos:  # el LEL puede citar requisitos que ya no se comparan: quedan sin similitud
        h.similitud = c.matriz_similitud.get(clave_par(*h.requisitos))
    simbolos_lel = analizar_simbolos(deps.analizador, list(dict.fromkeys(e.simbolo for e in lel)))
    perfiles = {r.req_id: perfil(deps.analizador, r.texto, simbolos_lel) for r in requisitos}
    textos = {r.req_id: r.texto for r in requisitos}
    for a, b, x in casi_duplicados(ids, c.matriz_similitud, cfg.umbral_duplicado):
        simbolos, lemas = compartidos(perfiles[a], perfiles[b])
        _hallazgo(c.hallazgos, {
            "tipo": "casi_duplicado", "requisitos": [a, b], "terminos": list(dict.fromkeys(simbolos + lemas)),
            "similitud": x, "explicacion": f"Similitud coseno {x:.3f} >= umbral de duplicado {cfg.umbral_duplicado}.",
            "evidencia": [{"req_id": r, "cita": textos[r], "verificada": True} for r in (a, b)],
            "fuente": "embeddings", "modelo": cfg.modelo_embeddings, "prompt_version": None})
    sel = seleccionar_pares(ids, c.matriz_similitud, perfiles, cfg.umbral_relacion, cfg.max_pares)
    c.pares_candidatos, c.pares_evaluados, c.pares_fuera_por_limite = sel.candidatos, len(sel.evaluar), len(sel.fuera)
    c.fuera_por_limite = [ParFuera(par=p.clave, similitud=p.similitud, motivos=list(p.motivos)) for p in sel.fuera]
    c.avance = Avance(hechos=0, total=len(sel.evaluar))
    _guardar(srv, c)

    # 3. juez LLM por par
    juez = Juez(deps.llm_comparador)
    por_id = {r.req_id: r for r in requisitos}
    for par in sel.evaluar:
        relacion, hallazgo = _juzgar(juez, por_id[par.a], por_id[par.b], par)
        c.relaciones_por_par.append(relacion)
        c.pares_con_error += relacion.error is not None
        if hallazgo:
            _hallazgo(c.hallazgos, hallazgo)
        c.avance.hechos += 1
        _guardar(srv, c)
