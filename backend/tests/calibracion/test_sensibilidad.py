"""Funciones puras de la calibración con números conocidos: rejilla, sensibilidad,
distribución y extracción de las similitudes iniciales de las trazas."""
import pytest

from app.calibracion import distribucion, extraer_similitudes, puntos_rejilla, rejilla, reprocesados, sensibilidad
from tests.calibracion.ayudantes import clasificacion, similitud, traza, valor

# ---------------------------------------------------------------- rejilla


def test_rejilla_redondeo_estable():
    assert rejilla(0.5, 0.95, 0.05) == [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
    # sin redondeo: 0.1 + 2 * 0.1 = 0.30000000000000004 y (0.95 - 0.5) / 0.05 = 8.999999999999998
    assert rejilla(0.1, 0.3, 0.1) == [0.1, 0.2, 0.3]
    assert rejilla(0.0, 1.0, 0.25) == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert puntos_rejilla(0.5, 0.95, 0.05) == 10


def test_rejilla_paso_que_no_divide_el_intervalo():
    assert rejilla(0.5, 0.6, 0.07) == [0.5, 0.57]


def test_rejilla_incluye_el_umbral_configurado():
    assert rejilla(0.5, 0.9, 0.1, incluir=0.75) == [0.5, 0.6, 0.7, 0.75, 0.8, 0.9]
    assert rejilla(0.5, 0.9, 0.1, incluir=0.7) == [0.5, 0.6, 0.7, 0.8, 0.9]  # ya estaba: no se repite
    assert rejilla(0.5, 0.9, 0.1, incluir=0.3)[0] == 0.3  # fuera del intervalo también entra


def test_rejilla_vacia_y_paso_invalido():
    assert rejilla(0.9, 0.5, 0.1) == [] and puntos_rejilla(0.9, 0.5, 0.1) == 0
    assert rejilla(0.9, 0.5, 0.1, incluir=0.75) == [0.75]
    with pytest.raises(ValueError):
        puntos_rejilla(0.5, 0.9, 0)


# ---------------------------------------------------------------- sensibilidad

VALORES = [valor("R01", "sesión", 0.6), valor("R02", "jalar", 0.75), valor("R03", "checar", 0.8)]


def test_similitud_igual_al_umbral_es_directo():
    assert [v["decision_real"] for v in VALORES] == ["en_debate", "aceptado_directo", "aceptado_directo"]
    filas = {f["umbral"]: f for f in sensibilidad(VALORES, [0.6, 0.75, 0.8])}
    assert (filas[0.75]["directos"], filas[0.75]["debates"], filas[0.75]["cambian"]) == (2, 1, [])
    assert (filas[0.8]["directos"], filas[0.8]["debates"]) == (1, 2)  # 0.8 >= 0.8: directo
    assert filas[0.8]["cambian"] == [{"req_id": "R02", "termino": "jalar", "similitud": 0.75,
                                      "decision_real": "aceptado_directo", "decision_con_umbral": "en_debate"}]
    assert filas[0.6]["cambian"] == [{"req_id": "R01", "termino": "sesión", "similitud": 0.6,
                                      "decision_real": "en_debate", "decision_con_umbral": "aceptado_directo"}]


def test_sensibilidad_casi_igual_al_umbral_es_debate():
    """El punto flotante no se redondea a favor del umbral: es la misma regla que usó el grafo."""
    v = valor("R01", "sesión", 0.7499999999999999)
    assert v["decision_real"] == "en_debate"
    assert sensibilidad([v], [0.75])[0]["debates"] == 1


def test_sensibilidad_sin_valores():
    assert sensibilidad([], [0.5, 0.75]) == [{"umbral": 0.5, "directos": 0, "debates": 0, "cambian": []},
                                             {"umbral": 0.75, "directos": 0, "debates": 0, "cambian": []}]


# ---------------------------------------------------------------- distribución

def test_distribucion_con_numeros_conocidos():
    sims = [0.52, 0.55, 0.61, 0.75, 0.75]
    d = distribucion([valor(f"R0{i}", "t", s) for i, s in enumerate(sims, 1)], 0.05, origen=0.5)
    assert d["bins"] == [{"desde": 0.5, "hasta": 0.55, "n": 1}, {"desde": 0.55, "hasta": 0.6, "n": 1},
                         {"desde": 0.6, "hasta": 0.65, "n": 1}, {"desde": 0.65, "hasta": 0.7, "n": 0},
                         {"desde": 0.7, "hasta": 0.75, "n": 0}, {"desde": 0.75, "hasta": 0.8, "n": 2}]
    assert (d["n"], d["min"], d["max"], d["mediana"]) == (5, 0.52, 0.75, 0.61)
    assert d["media"] == pytest.approx(0.636)
    assert (d["ancho_bin"], d["origen"]) == (0.05, 0.5)


def test_distribucion_bordes_cuadran_con_la_regla():
    """Para cada umbral de la rejilla, los bins a su izquierda suman exactamente los debates."""
    sims = [0.0, 0.3, 0.55, 0.7499999999999999, 0.75, 0.8, 0.95, 0.9999, 1.0, -0.2]
    valores = [valor(f"R{i:02d}", "t", s) for i, s in enumerate(sims, 1)]
    d = distribucion(valores, 0.05, origen=0.5)
    assert sum(b["n"] for b in d["bins"]) == len(sims)
    assert d["bins"][0]["desde"] == -0.2 and d["bins"][-1] == {"desde": 1.0, "hasta": 1.05, "n": 1}
    for fila in sensibilidad(valores, rejilla(0.5, 0.95, 0.05)):
        assert fila["debates"] == sum(b["n"] for b in d["bins"] if b["hasta"] <= fila["umbral"])


def test_distribucion_vacia_y_de_un_valor():
    assert distribucion([], 0.05, origen=0.5) == {"ancho_bin": 0.05, "origen": 0.5, "n": 0, "min": None, "max": None,
                                                  "media": None, "mediana": None, "bins": []}
    d = distribucion([valor("R01", "t", 0.0)], 0.05, origen=0.5)
    assert d["bins"] == [{"desde": 0.0, "hasta": 0.05, "n": 1}]
    with pytest.raises(ValueError):
        distribucion([], 0)
    with pytest.raises(ValueError):  # el redondeo a 6 decimales juntaría bordes
        distribucion([valor("R01", "t", 0.5)], 1e-7)


# ---------------------------------------------------------------- extracción desde las trazas

def test_extraer_similitudes_iniciales():
    trazas = [
        traza("R02", similitud(None, None), estado="formalizado"),  # sin interpretaciones: se ignora
        traza("R01",
              clasificacion(("sesión", "lexica"), ("cada usuario", "alcance")),
              similitud("sesión", 0.9),
              similitud("cada usuario", 0.3),
              ("objecion", 1, {"termino": "cada usuario"}),
              similitud("cada usuario", 0.8, ronda=1, decision="consenso"),  # ronda de debate: no cuenta
              ("consenso", 1, {"termino": "cada usuario", "motivo": "umbral"}),
              ciclo=2),
        traza("R03", clasificacion(("jalar", None)), similitud("jalar", 0.1),
              ("arbitraje", 2, {"termino": "jalar", "interpretacion_elegida": "I1"}), estado="formalizado"),
        traza("R10", clasificacion(("checar", "lexica")), similitud("checar", 0.2), estado="en_debate"),
    ]
    valores = extraer_similitudes(trazas)
    assert [(v["req_id"], v["termino"], v["similitud"]) for v in valores] == [
        ("R01", "sesión", 0.9), ("R01", "cada usuario", 0.3), ("R03", "jalar", 0.1), ("R10", "checar", 0.2)]
    sesion, cada, jalar, checar = valores
    assert sesion == {"req_id": "R01", "proyecto_id": "P01", "ciclo": 2, "termino": "sesión", "similitud": 0.9,
                      "umbral_usado": 0.75, "decision_real": "aceptado_directo", "tipo_ambiguedad": "lexica",
                      "via": "aceptado_directo", "estado_requisito": "pendiente_validacion",
                      "modelo_embeddings": "embeddings-falsos"}
    assert (cada["decision_real"], cada["via"], cada["tipo_ambiguedad"]) == ("en_debate", "consenso", "alcance")
    assert (jalar["via"], jalar["tipo_ambiguedad"]) == ("arbitraje", "lexica")  # sin tipo: léxica (ADR 0010 §5)
    assert (checar["via"], checar["estado_requisito"]) == (None, "en_debate")  # aún se debate


def test_extraer_similitudes_nodo_reejecutado_cuenta_la_ultima_clasificacion():
    t = traza("R01",
              clasificacion(("sesión", "lexica"), ("jalar", "lexica")),
              similitud("sesión", 0.2), similitud("jalar", 0.3),
              clasificacion(("sesión", "lexica")),  # el nodo se reejecutó y esta vez «jalar» no llegó
              similitud("Sesion", 0.4))
    assert [(v["termino"], v["similitud"]) for v in extraer_similitudes([t])] == [("Sesion", 0.4)]


def test_extraer_similitudes_excluye_trazas_reprocesadas():
    trazas = [traza("R01", clasificacion(("sesión", "lexica")), similitud("sesión", 0.2)),
              traza("R02", clasificacion(("sesión", "lexica")), similitud("sesión", 0.5), reproceso_de="R01")]
    assert reprocesados(trazas) == {"R01"}
    assert [v["req_id"] for v in extraer_similitudes(trazas)] == ["R02"]


def test_reproceso_pendiente_o_fallido_conserva_la_traza_anterior():
    """Solo se descarta la traza anterior cuando su reproceso ya tiene su propia similitud inicial."""
    anterior = traza("R01", clasificacion(("sesión", "lexica")), similitud("sesión", 0.2))
    en_cola = traza("R02", estado="cargado", reproceso_de="R01")
    fallido = traza("R03", ("error", 0, {"nodo": "extraido", "mensaje": "falló"}), estado="error", reproceso_de="R01")
    assert reprocesados([anterior, en_cola, fallido]) == set()
    assert [v["req_id"] for v in extraer_similitudes([anterior, en_cola, fallido])] == ["R01"]
    # el reproceso ya no encontró interpretaciones (similitud null): la versión vigente no tiene nada que medir
    sin_ambiguedad = traza("R04", similitud(None, None), estado="formalizado", reproceso_de="R01")
    assert reprocesados([anterior, sin_ambiguedad]) == {"R01"}
    assert extraer_similitudes([anterior, sin_ambiguedad]) == []


def test_decision_no_registrada_se_reconstruye_con_la_regla():
    _, _, sin_decision = similitud("sesión", 0.75)
    sin_decision = {k: v for k, v in sin_decision.items() if k != "decision"}
    _, _, rara = similitud("jalar", 0.4, decision="consenso")  # en ronda 0 solo hay directo o debate
    _, _, sin_umbral = similitud("checar", 0.9)
    sin_umbral = {k: v for k, v in sin_umbral.items() if k not in ("decision", "umbral")}
    t = traza("R01", clasificacion(("sesión", "lexica"), ("jalar", "lexica"), ("checar", "lexica")),
              ("similitud", 0, sin_decision), ("similitud", 0, rara), ("similitud", 0, sin_umbral))
    assert [(v["termino"], v["decision_real"]) for v in extraer_similitudes([t])] == [
        ("sesión", "aceptado_directo"), ("jalar", "en_debate")]  # sin decisión ni umbral no hay contra qué comparar


def test_extraer_similitudes_sin_trazas():
    assert extraer_similitudes([]) == []
