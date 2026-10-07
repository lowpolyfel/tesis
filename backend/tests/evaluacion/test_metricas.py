"""Métricas puras sobre trazas hechas a mano, con números verificados a mano."""
from app.evaluacion.agente_unico import EntradaLineaBase
from app.evaluacion.corpus import RequisitoGT
from app.evaluacion.emparejamiento import lematizador, sin_lemas
from app.evaluacion.metricas import (
    completa,
    deteccion,
    esperados,
    etiquetas_de,
    informe,
    lado_linea_base,
    lado_sistema,
    resultado_sistema,
    resumen_lado,
    resumen_sistema,
)
from app.evaluacion.modelos import Evaluacion
from app.models import Mensaje, Transicion, Traza
from tests.evaluacion.ayudantes import GROUND_TRUTH
from tests.fakes import interp

GT_A, GT_B, GT_C, GT_D = (RequisitoGT.model_validate(g) for g in GROUND_TRUTH)


def traza(*mensajes: tuple, estado="pendiente_validacion", transiciones=("cargado",)) -> Traza:
    return Traza(req_id="R01", texto="requisito", estado=estado, config={},
                 transiciones=[Transicion(estado=e, secuencia=0) for e in transiciones],
                 mensajes=[Mensaje(req_id="R01", secuencia=i, ronda=ronda, emisor="sistema", receptor="sistema", tipo=tipo,
                                   payload=payload) for i, (tipo, ronda, payload) in enumerate(mensajes, 1)])


def filtrado(*pares):
    return "filtrado", 0, {"terminos": [{"termino": t, "decision_filtro": d} for t, d in pares]}


def clasificado(*resultados):
    return "interpretaciones", 0, {"resultados": list(resultados)}


def similitud(termino, valor, decision="en_debate"):
    return "similitud", 0, {"termino": termino, "similitud": valor, "umbral": 0.75, "decision": decision}


AMBAS = [interp("I1", "periodo de uso", "p1"), interp("I2", "evento de conexión", "p2")]
FILTRADO = filtrado(("sesión", "candidato"), ("jalar", "regional"), ("ahorita", "vaguedad"),
                    ("cliente", "resuelto_por_lel"))


def test_deteccion_con_denominadores_cero():
    assert deteccion(0, 0, 0) == {"vp": 0, "fp": 0, "fn": 0, "precision": None, "exhaustividad": None, "f1": None}
    assert deteccion(2, 1, 1) == {"vp": 2, "fp": 1, "fn": 1, "precision": 0.666667, "exhaustividad": 0.666667,
                                  "f1": 0.666667}
    assert deteccion(0, 2, 1)["f1"] == 0.0
    assert deteccion(3, 0, 1)["f1"] == 0.857143  # 6 / 7


def test_esperados_sin_repetir_un_regional_que_tambien_es_ambiguo():
    gt = RequisitoGT.model_validate({**GROUND_TRUTH[1], "regionales": ["Jalar"]})
    assert esperados(gt) == [{"termino": "jalar", "clase": "ambiguedad", "tipo_ambiguedad": "lexica"},
                             {"termino": "ahorita", "clase": "vaguedad", "tipo_ambiguedad": None}]


def test_resultado_cuenta_la_ultima_clasificacion_y_lo_que_vino_despues():
    t = traza(
        FILTRADO,
        clasificado({"termino": "sesión", "univoco": True}, {"termino": "jalar", "univoco": True}),
        similitud("sesión", 0.9, "aceptado_directo"),  # de la clasificación anterior: no cuenta
        clasificado({"termino": "sesión", "interpretaciones": AMBAS},  # traza anterior al tipo → léxica
                    {"termino": "jalar", "tipo_ambiguedad": "lexica", "interpretaciones": AMBAS}),
        similitud("sesión", 0.1), similitud("jalar", 0.2),
        ("consenso", 1, {"termino": "jalar", "motivo": "una_interpretacion", "propuesta": "I1"}),
        ("arbitraje", 2, {"termino": "sesión", "interpretacion_elegida": "I2"}),
        ("solicitud_validacion", 0, {"terminos": [
            {"termino": "sesión", "propuesta": AMBAS[1]}, {"termino": "jalar", "propuesta": AMBAS[0]}]}),
        transiciones=("cargado", "extraido", "interpretado", "en_debate", "arbitrado", "pendiente_validacion"))
    rs = resultado_sistema(t)
    assert (rs["listo"], rs["error"], rs["ambiguo"], rs["debate"]) == (True, None, True, True)
    assert rs["resueltos_por_lel"] == ["cliente"]
    assert [(x["termino"], x["origen"], x["clasificado"], x["tipo_ambiguedad"], x["interpretacion"], x["via"],
             x["similitud"]) for x in rs["terminos"]] == [
        ("sesión", "candidato", True, "lexica", "evento de conexión", "arbitraje", 0.1),
        ("jalar", "regional", True, "lexica", "periodo de uso", "consenso", 0.2),
        ("ahorita", "vaguedad", False, None, None, None, None),
    ]


