"""Corrida de una evaluación contra un corpus (ADR 0014).

1. Se crea un proyecto `evaluacion` (su LEL empieza vacío) y los requisitos del
   corpus entran a la cola como un lote, con `origen.marca` = id del corpus.
2. Por cada requisito se encola la línea base en la prioridad de análisis: corre
   después de los grafos, con el mismo texto que recibió el sistema.
3. Un último trabajo cierra la evaluación. Las etiquetas para la calibración y el
   estado se recalculan al terminar cada trabajo y al consultar.
4. La cola vive en memoria: tras un reinicio, `recuperar` (al arrancar) o la primera
   consulta del informe vuelven a encolar la línea base que faltaba.

No hace falta validación humana: se evalúa lo que el sistema propone al llegar a
`pendiente_validacion` (o a un estado terminal). El ground truth se copia en el
documento al crearlo y nunca entra a un prompt.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from app.models import Origen, Traza, ahora

from . import metricas
from .agente_unico import PROMPT, EntradaLineaBase, ErrorLineaBase, linea_base
from .corpus import CorpusInvalido, CorpusNoEncontrado, cargar_corpus, conteo, nombres_de_corpus, resumen_corpus
from .emparejamiento import lematizador
from .modelos import COLECCION, PREFIJO, Etiqueta, Evaluacion, ItemEvaluacion

# El trabajador de la cola y las consultas leen y escriben el mismo documento
_candado = threading.RLock()


class SinAgenteUnico(RuntimeError):
    """No hay cliente LLM configurado para la línea base."""


def raiz_corpus(srv) -> Path:
    s = srv.deps.settings
    return s.ruta(s.corpus_dir)


def _guardar(srv, ev: Evaluacion) -> None:
    srv.repo.guardar_doc(COLECCION, ev.evaluacion_id, ev.model_dump(mode="json"))


def obtener(srv, evaluacion_id: str) -> Evaluacion | None:
    datos = srv.repo.obtener_doc(COLECCION, evaluacion_id)
    return Evaluacion.model_validate(datos) if datos else None


def _trazas(srv, ev: Evaluacion) -> dict[str, Traza]:
    return {t.req_id: t for t in srv.repo.trazas_completas(ev.proyecto_id)}


# ---------------------------------------------------------------- creación

def crear(srv, corpus: str, nombre: str | None = None) -> Evaluacion:
    """Crea el proyecto y el documento y encola los requisitos en el grafo (no la línea base).
    `CorpusNoEncontrado`, `CorpusInvalido` o `SinAgenteUnico` antes de crear nada."""
    c = cargar_corpus(raiz_corpus(srv), corpus)
    cliente = srv.deps.llm_agente_unico
    if cliente is None:
        raise SinAgenteUnico("no hay cliente LLM para la línea base de un solo agente (AGENTE_UNICO_MODEL)")
    nombre = nombre or f"Evaluación del corpus {c.nombre}"
    p = srv.proyectos.crear(nombre, f"Corrida de evaluación contra el corpus «{c.nombre}» ({len(c.items)} requisitos). "
                                    "Sin validación humana: se evalúa lo que propone el sistema.", tipo="evaluacion")
    _, req_ids = srv.solicitar_lote(
        [(it.texto, Origen(archivo=f"corpus:{c.nombre}", marca=it.id, indice=i)) for i, it in enumerate(c.items, 1)],
        p.proyecto_id)
    config = {**srv.deps.config_traza(), "agente_unico": {"modelo": cliente.modelo, "prompt_version": PROMPT}}
    datos = srv.repo.crear_doc(COLECCION, PREFIJO, lambda eid: Evaluacion(
        evaluacion_id=eid, nombre=nombre, proyecto_id=p.proyecto_id, corpus=c.nombre, ejemplo=c.ejemplo,
        huella=c.huella, config=config, ground_truth=[it.ground_truth for it in c.items],
        items=[ItemEvaluacion(id_corpus=it.id, req_id=r) for it, r in zip(c.items, req_ids)],
    ).model_dump(mode="json"))
    return Evaluacion.model_validate(datos)


def encolar(srv, ev: Evaluacion) -> None:
    """Línea base de cada requisito que aún no la tiene y el cierre, en la prioridad de análisis."""
    for it in ev.items:
        if it.id_corpus not in ev.linea_base:
            srv.cola.encolar("analisis", f"{ev.evaluacion_id}:{it.id_corpus}",
                             lambda ic=it.id_corpus: correr_linea_base(srv, ev.evaluacion_id, ic))
    srv.cola.encolar("analisis", ev.evaluacion_id, lambda: sincronizar(srv, ev.evaluacion_id))


def solicitar(srv, corpus: str, nombre: str | None = None) -> Evaluacion:
    """Crear y encolar (API)."""
    ev = crear(srv, corpus, nombre)
    encolar(srv, ev)
    return ev


def recuperar(srv) -> list[str]:
    """Tras un reinicio, vuelve a encolar la línea base que faltaba y el cierre de las
    evaluaciones sin terminar (los grafos los retoma `Servicio.recuperar`). Llamar una
    sola vez, al arrancar el servicio."""
    ids = []
    for d in srv.repo.listar_docs(COLECCION):
        if d.get("estado") != "terminada":
            ev = Evaluacion.model_validate(d)
            encolar(srv, ev)
            ids.append(ev.evaluacion_id)
    return ids


def _en_cola(srv, evaluacion_id: str) -> bool:
    """Algún trabajo de la evaluación espera o corre en la cola de este proceso."""
    estado = srv.cola.estado()
    trabajos = [*estado["pendientes"], *([estado["en_proceso"]] if estado["en_proceso"] else [])]
    return any(t["clave"] == evaluacion_id or t["clave"].startswith(f"{evaluacion_id}:") for t in trabajos)


def reanudar_si_falta(srv, ev: Evaluacion) -> bool:
    """La cola vive en memoria: si el proceso se reinició, la línea base pendiente se perdió.
    Si falta alguna y ningún trabajo de la evaluación está en la cola, la vuelve a encolar.
    Un duplicado no repite llamadas: `correr_linea_base` se salta lo que ya tiene resultado."""
    if ev.estado == "terminada" or all(it.id_corpus in ev.linea_base for it in ev.items):
        return False
    if _en_cola(srv, ev.evaluacion_id):
        return False
    encolar(srv, ev)
    return True


# ---------------------------------------------------------------- trabajos

def sincronizar(srv, evaluacion_id: str, cambio: Callable[[Evaluacion], None] | None = None
                ) -> tuple[Evaluacion, dict[str, Traza]] | None:
    """Aplica `cambio` al documento y recalcula etiquetas y estado con las trazas actuales,
    todo bajo el candado; guarda solo si algo cambió. Una evaluación terminada no vuelve atrás."""
    with _candado:
        ev = obtener(srv, evaluacion_id)
        if ev is None:
            return None
        antes = ev.model_dump(mode="json")
        if cambio:
            cambio(ev)
        trazas = _trazas(srv, ev)
        ev.etiquetas = [Etiqueta.model_validate(e)
                        for e in metricas.etiquetas(ev, trazas, lematizador(srv.deps.analizador))]
        if ev.estado != "terminada" and metricas.completa(ev, trazas):
            ev.estado, ev.terminado = "terminada", ahora()
        if ev.model_dump(mode="json") != antes:
            _guardar(srv, ev)
        return ev, trazas


def correr_linea_base(srv, evaluacion_id: str, id_corpus: str) -> None:
    """Una llamada del agente único sobre el texto que recibió el sistema. La llamada va fuera
    del candado; el resultado (o la falla) se guarda dentro."""
    ev = obtener(srv, evaluacion_id)
    if ev is None or id_corpus in ev.linea_base:
        return
    item = next(it for it in ev.items if it.id_corpus == id_corpus)
    traza = srv.traza(item.req_id)
    if traza is None:  # sin texto no hay llamada; queda registrado para que la evaluación pueda cerrar
        entrada = EntradaLineaBase(error=ErrorLineaBase(excepcion="TrazaNoEncontrada",
                                                        mensaje=f"no existe la traza {item.req_id}"))
    else:
        entrada = linea_base(srv.deps.llm_agente_unico, srv.deps.settings.significado_max_palabras, traza.texto)

    def guardar(e: Evaluacion) -> None:
        e.linea_base[id_corpus] = entrada

    sincronizar(srv, evaluacion_id, guardar)


# ---------------------------------------------------------------- consultas

def informe(srv, evaluacion_id: str) -> dict | None:
    """Métricas calculadas al vuelo (forma `formas.InformeEvaluacion`). Si la evaluación quedó
    a medias por un reinicio, vuelve a encolar lo que falta (`reanudar_si_falta`)."""
    sinc = sincronizar(srv, evaluacion_id)
    if sinc is None:
        return None
    ev, trazas = sinc
    reanudar_si_falta(srv, ev)
    try:
        actual = cargar_corpus(raiz_corpus(srv), ev.corpus).huella
    except (CorpusNoEncontrado, CorpusInvalido):
        actual = None
    analizador = srv.deps.analizador
    return metricas.informe(ev, trazas, lematizador(analizador), huella_actual=actual, con_lemas=analizador is not None)


def listar(srv) -> list[dict]:
    """Resúmenes (forma `formas.ResumenEvaluacion`), la más reciente primero."""
    salida = []
    for d in reversed(srv.repo.listar_docs(COLECCION)):
        ev = Evaluacion.model_validate(d)
        estados = {t["req_id"]: t["estado"] for t in srv.repo.listar_trazas(ev.proyecto_id)}
        salida.append({"evaluacion_id": ev.evaluacion_id, "nombre": ev.nombre, "proyecto_id": ev.proyecto_id,
                       "corpus": ev.corpus, "ejemplo": ev.ejemplo, "creado": ev.creado, "terminado": ev.terminado,
                       "estado": ev.estado, "progreso": metricas.progreso(ev, estados)})
    return salida


def listar_corpus(srv) -> list[dict]:
    raiz = raiz_corpus(srv)
    return [resumen_corpus(raiz, n) for n in nombres_de_corpus(raiz)]


def detalle_corpus(srv, nombre: str) -> dict:
    """Forma `formas.DetalleCorpus`. `CorpusNoEncontrado` o `CorpusInvalido`."""
    c = cargar_corpus(raiz_corpus(srv), nombre)
    return {"nombre": c.nombre, "descripcion": c.descripcion, "ejemplo": c.ejemplo, "autoria": c.autoria,
            "validado_por": c.validado_por, "huella": c.huella, "avisos": c.avisos, "conteo": conteo(c.items),
            "items": [it.model_dump(mode="json") for it in c.items]}
