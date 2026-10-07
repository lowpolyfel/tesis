"""Vista por término de un requisito, sobre trazas producidas por el grafo real
(LLM y embeddings falsos): caminos completos, trazas en proceso, en error,
anteriores al tipo de ambigüedad y con mensajes repetidos tras un reinicio."""
import pytest

from app.analisis import (
    formas,
    mensajes_efectivos,
    normalizar_config,
    resumen_requisito,
    vista_requisito,
)
from app.models import Estado, Interpretacion, Validacion
from tests.analisis.caminos import (
    APROBAR,
    I2_CERCANA,
    JUSTIFICACION,
    T1,
    insertar,
    montar_dos_terminos,
    termino,
    vista,
)
from tests.escenarios import (
    EXTRACCION_SESION,
    I1,
    I2,
    MODELADO,
    P1_CERCANA,
    SESION,
    clasificacion,
    montar,
)
from tests.fakes import interp, r3_todas

INTERP_I2_REFINADA = interp("I2", "periodo de uso", P1_CERCANA)


def _sin_estado(interps):
    return [{k: i[k] for k in ("id", "significado", "parafrasis_del_requisito")} for i in interps]


# ---------------------------------------------------------------- caminos completos

def test_aceptado_directo_pendiente_y_luego_formalizado(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2_CERCANA)],
        "modelador_v1": [MODELADO]})
    req = srv.procesar(SESION)
    v = vista(srv, req)
    assert (v["req_id"], v["proyecto_id"], v["ciclo"], v["texto"], v["origen"]) == (req, "P00", 1, SESION, None)
    assert (v["estado"], v["en_proceso"], v["terminal"]) == ("pendiente_validacion", False, False)
    assert v["solicitud"]["terminos"][0]["termino"] == "sesión" and v["validacion"] is None
    assert v["formalizacion"] is None and v["errores"] == []

    # configuración normalizada desde la traza
    assert v["config"] == {
        "umbral": 0.75, "max_rondas": 2,
        "modelos": {"extractor": "qwen2.5:7b", "clasificador": "qwen2.5:7b", "critico": "ollama:qwen2.5:7b",
                    "modelador": "qwen2.5:7b"},
        "modelo_embeddings": "nomic-embed-text", "temperatura": 0.0, "semilla": 42, "significado_max_palabras": 12,
        "spacy_model": "es_core_news_sm", "catalogos": {"regionales": "v1-semilla", "vaguedad": "v1-semilla"},
        "persistencia": repo.descripcion, "otros": {}}

    # marcados: tramo exacto del texto y tipo según el Clasificador
    assert [(m["texto"], m["decision_filtro"], m["tipo"], m["univoco"]) for m in v["marcados"]] == [
        ("sistema", "candidato", None, True), ("registrar", "candidato", None, True),
        ("sesión", "candidato", "lexica", False)]
    assert all(SESION[m["inicio"]:m["fin"]] == m["texto"] for m in v["marcados"])

    t = srv.traza(req)
    ext = v["extraccion"]
    assert [x["termino"] for x in ext["terminos"]] == ["sistema", "registrar", "sesión"]
    assert (ext["modelo"], ext["prompt_version"], ext["intentos"], ext["descartados"]) == ("llm-falso", "extractor_v1", 1, [])
    esperado = round((t.mensajes[0].timestamp - t.transiciones[0].timestamp).total_seconds() * 1000)
    assert ext["duracion_ms"] == esperado >= 0

    s = termino(v, "sesión")
    assert (s["origen"], s["categoria"], s["univoco"], s["tipo_ambiguedad"]) == ("extractor", "objeto", False, "lexica")
    assert [(i["id"], i["estado"], i["retirada_en_ronda"]) for i in s["interpretaciones"]] == [
        ("I1", "vigente", None), ("I2", "vigente", None)]
    d = s["divergencia_inicial"]
    assert d["decision"] == "aceptado_directo" and d["similitud"] >= 0.75 and d["umbral"] == 0.75
    assert d["par_minimo"] == ["I1", "I2"] and set(d["pares"]) == {"I1-I2"} and d["modelo_embeddings"] == "embeddings-falsos"
    assert s["rondas"] == []
    assert s["resolucion"] == {"via": "aceptado_directo", "decision": "aceptado_directo", "propuesta": I1,
                               "motivo": "umbral", "similitud_final": d["similitud"], "arbitraje": None}
    assert s["validacion"] is None and s["entrada_lel"] is None
    assert [(x["termino"], x["univoco"], x["interpretaciones"]) for x in v["terminos"][:2]] == [
        ("sistema", True, []), ("registrar", True, [])]
    assert v["resumen"] == {"n_terminos": 3, "n_ambiguos": 1, "tipos": {"lexica": 1, "alcance": 0, "anaforica": 0,
                                                                          "sintactica": 0},
                            "vaguedad": [], "regionales": [], "resueltos_por_lel": [], "estructuras": 0,
                            "similitud_minima": d["similitud"], "via": "aceptado_directo", "rondas_max": 0,
                            "n_errores": 0}

    srv.validar(req, APROBAR)
    v = vista(srv, req)
    assert (v["estado"], v["en_proceso"], v["terminal"]) == ("formalizado", False, True)
    assert [x["estado"] for x in v["transiciones"]] == ["cargado", "extraido", "interpretado", "aceptado_directo",
                                                        "pendiente_validacion", "validado", "formalizado"]
    s = termino(v, "sesión")
    assert s["validacion"] == {"final": I1, "cambio": "ninguno"}
    assert s["entrada_lel"]["simbolo"] == "sesión" and s["entrada_lel"]["via"] == "aceptado_directo"
    assert v["validacion"]["decision"] == "aprobar" and v["validacion"]["timestamp"]
    assert v["formalizacion"] == repo.obtener_doc("formalizados", req)
    assert v["formalizacion"]["entradas_lel"] == ["sesión"]
    assert v["n_mensajes"] == v["ultima_secuencia"] == len(srv.traza(req).mensajes) and v["n_repetidos"] == 0
    # sin el documento de `formalizados`, sale del mensaje con alcance requisito
    sin_doc = vista_requisito(srv.traza(req))
    assert sin_doc["formalizacion"]["alcance"] == "requisito" and sin_doc["formalizacion"]["entradas_lel"] == ["sesión"]


