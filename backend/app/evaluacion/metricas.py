"""Métricas de la evaluación contra el ground truth (ADR 0014).

Funciones puras: reciben las trazas, el ground truth guardado y la línea base, y
no escriben nada. Se comparan dos lados con las mismas reglas:

- **sistema**: lo que propone el grafo al llegar a `pendiente_validacion` (o a un
  estado terminal), sin validación humana;
- **línea base**: un solo agente, una llamada, sin debate.

Detección por término (`deteccion`): lo esperado es todo lo que el ground truth
marca (términos ambiguos, vaguedad y regionales, sin repetir). Un término del
sistema cuenta como detectado si tuvo interpretaciones, o si los filtros lo
marcaron como vaguedad o regional y el ground truth lo lista así. Un término de la
línea base cuenta si lo devolvió. `deteccion_ambiguedad` repite la cuenta solo con
términos ambiguos (el núcleo): ahí la línea base no queda en desventaja por no
tener catálogos.
"""
from __future__ import annotations

from collections import Counter

from app.models import Estado, TipoAmbiguedad, TipoMensaje, Traza, Via
from app.nlp import normalizar

from .agente_unico import EntradaLineaBase
from .corpus import RequisitoGT
from .emparejamiento import Lematizador, criterio, emparejar, palabras
from .modelos import Evaluacion

DECIMALES = 6
LISTOS = {Estado.PENDIENTE_VALIDACION, Estado.VALIDADO, Estado.RECHAZADO, Estado.FORMALIZADO, Estado.ERROR}
VIAS = (Via.ACEPTADO_DIRECTO.value, Via.CONSENSO.value, Via.ARBITRAJE.value)

NOTA = ("Resultados exploratorios: con un corpus de 15 a 25 requisitos, un solo caso mueve las proporciones varios "
        "puntos. Se evalúa lo que el sistema propone antes de la validación humana. `deteccion` cuenta todo lo que el "
        "ground truth marca (ambigüedad, vaguedad y regionales) y favorece al sistema, que tiene catálogos; "
        "`deteccion_ambiguedad` cuenta solo términos ambiguos y es la comparación del núcleo. Un debate faltante puede "
        "ser una ambigüedad inocua (interpretaciones cercanas): el ground truth no distingue nociva de inocua. La "
        "interpretación elegida no se califica automáticamente: se muestra junto a la esperada para revisarla a mano.")


def proporcion(a: int, b: int) -> float | None:
    return round(a / b, DECIMALES) if b else None


def deteccion(vp: int, fp: int, fn: int) -> dict:
    """Precisión, exhaustividad y F1; `null` cuando el denominador es cero."""
    precision, exhaustividad = proporcion(vp, vp + fp), proporcion(vp, vp + fn)
    f1 = None if precision is None or exhaustividad is None else proporcion(2 * vp, 2 * vp + fp + fn)
    return {"vp": vp, "fp": fp, "fn": fn, "precision": precision, "exhaustividad": exhaustividad, "f1": f1}


def esperados(gt: RequisitoGT) -> list[dict]:
    """Lo que el ground truth marca en un requisito, sin repetir: un regional que además
    es ambiguo cuenta una vez, como ambigüedad."""
    salida = [{"termino": t.termino, "clase": "ambiguedad", "tipo_ambiguedad": t.tipo_ambiguedad.value}
              for t in gt.terminos]
    for clase, lista in (("vaguedad", gt.vaguedad), ("regional", gt.regionales)):
        for x in lista:
            if all(palabras(x) != palabras(e["termino"]) for e in salida):
                salida.append({"termino": x, "clase": clase, "tipo_ambiguedad": None})
    return salida


# ---------------------------------------------------------------- lectura de la traza

def _ultimo(mensajes, tipo: TipoMensaje):
    return next((m for m in reversed(mensajes) if m.tipo == tipo), None)