def test_requisito_en_error_antes_de_clasificar():
    t = traza(FILTRADO, ("error", 0, {"nodo": "interpretado", "excepcion": "FalloEstructurado",
                                      "mensaje": "falló el Clasificador"}),
              estado="error", transiciones=("cargado", "extraido", "error"))
    rs = resultado_sistema(t)
    assert (rs["listo"], rs["error"], rs["ambiguo"], rs["debate"]) == (True, "falló el Clasificador", None, False)
    lado = lado_sistema(rs, GT_B, sin_lemas)
    # los filtros sí corrieron: «jalar» (regional) y «ahorita» (vaguedad) cuentan como detectados
    assert (lado["ambiguo"], lado["correcto"], lado["debate_gt"]) == (None, None, "faltante")
    assert lado["deteccion"] == {"vp": 2, "fp": 0, "fn": 0}
    assert lado["deteccion_ambiguedad"] == {"vp": 0, "fp": 0, "fn": 1}
    r = resumen_sistema([(lado, GT_B)])
    assert r["errores"] == 1 and r["requisito"] == {"vp": 0, "fp": 0, "vn": 0, "fn": 0, "sin_decision": 1,
                                                    "exactitud": 0.0}
    assert r["debates"] == {"activados": 0, "necesarios": 1, "justificados": 0, "de_mas": 0, "faltantes": 1}


def test_vaguedad_o_regional_que_el_ground_truth_no_lista_no_cuenta_como_deteccion():
    t = traza(filtrado(("rápido", "vaguedad"), ("checar", "regional")),
              clasificado({"termino": "checar", "univoco": True}),
              ("similitud", 0, {"similitud": None, "umbral": 0.75, "motivo": "sin_interpretaciones",
                                "decision": "aceptado_directo"}))
    lado = lado_sistema(resultado_sistema(t), GT_D, sin_lemas)
    assert [(x["termino"], x["detectado"]) for x in lado["terminos"]] == [("checar", False), ("rápido", False)]
    assert (lado["ambiguo"], lado["correcto"], lado["debate_gt"]) == (False, True, "sin_debate_correcto")
    assert lado["deteccion"] == {"vp": 0, "fp": 0, "fn": 0}


def test_requisito_en_proceso_no_cuenta():
    lado = lado_sistema(resultado_sistema(traza(FILTRADO, estado="en_debate")), GT_A, sin_lemas)
    assert (lado["listo"], lado["estado"], lado["deteccion"]) == (False, "en_debate", {"vp": 0, "fp": 0, "fn": 0})
    assert lado_sistema(None, GT_A, sin_lemas)["estado"] is None
    assert resumen_lado([(lado, GT_A)])["n"] == 0


def test_termino_que_fallo_a_mitad_del_debate_queda_sin_via():
    t = traza(FILTRADO, clasificado({"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretaciones": AMBAS},
                                    {"termino": "jalar", "univoco": True}),
              similitud("sesión", 0.1), ("error", 1, {"nodo": "en_debate", "mensaje": "el Crítico no respondió"}),
              estado="error", transiciones=("cargado", "extraido", "interpretado", "en_debate", "error"))
    lado = lado_sistema(resultado_sistema(t), GT_A, sin_lemas)
    assert (lado["ambiguo"], lado["correcto"], lado["debate_gt"], lado["error"]) == (True, True, "justificado",
                                                                                     "el Crítico no respondió")
    assert resumen_sistema([(lado, GT_A)])["vias"] == {"aceptado_directo": 0, "consenso": 0, "arbitraje": 0,
                                                       "sin_via": 1}