def test_consenso_por_retiro_en_la_ronda_1(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [{"interpretaciones": [I1],
                                          "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega servidor"}]}],
        "modelador_v1": [MODELADO]})
    req = srv.procesar(SESION)
    s = termino(vista(srv, req), "sesión")
    assert s["divergencia_inicial"]["decision"] == "en_debate" and s["divergencia_inicial"]["similitud"] == 0.0
    assert [(i["id"], i["estado"], i["retirada_en_ronda"], i["motivo_retiro"]) for i in s["interpretaciones"]] == [
        ("I1", "vigente", None, None), ("I2", "retirada", 1, "agrega servidor")]
    (r1,) = s["rondas"]
    assert r1["ronda"] == 1 and _sin_estado(r1["evaluadas"]) == [I1, I2]
    assert [e["interpretacion_id"] for e in r1["evaluaciones"]] == ["I1", "I2"]
    assert all({"reglas", "r1_estricta", "r2_estricta"} <= set(e) for e in r1["evaluaciones"])
    assert [(o["interpretacion_id"], o["regla"]) for o in r1["objeciones"]] == [("I1", "R3"), ("I2", "R3")]
    assert r1["refinamiento"] == {"interpretaciones": [I1], "nota": None,
                                  "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega servidor"}]}
    assert r1["similitud"] is None  # con una sola interpretación no hay nada que comparar
    assert r1["consenso"] == {"motivo": "una_interpretacion", "similitud": None, "umbral": 0.75, "propuesta": "I1"}
    assert s["resolucion"] == {"via": "consenso", "decision": "consenso", "propuesta": I1, "motivo": "una_interpretacion",
                               "similitud_final": None, "arbitraje": None}
    v = vista(srv, req)
    assert v["resumen"]["via"] == "consenso" and v["resumen"]["rondas_max"] == 1 and v["resumen"]["similitud_minima"] == 0.0