def lectura_sistema(traza: Traza) -> dict:
    """Lo que el sistema propuso para un requisito, leído de su traza::

        {estado, listo, error, ambiguo, debate, resueltos_por_lel: [str],
         terminos: [{termino, origen, clasificado, con_interpretaciones, tipo_ambiguedad,
                     interpretacion, via, similitud}]}

    `origen` es la decisión de los filtros (candidato, regional, alcance, anafora,
    vaguedad). Cuenta la última clasificación y lo que vino después (un nodo
    reejecutado repite sus mensajes, ADR 0008). `ambiguo` es `null` si el
    requisito no llegó a clasificarse; `similitud` es la inicial (ronda 0).
    """
    mensajes = sorted(traza.mensajes, key=lambda m: m.secuencia)
    clasificacion = _ultimo(mensajes, TipoMensaje.INTERPRETACIONES)
    filtrado = _ultimo(mensajes, TipoMensaje.FILTRADO)
    posteriores = [m for m in mensajes if m.secuencia > (clasificacion.secuencia if clasificacion else 0)]
    solicitud = _ultimo(posteriores, TipoMensaje.SOLICITUD_VALIDACION)
    propuestas = {normalizar(t["termino"]): t.get("propuesta") for t in (solicitud.payload.get("terminos") or [])} \
        if solicitud else {}
    filtrados = (filtrado.payload.get("terminos") or []) if filtrado else []
    decision = {normalizar(t["termino"]): t.get("decision_filtro") for t in filtrados}

    similitud: dict[str, float | None] = {}
    via: dict[str, str] = {}
    for m in posteriores:
        p = m.payload or {}
        if not p.get("termino"):
            continue
        k = normalizar(p["termino"])
        if m.tipo == TipoMensaje.SIMILITUD and m.ronda == 0:
            similitud[k] = p.get("similitud")
            if p.get("decision") == Estado.ACEPTADO_DIRECTO.value:
                via[k] = Via.ACEPTADO_DIRECTO.value
        elif m.tipo == TipoMensaje.CONSENSO:
            via[k] = Via.CONSENSO.value
        elif m.tipo == TipoMensaje.ARBITRAJE:
            via[k] = Via.ARBITRAJE.value

    terminos, vistos = [], set()
    for r in (clasificacion.payload.get("resultados") or []) if clasificacion else []:
        k = normalizar(r["termino"])
        vistos.add(k)
        con = not r.get("univoco") and bool(r.get("interpretaciones"))
        propuesta = propuestas.get(k)
        terminos.append({
            "termino": r["termino"], "origen": decision.get(k) or "candidato", "clasificado": True,
            "con_interpretaciones": con,
            # Las trazas anteriores al tipo de ambigüedad se tratan como léxicas (ADR 0010 §5)
            "tipo_ambiguedad": (r.get("tipo_ambiguedad") or TipoAmbiguedad.LEXICA.value) if con else None,
            "interpretacion": propuesta.get("significado") if isinstance(propuesta, dict) else None,
            "via": via.get(k) if con else None, "similitud": similitud.get(k) if con else None})
    for f in filtrados:
        k = normalizar(f["termino"])
        if f.get("decision_filtro") in ("vaguedad", "regional") and k not in vistos:
            vistos.add(k)
            terminos.append({"termino": f["termino"], "origen": f["decision_filtro"], "clasificado": False,
                             "con_interpretaciones": False, "tipo_ambiguedad": None, "interpretacion": None,
                             "via": None, "similitud": None})

    error = None
    if traza.estado == Estado.ERROR:
        m = _ultimo(mensajes, TipoMensaje.ERROR)
        error = ((m.payload or {}).get("mensaje") if m else None) or "error sin mensaje"
    return {
        "estado": traza.estado.value,
        "listo": traza.estado in LISTOS,
        "error": error,
        "ambiguo": any(t["con_interpretaciones"] for t in terminos) if clasificacion else None,
        "debate": any(t.estado == Estado.EN_DEBATE for t in traza.transiciones),
        "resueltos_por_lel": [f["termino"] for f in filtrados if f.get("decision_filtro") == "resuelto_por_lel"],
        "terminos": terminos,
    }


# ---------------------------------------------------------------- un lado contra el ground truth

_CERO = {"vp": 0, "fp": 0, "fn": 0}


def _evaluar_terminos(terminos: list[dict], gt: RequisitoGT, lemas: Lematizador) -> dict:
    """Empareja los términos detectados con lo esperado. Un término con `tipo_ambiguedad`
    es uno que el lado declaró ambiguo: con esos se cuenta `deteccion_ambiguedad`."""
    esp = esperados(gt)
    detectados = [i for i, t in enumerate(terminos) if t["detectado"]]
    pares = emparejar([terminos[i]["termino"] for i in detectados], [e["termino"] for e in esp], lemas)
    salida = [{**t, "emparejado_con": None, "criterio": None, "clase_gt": None, "tipo_gt": None, "tipo_correcto": None}
              for t in terminos]
    for p in pares:
        t, e = salida[detectados[p.izquierda]], esp[p.derecha]
        t.update(emparejado_con=e["termino"], criterio=p.criterio, clase_gt=e["clase"], tipo_gt=e["tipo_ambiguedad"])
        if e["clase"] == "ambiguedad" and t["tipo_ambiguedad"]:
            t["tipo_correcto"] = t["tipo_ambiguedad"] == e["tipo_ambiguedad"]
    usados = {p.derecha for p in pares}

    ambiguos = [t["termino"] for t in terminos if t["tipo_ambiguedad"]]
    pares_amb = emparejar(ambiguos, [t.termino for t in gt.terminos], lemas)
    return {
        "terminos": salida,
        "faltantes": [e["termino"] for j, e in enumerate(esp) if j not in usados],
        "deteccion": {"vp": len(pares), "fp": len(detectados) - len(pares), "fn": len(esp) - len(pares)},
        "deteccion_ambiguedad": {"vp": len(pares_amb), "fp": len(ambiguos) - len(pares_amb),
                                 "fn": len(gt.terminos) - len(pares_amb)},
    }