def test_linea_base_por_lema_y_tipo(analizador):
    entrada = EntradaLineaBase.model_validate({"resultado": {"ambiguo": True, "terminos": [
        {"termino": "sesiones", "tipo_ambiguedad": "anaforica", "interpretacion_elegida": "x"},
        {"termino": "usuario", "tipo_ambiguedad": "lexica", "interpretacion_elegida": "y"}]}, "modelo": "m"})
    lado = lado_linea_base(entrada, GT_A, lematizador(analizador))
    sesiones, usuario = lado["terminos"]
    assert (sesiones["emparejado_con"], sesiones["criterio"], sesiones["tipo_correcto"]) == ("sesión", "lema", False)
    assert usuario["emparejado_con"] is None
    assert lado["deteccion"] == {"vp": 1, "fp": 1, "fn": 0} == lado["deteccion_ambiguedad"]
    r = resumen_lado([(lado, GT_A), (lado_linea_base(None, GT_B, sin_lemas), GT_B)])
    assert r["n"] == 1 and r["tipo"] == {"n": 1, "aciertos": 0, "exactitud": 0.0}
    assert r["deteccion"]["precision"] == 0.5 and r["requisito"]["exactitud"] == 1.0


def test_etiquetas_por_candidato_y_por_termino_del_ground_truth_sin_pareja(analizador):
    t = traza(filtrado(("sesiones", "candidato"), ("ahorita", "vaguedad")),
              clasificado({"termino": "sesiones", "tipo_ambiguedad": "lexica", "interpretaciones": AMBAS},
                          {"termino": "datos", "univoco": True}))
    gt = RequisitoGT.model_validate({**GROUND_TRUTH[0], "terminos": [
        *GROUND_TRUTH[0]["terminos"],
        {"termino": "su historial", "tipo_ambiguedad": "anaforica", "interpretaciones_validas": ["a", "b"]}]})
    assert etiquetas_de("R07", resultado_sistema(t), gt, lematizador(analizador)) == [
        {"req_id": "R07", "termino": "sesiones", "ambiguo": True, "tipo_ambiguedad": "lexica"},
        {"req_id": "R07", "termino": "datos", "ambiguo": False, "tipo_ambiguedad": None},
        {"req_id": "R07", "termino": "su historial", "ambiguo": True, "tipo_ambiguedad": "anaforica"},
    ]


def test_etiquetas_prefieren_el_candidato_con_interpretaciones():
    """Un candidato unívoco que aparece antes no le quita el término del ground truth al que sí
    tuvo interpretaciones y similitud: la calibración recibiría «su cliente» como no ambiguo."""
    t = traza(filtrado(("historial", "candidato"), ("su cliente", "anafora")),
              clasificado({"termino": "historial", "univoco": True},
                          {"termino": "su cliente", "tipo_ambiguedad": "anaforica", "interpretaciones": AMBAS}),
              similitud("su cliente", 0.4))
    gt = RequisitoGT.model_validate({"id": "X", "ambiguo": True, "terminos": [
        {"termino": "historial de compras de su cliente", "tipo_ambiguedad": "anaforica",
         "interpretaciones_validas": ["del administrador", "del cliente"]}]})
    rs = resultado_sistema(t)
    assert etiquetas_de("R01", rs, gt, sin_lemas) == [
        {"req_id": "R01", "termino": "historial", "ambiguo": False, "tipo_ambiguedad": None},
        {"req_id": "R01", "termino": "su cliente", "ambiguo": True, "tipo_ambiguedad": "anaforica"},
    ]
    # las métricas emparejan igual
    assert [(x["termino"], x["criterio"]) for x in lado_sistema(rs, gt, sin_lemas)["terminos"]] == [
        ("historial", None), ("su cliente", "contencion")]
    # un unívoco que coincide exacto sí se queda con el término: el Clasificador lo tuvo y no vio ambigüedad
    gt_exacto = RequisitoGT.model_validate({**gt.model_dump(), "terminos": [
        {**gt.terminos[0].model_dump(), "termino": "historial"}]})
    assert [e["ambiguo"] for e in etiquetas_de("R01", rs, gt_exacto, sin_lemas)] == [True, False]