def test_consenso_por_umbral_muestra_la_ultima_version_de_cada_interpretacion(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [{"interpretaciones": [I1, INTERP_I2_REFINADA]}]})
    s = termino(vista(srv, srv.procesar(SESION)), "sesión")
    assert _sin_estado(s["interpretaciones"]) == [I1, INTERP_I2_REFINADA]
    assert all(i["estado"] == "vigente" for i in s["interpretaciones"])
    (r1,) = s["rondas"]
    assert _sin_estado(r1["evaluadas"]) == [I1, I2]  # lo que el Crítico evaluó, antes de refinar
    assert r1["similitud"]["decision"] == "consenso" and r1["similitud"]["similitud"] >= 0.75
    assert r1["consenso"]["motivo"] == "umbral"
    assert s["resolucion"]["motivo"] == "umbral" and s["resolucion"]["similitud_final"] == r1["similitud"]["similitud"]


def test_arbitraje_tras_dos_rondas_y_eleccion_humana(tmp_path, analizador):
    sin_cambios = {"interpretaciones": [I1, I2]}
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False), "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v1": [{"interpretacion_elegida": "I2", "justificacion_por_regla": JUSTIFICACION}],
        "modelador_v1": [MODELADO]})
    req = srv.procesar(SESION)
    s = termino(vista(srv, req), "sesión")
    assert [r["ronda"] for r in s["rondas"]] == [1, 2]
    assert [r["similitud"]["decision"] for r in s["rondas"]] == ["en_debate", "en_debate"]
    assert all(r["consenso"] is None for r in s["rondas"])
    assert s["resolucion"] == {"via": "arbitraje", "decision": "arbitrado", "propuesta": I2, "motivo": "rondas_agotadas",
                               "similitud_final": 0.0,
                               "arbitraje": {"interpretacion_elegida": "I2", "justificacion_por_regla": JUSTIFICACION}}
    assert vista(srv, req)["resumen"]["via"] == "arbitraje" and vista(srv, req)["resumen"]["rondas_max"] == 2

    srv.validar(req, Validacion(decision="aprobar", interpretaciones_editadas={"sesión": Interpretacion(**I1)}))
    s = termino(vista(srv, req), "sesión")
    assert s["validacion"] == {"final": I1, "cambio": "eleccion"}
    assert s["entrada_lel"]["interpretacion"]["id"] == "I1" and s["entrada_lel"]["via"] == "arbitraje"


def test_edicion_humana_queda_en_la_vista_del_termino(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2_CERCANA)],
        "modelador_v1": [MODELADO]})
    req = srv.procesar(SESION)
    editada = interp("I1", "periodo autenticado", "Otra paráfrasis.")
    srv.validar(req, Validacion(decision="aprobar", interpretaciones_editadas={"sesión": Interpretacion(**editada)}))
    s = termino(vista(srv, req), "sesión")
    assert s["validacion"] == {"final": editada, "cambio": "edicion"}
    assert s["resolucion"]["propuesta"] == I1 and s["entrada_lel"]["editada_por_humano"] is True


def test_vaguedad_sin_interpretaciones(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [{"terminos": [{"termino": "sistema", "categoria_tentativa": "sujeto"},
                                       {"termino": "responder", "categoria_tentativa": "verbo"},
                                       {"termino": "ahorita", "categoria_tentativa": "estado"}]}],
        "clasificador_v2": [{"resultados": [{"termino": "sistema", "univoco": True},
                                            {"termino": "responder", "univoco": True}]}]})
    v = vista(srv, srv.procesar("El sistema debe responder ahorita."))
    ahorita = next(m for m in v["marcados"] if m["texto"] == "ahorita")
    assert (ahorita["decision_filtro"], ahorita["tipo"], ahorita["univoco"]) == ("vaguedad", "vaguedad", None)
    assert "vaguedad" in ahorita["detalle"]
    assert [t["termino"] for t in v["terminos"]] == ["sistema", "responder"]  # la vaguedad no pasa al Clasificador
    assert v["resumen"]["vaguedad"] == ["ahorita"] and v["resumen"]["n_ambiguos"] == 0
    assert v["resumen"]["via"] is None and v["resumen"]["similitud_minima"] is None and v["resumen"]["rondas_max"] == 0
    assert v["estado"] == "pendiente_validacion"