def _listado(termino: str, lista: list[str], lemas: Lematizador) -> bool:
    return any(criterio(termino, x, lemas) for x in lista)


def _debate_gt(debate: bool, ambiguo: bool) -> str:
    if debate:
        return "justificado" if ambiguo else "de_mas"
    return "faltante" if ambiguo else "sin_debate_correcto"


def lado_sistema(lectura: dict | None, gt: RequisitoGT, lemas: Lematizador) -> dict:
    """Forma `formas.LadoSistema`."""
    if lectura is None or not lectura["listo"]:
        return {"listo": False, "estado": lectura["estado"] if lectura else None, "error": None, "ambiguo": None,
                "correcto": None, "debate": bool(lectura and lectura["debate"]), "debate_gt": None, "terminos": [],
                "faltantes": [], "deteccion": dict(_CERO), "deteccion_ambiguedad": dict(_CERO)}
    terminos = []
    for t in lectura["terminos"]:
        motivo = None
        if t["con_interpretaciones"]:
            motivo = "interpretaciones"
        elif t["origen"] == "vaguedad" and _listado(t["termino"], gt.vaguedad, lemas):
            motivo = "vaguedad"
        elif t["origen"] == "regional" and _listado(t["termino"], gt.regionales, lemas):
            motivo = "regional"
        terminos.append({"termino": t["termino"], "origen": t["origen"], "detectado": motivo is not None,
                         "motivo_deteccion": motivo, "tipo_ambiguedad": t["tipo_ambiguedad"],
                         "interpretacion": t["interpretacion"], "via": t["via"], "similitud": t["similitud"]})
    ambiguo = lectura["ambiguo"]
    return {"listo": True, "estado": lectura["estado"], "error": lectura["error"], "ambiguo": ambiguo,
            "correcto": None if ambiguo is None else ambiguo == gt.ambiguo, "debate": lectura["debate"],
            "debate_gt": _debate_gt(lectura["debate"], gt.ambiguo), **_evaluar_terminos(terminos, gt, lemas)}


def lado_linea_base(entrada: EntradaLineaBase | None, gt: RequisitoGT, lemas: Lematizador) -> dict:
    """Forma `formas.LadoLineaBase`. Una falla cuenta como «sin decisión» y sin términos detectados."""
    if entrada is None:
        return {"listo": False, "error": None, "ambiguo": None, "correcto": None, "terminos": [], "faltantes": [],
                "deteccion": dict(_CERO), "deteccion_ambiguedad": dict(_CERO), "modelo": None, "prompt_version": None}
    r = entrada.resultado
    terminos = [{"termino": t.termino, "origen": "agente_unico", "detectado": True, "motivo_deteccion": "agente_unico",
                 "tipo_ambiguedad": t.tipo_ambiguedad.value, "interpretacion": t.interpretacion_elegida,
                 "via": None, "similitud": None} for t in (r.terminos if r else [])]
    ambiguo = r.ambiguo if r else None
    return {"listo": True, "error": entrada.error.mensaje if entrada.error else None, "ambiguo": ambiguo,
            "correcto": None if ambiguo is None else ambiguo == gt.ambiguo, **_evaluar_terminos(terminos, gt, lemas),
            "modelo": entrada.modelo, "prompt_version": entrada.prompt_version}


# ---------------------------------------------------------------- resúmenes

def _suma(lados: list[dict], clave: str) -> dict:
    return {k: sum(l[clave][k] for l in lados) for k in ("vp", "fp", "fn")}