def test_lo_que_marca_un_catalogo_cuenta_aunque_el_ground_truth_lo_liste_en_la_otra_clase():
    """«ahorita» está en el catálogo de vaguedad; el ground truth puede listarlo como regional."""
    gt = RequisitoGT.model_validate({"id": "X", "ambiguo": False, "terminos": [], "vaguedad": [],
                                     "regionales": ["ahorita"]})
    t = traza(filtrado(("ahorita", "vaguedad")), clasificado())
    lado = lado_sistema(resultado_sistema(t), gt, sin_lemas)
    [ahorita] = lado["terminos"]
    assert (ahorita["detectado"], ahorita["motivo_deteccion"], ahorita["clase_gt"]) == (True, "vaguedad", "regional")
    assert lado["deteccion"] == {"vp": 1, "fp": 0, "fn": 0}
    assert lado["deteccion_ambiguedad"] == {"vp": 0, "fp": 0, "fn": 0}


def _evaluacion(*pares) -> Evaluacion:
    """`pares`: (id_corpus, ground truth); req_id R01, R02… en orden."""
    return Evaluacion(evaluacion_id="E01", nombre="prueba", proyecto_id="P01", corpus="c", huella="h", config={},
                      ground_truth=[RequisitoGT.model_validate({**g.model_dump(), "id": i}) for i, g in pares],
                      items=[{"id_corpus": i, "req_id": f"R{n:02d}"} for n, (i, _) in enumerate(pares, 1)])


def _con_id(t: Traza, req_id: str) -> Traza:
    return t.model_copy(update={"req_id": req_id})


def test_una_traza_que_no_existe_no_detiene_el_cierre():
    ev = _evaluacion(("A", GT_A), ("B", GT_B))
    lista = _con_id(traza(FILTRADO, clasificado()), "R01")
    assert not completa(ev, {"R01": lista})  # falta la línea base
    ev.linea_base = {i: EntradaLineaBase(resultado={"ambiguo": False}) for i in "AB"}
    assert completa(ev, {"R01": lista})  # R02 no existe: no va a llegar
    assert not completa(ev, {"R01": _con_id(traza(FILTRADO, estado="en_debate"), "R01")})
    r = informe(ev, {"R01": lista}, sin_lemas, huella_actual="h")
    assert "no se encontraron las trazas R02: esos requisitos no cuentan" in r["avisos"]
    assert r["progreso"] == {"total": 2, "listos_sistema": 1, "listos_linea_base": 2}


def test_avisos_de_error_antes_y_despues_de_la_clasificacion():
    antes = traza(FILTRADO, ("error", 0, {"nodo": "interpretado", "mensaje": "falló el Clasificador"}),
                  estado="error", transiciones=("cargado", "extraido", "error"))
    despues = traza(FILTRADO, clasificado({"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretaciones": AMBAS}),
                    similitud("sesión", 0.1), ("error", 1, {"nodo": "en_debate", "mensaje": "el Crítico no respondió"}),
                    estado="error", transiciones=("cargado", "extraido", "interpretado", "en_debate", "error"))
    ev = _evaluacion(("B", GT_B), ("A", GT_A))
    r = informe(ev, {"R01": _con_id(antes, "R01"), "R02": _con_id(despues, "R02")}, sin_lemas, huella_actual="h")
    assert [f["sistema"]["ambiguo"] for f in r["requisitos"]] == [None, True]
    assert ("1 requisito(s) del sistema fallaron antes de la clasificación (B): cuentan como «sin decisión», sin debate, "
            "y de sus términos solo cuenta lo que ya habían marcado los filtros") in r["avisos"]
    assert ("1 requisito(s) del sistema fallaron después de la clasificación (A): cuenta lo que propuso el "
            "Clasificador; los términos que no terminaron el debate quedan sin vía") in r["avisos"]
    s = r["resumen"]["sistema"]
    assert s["errores"] == 2 and s["requisito"] == {"vp": 1, "fp": 0, "vn": 0, "fn": 0, "sin_decision": 1,
                                                    "exactitud": 0.5}