# ---------------------------------------------------------------- proyecto: regional, anáfora, LEL, rechazo, error

def test_regional_ambiguo_y_anafora(proyecto):
    srv, *_ = proyecto
    v = vista(srv, "R05")
    jalar = next(m for m in v["marcados"] if m["texto"] == "jalar")
    assert (jalar["decision_filtro"], jalar["tipo"], jalar["univoco"]) == ("regional", "lexica", False)
    j = termino(v, "jalar")
    assert j["origen"] == "regional" and "catálogo de regionales" in j["detalle"]
    assert j["resolucion"]["via"] == "arbitraje" and v["resumen"]["regionales"] == ["jalar"]

    v = vista(srv, "R06")
    cuenta = next(m for m in v["marcados"] if m["decision_filtro"] == "anafora")
    assert (cuenta["texto"], cuenta["tipo"]) == ("su cuenta", "anaforica")
    c = termino(v, "su cuenta")
    assert (c["origen"], c["tipo_ambiguedad"]) == ("anafora", "anaforica") and c["detalle"]
    assert v["resumen"]["estructuras"] == 1 and v["resumen"]["tipos"]["anaforica"] == 1


def test_regional_univoco_se_marca_como_regional(proyecto):
    srv, *_ = proyecto
    t = srv.traza("R05")
    m = next(m for m in t.mensajes if m.tipo == "interpretaciones")
    resultados = [{"termino": r["termino"], "univoco": True, "tipo_ambiguedad": None, "interpretaciones": []}
                  for r in m.payload["resultados"]]
    mensajes = [x.model_copy(update={"payload": {**x.payload, "resultados": resultados}}) if x is m else x
                for x in t.mensajes if x.secuencia <= m.secuencia]
    v = vista_requisito(t.model_copy(update={"mensajes": mensajes, "estado": Estado.INTERPRETADO}))
    jalar = next(x for x in v["marcados"] if x["texto"] == "jalar")
    assert (jalar["tipo"], jalar["univoco"]) == ("regional", True)


def test_termino_resuelto_por_el_lel(proyecto):
    srv, *_ = proyecto
    v = vista(srv, "R04")
    sesion = next(m for m in v["marcados"] if m["texto"] == "sesión")
    assert (sesion["decision_filtro"], sesion["tipo"], sesion["univoco"]) == ("resuelto_por_lel", "lel", None)
    assert v["resumen"]["resueltos_por_lel"] == ["sesión"] and v["resumen"]["n_ambiguos"] == 0
    assert "sesión" not in [t["termino"] for t in v["terminos"]]


def test_rechazo(proyecto):
    srv, *_ = proyecto
    v = vista(srv, "R03")
    assert (v["estado"], v["terminal"], v["en_proceso"]) == ("rechazado", True, False)
    assert v["validacion"]["decision"] == "rechazar" and v["validacion"]["comentario"] == "falta una métrica"
    assert v["formalizacion"] is None


def test_error_en_el_extractor(proyecto):
    srv, *_ = proyecto
    v = vista(srv, "R07")
    assert (v["estado"], v["terminal"], v["en_proceso"]) == ("error", True, False)
    assert v["marcados"] == [] and v["extraccion"] is None and v["terminos"] == []
    (e,) = v["errores"]
    assert (e["nodo"], e["excepcion"], e["prompt_version"]) == ("extraido", "FalloEstructurado", "extractor_v1")
    assert e["secuencia"] == 1 and "extractor_v1" in e["mensaje"]
    assert v["resumen"]["n_errores"] == 1 and v["resumen"]["n_terminos"] == 0