def resumen_lado(filas: list[tuple[dict, RequisitoGT]]) -> dict:
    """Forma `formas.ResumenLineaBase`, sobre los requisitos listos de ese lado."""
    listos = [(l, g) for l, g in filas if l["listo"]]
    lados = [l for l, _ in listos]
    vp = sum(l["ambiguo"] is True and g.ambiguo for l, g in listos)
    fp = sum(l["ambiguo"] is True and not g.ambiguo for l, g in listos)
    vn = sum(l["ambiguo"] is False and not g.ambiguo for l, g in listos)
    fn = sum(l["ambiguo"] is False and g.ambiguo for l, g in listos)
    tipos = [t["tipo_correcto"] for l in lados for t in l["terminos"] if t["tipo_correcto"] is not None]
    return {
        "n": len(listos),
        "errores": sum(l["error"] is not None for l in lados),
        "deteccion": deteccion(**_suma(lados, "deteccion")),
        "deteccion_ambiguedad": deteccion(**_suma(lados, "deteccion_ambiguedad")),
        "requisito": {"vp": vp, "fp": fp, "vn": vn, "fn": fn, "sin_decision": sum(l["ambiguo"] is None for l in lados),
                      "exactitud": proporcion(vp + vn, len(listos))},
        "tipo": {"n": len(tipos), "aciertos": sum(tipos), "exactitud": proporcion(sum(tipos), len(tipos))},
    }


def resumen_sistema(filas: list[tuple[dict, RequisitoGT]]) -> dict:
    """Forma `formas.ResumenSistema`: lo de la línea base más debates y vías.

    Debates por requisito (`en_debate` contra `ambiguo` del ground truth):
    activados = justificados + de_mas; necesarios = justificados + faltantes."""
    listos = [(l, g) for l, g in filas if l["listo"]]
    vias = Counter(t["via"] or "sin_via" for l, _ in listos for t in l["terminos"]
                   if t["motivo_deteccion"] == "interpretaciones")
    return {
        **resumen_lado(filas),
        "debates": {
            "activados": sum(l["debate"] for l, _ in listos),
            "necesarios": sum(g.ambiguo for _, g in listos),
            "justificados": sum(l["debate"] and g.ambiguo for l, g in listos),
            "de_mas": sum(l["debate"] and not g.ambiguo for l, g in listos),
            "faltantes": sum(not l["debate"] and g.ambiguo for l, g in listos),
        },
        "vias": {v: vias.get(v, 0) for v in (*VIAS, "sin_via")},
    }


# ---------------------------------------------------------------- etiquetas para la calibración

def etiquetas_de(req_id: str, lectura: dict, gt: RequisitoGT, lemas: Lematizador) -> list[dict]:
    """Contrato con la calibración (ADR 0013): una etiqueta por candidato del Clasificador y
    otra por término ambiguo del ground truth que no se emparejó con ninguno.

    El candidato lleva el término como lo escribió el sistema (así la calibración lo
    encuentra entre sus similitudes) y es ambiguo si se emparejó con un término
    ambiguo del ground truth, con el tipo del ground truth."""
    candidatos = [t["termino"] for t in lectura["terminos"] if t["clasificado"]]
    pares = {p.izquierda: p.derecha for p in emparejar(candidatos, [t.termino for t in gt.terminos], lemas)}
    salida = [{"req_id": req_id, "termino": c, "ambiguo": i in pares,
               "tipo_ambiguedad": gt.terminos[pares[i]].tipo_ambiguedad.value if i in pares else None}
              for i, c in enumerate(candidatos)]
    usados = set(pares.values())
    salida += [{"req_id": req_id, "termino": t.termino, "ambiguo": True, "tipo_ambiguedad": t.tipo_ambiguedad.value}
               for j, t in enumerate(gt.terminos) if j not in usados]
    return salida


def etiquetas(ev: Evaluacion, trazas: dict[str, Traza], lemas: Lematizador) -> list[dict]:
    """Etiquetas de los requisitos que el sistema ya terminó (los demás aún no tienen candidatos)."""
    gt = {g.id: g for g in ev.ground_truth}
    salida = []
    for it in ev.items:
        t = trazas.get(it.req_id)
        if t is not None and t.estado in LISTOS:
            salida += etiquetas_de(it.req_id, lectura_sistema(t), gt[it.id_corpus], lemas)
    return salida


def completa(ev: Evaluacion, trazas: dict[str, Traza]) -> bool:
    return all((t := trazas.get(it.req_id)) is not None and t.estado in LISTOS and it.id_corpus in ev.linea_base
               for it in ev.items)


# ---------------------------------------------------------------- informe