def test_error_a_mitad_del_debate(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2)],
        "critico_v1": ["no es json", "tampoco"]})
    v = vista(srv, srv.procesar(SESION))
    assert v["estado"] == "error" and [t["estado"] for t in v["transiciones"]][-2:] == ["en_debate", "error"]
    s = termino(v, "sesión")
    assert s["divergencia_inicial"]["decision"] == "en_debate" and s["rondas"] == [] and s["resolucion"] is None
    assert [(e["nodo"], e["prompt_version"]) for e in v["errores"]] == [("en_debate", "critico_v1")]
    assert v["resumen"]["via"] is None and v["resumen"]["n_errores"] == 1


# ---------------------------------------------------------------- trazas en proceso

def test_vista_en_vivo_durante_el_debate(tmp_path, analizador):
    """El guion del Crítico toma la vista en el momento en que se le consulta."""
    capturas, servicio = [], []
    critico = r3_todas(False)

    def critico_que_mira(prompt):
        capturas.append(vista(servicio[0], "R01"))
        return critico(prompt)

    sin_cambios = {"interpretaciones": [I1, I2]}
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2)],
        "critico_v1": critico_que_mira, "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v1": [{"interpretacion_elegida": "I1", "justificacion_por_regla": JUSTIFICACION}]})
    servicio.append(srv)
    srv.procesar(SESION)

    r1, r2 = capturas
    for v in capturas:
        assert (v["estado"], v["en_proceso"], v["terminal"]) == ("en_debate", True, False)
        assert v["solicitud"] is None and v["resumen"]["via"] is None
        assert termino(v, "sesión")["resolucion"] is None
    assert termino(r1, "sesión")["rondas"] == []
    (ronda,) = termino(r2, "sesión")["rondas"]
    assert ronda["similitud"]["decision"] == "en_debate" and ronda["consenso"] is None
    assert r2["resumen"]["rondas_max"] == 1


def test_traza_recien_cargada(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {})
    v = vista(srv, srv.registrar(SESION))
    assert (v["estado"], v["en_proceso"], v["terminal"]) == ("cargado", True, False)
    assert v["marcados"] == [] and v["extraccion"] is None and v["terminos"] == [] and v["solicitud"] is None
    assert v["resumen"]["n_terminos"] == 0 and v["resumen"]["via"] is None
    assert (v["n_mensajes"], v["ultima_secuencia"]) == (0, 0)


def test_trazas_truncadas_en_cualquier_punto_no_rompen_la_vista(tmp_path, analizador):
    sin_cambios = {"interpretaciones": [I1, I2]}
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False), "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v1": [{"interpretacion_elegida": "I2", "justificacion_por_regla": JUSTIFICACION}],
        "modelador_v1": [MODELADO]})
    req = srv.procesar(SESION)
    srv.validar(req, APROBAR)
    t = srv.traza(req)
    for n in range(len(t.mensajes) + 1):
        transiciones = [x for x in t.transiciones if x.secuencia <= n]
        parcial = t.model_copy(update={"mensajes": t.mensajes[:n], "transiciones": transiciones,
                                       "estado": transiciones[-1].estado})
        formas.VistaRequisito.model_validate(vista_requisito(parcial))
        formas.ResumenRequisito.model_validate(resumen_requisito(parcial))


# ---------------------------------------------------------------- tolerancia

def test_mensajes_repetidos_tras_reinicio_cuenta_el_ultimo(tmp_path, analizador):
    sin_cambios = {"interpretaciones": [I1, I2]}
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False), "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v1": [{"interpretacion_elegida": "I2", "justificacion_por_regla": JUSTIFICACION}]})
    req = srv.procesar(SESION)
    original = srv.traza(req)
    objecion = next(m for m in original.mensajes if m.tipo == "objecion" and m.ronda == 1)
    vieja = {**objecion.model_dump(include={"ronda", "emisor", "receptor", "tipo", "modelo", "prompt_version"}),
             "payload": {**objecion.payload, "objeciones": [{"interpretacion_id": "I1", "regla": "R1", "texto": "vieja"}]}}
    repetida = insertar(original, objecion.secuencia, [vieja])
    assert len(repetida.mensajes) == len(original.mensajes) + 1

    antes, despues = vista_requisito(original), vista_requisito(repetida)
    formas.VistaRequisito.model_validate(despues)
    assert despues["terminos"] == antes["terminos"] and despues["resumen"] == antes["resumen"]
    assert despues["n_repetidos"] == 1 and despues["n_mensajes"] == antes["n_mensajes"] + 1
    assert termino(despues, "sesión")["rondas"][0]["objeciones"][0]["texto"] == "sigue siendo ambiguo"


def test_clasificacion_repetida_descarta_similitudes_anteriores(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2_CERCANA)]})
    original = srv.traza(srv.procesar(SESION))
    interps = next(m for m in original.mensajes if m.tipo == "interpretaciones")
    # primera ejecución, interrumpida: «registrar» era ambiguo y alcanzó a medirse
    vieja = {"ronda": 0, "emisor": "clasificador", "receptor": "divergencia", "tipo": "interpretaciones",
             "payload": {"resultados": [{"termino": "registrar", "tipo_ambiguedad": "lexica",
                                         "interpretaciones": [I1, I2]}]}}
    sim = {"ronda": 0, "emisor": "divergencia", "receptor": "critico", "tipo": "similitud",
           "payload": {"termino": "registrar", "similitud": 0.1, "umbral": 0.75, "decision": "en_debate",
                       "par_minimo": ["I1", "I2"], "pares": {"I1-I2": 0.1}, "modelo_embeddings": "x"}}
    repetida = insertar(original, interps.secuencia, [vieja, sim])
    efectivos, descartados = mensajes_efectivos(repetida)
    assert descartados == 2 and [m.tipo for m in efectivos] == [m.tipo for m in original.mensajes]
    v = vista_requisito(repetida)
    registrar = termino(v, "registrar")
    assert registrar["univoco"] is True and registrar["divergencia_inicial"] is None
    assert v["resumen"] == vista_requisito(original)["resumen"]


def test_traza_anterior_al_tipo_de_ambiguedad(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2_CERCANA)],
        "modelador_v1": [MODELADO]})
    req = srv.procesar(SESION)
    srv.validar(req, APROBAR)
    t = srv.traza(req)
    mensajes = []
    for m in t.mensajes:
        p = dict(m.payload)
        if m.tipo == "interpretaciones":
            p["resultados"] = [{k: v for k, v in r.items() if k != "tipo_ambiguedad"} for r in p["resultados"]]
        elif m.tipo == "solicitud_validacion":
            p["terminos"] = [{k: v for k, v in x.items() if k not in ("tipo_ambiguedad", "origen", "detalle")}
                             for x in p["terminos"]]
        elif m.tipo == "formalizacion":
            if p["alcance"] == "requisito":
                continue
            p = {"termino": p["termino"], "entrada_lel": p["entrada_lel"], "metas": [], "big_picture": {}}
        mensajes.append(m.model_copy(update={"payload": p}))
    config = {k: v for k, v in t.config.items() if k not in ("catalogos", "persistencia")}
    vieja = t.model_copy(update={"mensajes": mensajes, "config": {**config, "corrida": "piloto"}})

    v = vista_requisito(vieja)
    formas.VistaRequisito.model_validate(v)
    s = termino(v, "sesión")
    assert s["tipo_ambiguedad"] == "lexica" and v["resumen"]["tipos"]["lexica"] == 1
    assert next(m for m in v["marcados"] if m["texto"] == "sesión")["tipo"] == "lexica"
    assert s["entrada_lel"]["simbolo"] == "sesión" and v["formalizacion"] is None
    assert v["config"]["catalogos"] == {} and v["config"]["persistencia"] is None
    assert v["config"]["otros"] == {"corrida": "piloto"}