def progreso(ev: Evaluacion, estados: dict[str, Estado]) -> dict:
    return {"total": len(ev.items),
            "listos_sistema": sum(estados.get(it.req_id) in LISTOS for it in ev.items),
            "listos_linea_base": sum(it.id_corpus in ev.linea_base for it in ev.items)}


def _avisos(ev: Evaluacion, prog: dict, filas: list[dict], lecturas: dict[str, dict], faltan_trazas: list[str], *,
            huella_actual: str | None, con_lemas: bool) -> list[str]:
    avisos = []
    if ev.ejemplo:
        avisos.append("corpus de EJEMPLO: muestra el formato, no es el corpus de la tesis; sus resultados no se reportan")
    if prog["listos_sistema"] < prog["total"] or prog["listos_linea_base"] < prog["total"]:
        avisos.append(f"evaluación incompleta: sistema {prog['listos_sistema']}/{prog['total']}, línea base "
                      f"{prog['listos_linea_base']}/{prog['total']}; cada resumen cubre solo los requisitos listos de "
                      "su lado")
    if faltan_trazas:
        avisos.append(f"no se encontraron las trazas {', '.join(faltan_trazas)}: esos requisitos no cuentan")
    if huella_actual is None:
        avisos.append(f"el corpus «{ev.corpus}» ya no está en disco o no es válido; las métricas usan el ground truth "
                      "guardado al crear la evaluación")
    elif huella_actual != ev.huella:
        avisos.append(f"el corpus «{ev.corpus}» cambió desde que se creó la evaluación; las métricas usan el ground "
                      "truth guardado al crearla. Para medir contra el nuevo, crea otra evaluación")
    con_lel = [req_id for req_id, lect in lecturas.items() if lect["resueltos_por_lel"]]
    if con_lel:
        avisos.append(f"hubo términos resueltos por el LEL del proyecto de evaluación en {', '.join(con_lel)}: alguien "
                      "validó requisitos durante la corrida y la memoria afectó a los siguientes")
    for lado, nombre in (("sistema", "del sistema"), ("linea_base", "de la línea base")):
        errores = [f["id_corpus"] for f in filas if f[lado]["error"] is not None]
        if errores:
            avisos.append(f"{len(errores)} requisito(s) {nombre} terminaron en error ({', '.join(errores)}): cuentan "
                          "como «sin decisión» y sus términos como no detectados")
    if not con_lemas:
        avisos.append("sin analizador de spaCy: el emparejamiento por lema está desactivado")
    return avisos


def informe(ev: Evaluacion, trazas: dict[str, Traza], lemas: Lematizador, *, huella_actual: str | None,
            con_lemas: bool = True) -> dict:
    """Forma `formas.InformeEvaluacion`. `huella_actual` es la del corpus en disco (`None`
    si ya no existe o no es válido)."""
    gt_por_id = {g.id: g for g in ev.ground_truth}
    filas, lecturas, faltan = [], {}, []
    for it in ev.items:
        gt = gt_por_id[it.id_corpus]
        t = trazas.get(it.req_id)
        if t is None:
            faltan.append(it.req_id)
        lectura = lectura_sistema(t) if t is not None else None
        if lectura is not None:
            lecturas[it.req_id] = lectura
        filas.append({"id_corpus": it.id_corpus, "req_id": it.req_id, "texto": t.texto if t is not None else None,
                      "ground_truth": gt.model_dump(mode="json"), "sistema": lado_sistema(lectura, gt, lemas),
                      "linea_base": lado_linea_base(ev.linea_base.get(it.id_corpus), gt, lemas)})
    gts = [gt_por_id[it.id_corpus] for it in ev.items]
    prog = progreso(ev, {req_id: t.estado for req_id, t in trazas.items()})
    return {
        "evaluacion_id": ev.evaluacion_id, "nombre": ev.nombre, "proyecto_id": ev.proyecto_id, "corpus": ev.corpus,
        "ejemplo": ev.ejemplo, "creado": ev.creado, "terminado": ev.terminado, "estado": ev.estado,
        "config": ev.config, "progreso": prog,
        "resumen": {"sistema": resumen_sistema([(f["sistema"], g) for f, g in zip(filas, gts)]),
                    "linea_base": resumen_lado([(f["linea_base"], g) for f, g in zip(filas, gts)])},
        "requisitos": filas,
        "etiquetas": [e.model_dump(mode="json") for e in ev.etiquetas],
        "avisos": _avisos(ev, prog, filas, lecturas, faltan, huella_actual=huella_actual, con_lemas=con_lemas),
        "nota": NOTA,
    }