@pytest.mark.parametrize("config, esperado", [
    (None, {"umbral": None, "max_rondas": None, "catalogos": {}, "otros": {}}),
    ({"similarity_threshold": 0.6, "modelos": {"critico": "anthropic:x", "embeddings": "e", "otro": "y"}, "extra": 1},
     {"umbral": 0.6, "modelo_embeddings": "e", "otros": {"extra": 1, "modelos": {"otro": "y"}}}),
])
def test_normalizar_config(config, esperado):
    c = normalizar_config(config)
    formas.ConfigNormalizada.model_validate(c)
    assert {k: c[k] for k in esperado} == esperado


def test_resumen_requisito(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2_CERCANA)]})
    t = srv.traza(srv.procesar(SESION))
    r = resumen_requisito(t)
    formas.ResumenRequisito.model_validate(r)
    v = vista_requisito(t)
    assert set(r) == {"req_id", "proyecto_id", "ciclo", "texto", "origen", "estado", "creado", "actualizado",
                      "similitud_minima", "via", "rondas_max", "n_ambiguos", "tipos", "vaguedad", "en_proceso"}
    assert {k: r[k] for k in ("similitud_minima", "via", "rondas_max", "n_ambiguos", "tipos", "vaguedad")} == {
        k: v["resumen"][k] for k in ("similitud_minima", "via", "rondas_max", "n_ambiguos", "tipos", "vaguedad")}
    assert r["en_proceso"] is False and r["estado"] == "pendiente_validacion"


# ---------------------------------------------------------------- revisión: casos que fallaban o no se probaban

def test_reejecucion_de_una_ronda_descarta_lo_que_la_ultima_no_repitio(tmp_path, analizador):
    """La primera ejecución de la ronda 1 llegó a consenso (retiró I2) y se cortó antes del
    checkpoint; la que quedó en el grafo no retiró nada y terminó en arbitraje. El consenso
    viejo no tiene a quién reemplazarlo por clave, pero va antes de la última objeción."""
    sin_cambios = {"interpretaciones": [I1, I2]}
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False), "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v1": [{"interpretacion_elegida": "I2", "justificacion_por_regla": JUSTIFICACION}]})
    original = srv.traza(srv.procesar(SESION))
    objecion = next(m for m in original.mensajes if m.tipo == "objecion" and m.ronda == 1)
    abandonada = [
        objecion.model_dump(include={"ronda", "emisor", "receptor", "tipo", "modelo", "prompt_version", "payload"}),
        {"ronda": 1, "emisor": "clasificador", "receptor": "divergencia", "tipo": "refinamiento",
         "payload": {"termino": "sesión", "interpretaciones": [I1],
                     "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega servidor"}]}},
        {"ronda": 1, "emisor": "sistema", "receptor": "sistema", "tipo": "consenso",
         "payload": {"termino": "sesión", "motivo": "una_interpretacion", "similitud": None, "umbral": 0.75,
                     "propuesta": "I1", "interpretaciones": [I1]}},
    ]
    repetida = insertar(original, objecion.secuencia, abandonada)

    antes, despues = vista_requisito(original), vista_requisito(repetida)
    formas.VistaRequisito.model_validate(despues)
    assert despues["n_repetidos"] == 3
    assert despues["terminos"] == antes["terminos"] and despues["resumen"] == antes["resumen"]
    s = termino(despues, "sesión")
    assert [r["consenso"] for r in s["rondas"]] == [None, None]
    assert all(i["estado"] == "vigente" for i in s["interpretaciones"])
    assert s["resolucion"]["via"] == "arbitraje"


def test_dos_terminos_consenso_y_arbitraje_en_el_mismo_requisito(tmp_path, analizador):
    from app.analisis import flujo_proyecto

    srv, _, req = montar_dos_terminos(tmp_path, analizador)
    v = vista(srv, req)
    assert v["estado"] == "pendiente_validacion"
    assert [x["estado"] for x in v["transiciones"]] == [
        "cargado", "extraido", "interpretado", "en_debate", "en_debate", "arbitrado", "pendiente_validacion"]

    s, t = termino(v, "sesión"), termino(v, "turno")
    assert [r["ronda"] for r in s["rondas"]] == [1] and [r["ronda"] for r in t["rondas"]] == [1, 2]
    assert s["resolucion"] == {"via": "consenso", "decision": "consenso", "propuesta": I1,
                               "motivo": "una_interpretacion", "similitud_final": None, "arbitraje": None}
    assert [(i["id"], i["estado"], i["retirada_en_ronda"]) for i in s["interpretaciones"]] == [
        ("I1", "vigente", None), ("I2", "retirada", 1)]
    assert t["resolucion"]["via"] == "arbitraje" and t["resolucion"]["propuesta"] == T1
    assert t["resolucion"]["similitud_final"] == 0.0
    assert [r["similitud"]["similitud"] for r in t["rondas"]] == [0.0, 0.0]
    assert v["resumen"] == {"n_terminos": 2, "n_ambiguos": 2,
                            "tipos": {"lexica": 2, "alcance": 0, "anaforica": 0, "sintactica": 0},
                            "vaguedad": [], "regionales": [], "resueltos_por_lel": [], "estructuras": 0,
                            "similitud_minima": 0.0, "via": "arbitraje", "rondas_max": 2, "n_errores": 0}

    # a mano: ronda 1 debate de los dos (2 objeciones, 2 refinamientos, similitud solo de «turno»
    # porque a «sesión» le quedó una, 1 consenso); ronda 2 solo «turno»; 2 similitudes iniciales
    f = flujo_proyecto([srv.traza(req)], [])["total"]
    tipos = f["mensajes_por_tipo"]
    assert (tipos["similitud"], tipos["objecion"], tipos["refinamiento"], tipos["consenso"], tipos["arbitraje"]) == (
        4, 3, 3, 1, 1)
    assert f["fases"][2]["mensajes"] == 12
    # el requisito no pasó por el estado `consenso` aunque un término sí se resolvió así
    assert {k: f[k] for k in ("debates", "rondas_totales", "consensos", "arbitrajes", "directos")} == {
        "debates": 1, "rondas_totales": 2, "consensos": 0, "arbitrajes": 1, "directos": 0}


def test_error_del_modelador_tras_aprobar(tmp_path, analizador):
    from app.analisis import flujo_proyecto

    srv, _, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION], "clasificador_v2": [clasificacion(I1, I2_CERCANA)],
        "modelador_v1": ["no es json", "tampoco"]})
    req = srv.procesar(SESION)
    srv.validar(req, APROBAR)
    v = vista(srv, req)
    assert (v["estado"], v["terminal"], v["en_proceso"]) == ("error", True, False)
    assert [x["estado"] for x in v["transiciones"]][-2:] == ["validado", "error"]
    assert v["validacion"]["decision"] == "aprobar" and v["formalizacion"] is None
    assert [(e["nodo"], e["prompt_version"]) for e in v["errores"]] == [("formalizado", "modelador_v1")]
    s = termino(v, "sesión")
    assert s["validacion"] == {"final": I1, "cambio": "ninguno"} and s["entrada_lel"] is None
    assert v["resumen"]["via"] == "aceptado_directo" and v["resumen"]["n_errores"] == 1

    f = flujo_proyecto([srv.traza(req)], [])["total"]
    assert (f["validados"], f["formalizados"]) == (1, 0)
    assert [x["requisitos_que_pasaron"] for x in f["fases"]] == [1, 1, 1, 1, 0]


def test_similitud_inicial_no_finita_no_es_la_minima(tmp_path, analizador):
    """Con embeddings que devuelven NaN, `min` daba NaN o el otro valor según el orden."""
    srv, _, req = montar_dos_terminos(tmp_path, analizador)
    t = srv.traza(req)
    mensajes = [m.model_copy(update={"payload": {**m.payload, "similitud": float("nan")}})
                if m.tipo == "similitud" and m.ronda == 0 and m.payload.get("termino") == "sesión" else m
                for m in t.mensajes]
    v = vista_requisito(t.model_copy(update={"mensajes": mensajes}))
    assert v["resumen"]["similitud_minima"] == 0.0  # la de «turno»
    assert resumen_requisito(t.model_copy(update={"mensajes": mensajes}))["similitud_minima"] == 0.0
