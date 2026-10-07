"""Contraste contra etiquetas sembradas a mano y armado del informe completo."""
import pytest

from app.calibracion import NOTA, contrastar, formas, informe_calibracion, metricas, seleccionar_etiquetas
from tests.calibracion.ayudantes import clasificacion, similitud, traza, valor


def etiqueta(req_id, termino, ambiguo, tipo=None):
    return {"req_id": req_id, "termino": termino, "ambiguo": ambiguo, "tipo_ambiguedad": tipo}


# A y B ambiguos (0.3, 0.6), C y D no (0.7, 0.9); E etiquetado sin similitud; F con similitud sin etiqueta
VALORES = [valor("R01", "sesión", 0.3), valor("R02", "jalar", 0.6), valor("R03", "checar", 0.7),
           valor("R04", "registrar", 0.9), valor("R06", "dar de alta", 0.5)]
ETIQUETAS = [etiqueta("R01", "Sesion", True, "lexica"), etiqueta("R02", "jalar", True, "lexica"),
             etiqueta("R03", "checar", False), etiqueta("R04", "registrar", False),
             etiqueta("R05", "ahorita", True)]


def test_contraste_con_numeros_conocidos():
    c = contrastar(VALORES, ETIQUETAS, [0.2, 0.5, 0.6, 0.65, 0.75])
    assert (c["n_etiquetas"], c["n_emparejados"], c["n_ambiguos"], c["n_no_ambiguos"]) == (5, 4, 2, 2)
    assert c["etiquetas_sin_similitud"] == [{"req_id": "R05", "termino": "ahorita", "ambiguo": True,
                                             "tipo_ambiguedad": None}]
    assert c["valores_sin_etiqueta"] == [{"req_id": "R06", "termino": "dar de alta", "similitud": 0.5}]
    assert c["separacion"] == {"max_ambiguos": 0.6, "min_no_ambiguos": 0.7, "separa": True}

    f = {x["umbral"]: x for x in c["por_umbral"]}
    # 0.65 separa: los ambiguos van a debate y los otros no
    assert {k: f[0.65][k] for k in ("vp", "fp", "vn", "fn", "precision", "exhaustividad", "f1")} == \
        {"vp": 2, "fp": 0, "vn": 2, "fn": 0, "precision": 1.0, "exhaustividad": 1.0, "f1": 1.0}
    assert f[0.65]["mal_separados"] == []
    # 0.75 manda «checar» a debate: falso positivo
    assert (f[0.75]["vp"], f[0.75]["fp"], f[0.75]["precision"], f[0.75]["exhaustividad"], f[0.75]["f1"]) == \
        (2, 1, 0.666667, 1.0, 0.8)
    assert f[0.75]["mal_separados"] == [{"req_id": "R03", "termino": "checar", "similitud": 0.7, "ambiguo": False,
                                         "decision_con_umbral": "en_debate", "tipo_error": "falso_positivo"}]
    # borde: «jalar» tiene exactamente 0.6 y con umbral 0.6 se acepta directo: falso negativo
    assert (f[0.6]["vp"], f[0.6]["fn"], f[0.6]["exhaustividad"], f[0.6]["f1"]) == (1, 1, 0.5, 0.666667)
    assert [m["termino"] for m in f[0.6]["mal_separados"]] == ["jalar"]
    assert f[0.6]["mal_separados"][0]["tipo_error"] == "falso_negativo"
    # sin ningún debate la precisión no está definida
    assert (f[0.2]["vp"], f[0.2]["fp"], f[0.2]["fn"], f[0.2]["precision"], f[0.2]["exhaustividad"], f[0.2]["f1"]) == \
        (0, 0, 2, None, 0.0, None)


def test_contraste_cuando_la_similitud_no_separa():
    valores = [valor("R01", "sesión", 0.8), valor("R02", "jalar", 0.4)]
    c = contrastar(valores, [etiqueta("R01", "sesión", True), etiqueta("R02", "jalar", False)], [0.5])
    assert c["separacion"] == {"max_ambiguos": 0.8, "min_no_ambiguos": 0.4, "separa": False}
    assert (c["por_umbral"][0]["fp"], c["por_umbral"][0]["fn"], c["por_umbral"][0]["f1"]) == (1, 1, 0.0)


def test_contraste_con_una_sola_clase():
    c = contrastar([valor("R01", "sesión", 0.8)], [etiqueta("R01", "sesión", True)], [0.75])
    assert c["separacion"]["separa"] is None


def test_metricas():
    assert metricas(0, 0, 3, 0) == {"vp": 0, "fp": 0, "vn": 3, "fn": 0, "precision": None, "exhaustividad": None,
                                    "f1": None}
    assert metricas(0, 2, 0, 1)["f1"] == 0.0


def test_seleccionar_etiquetas():
    docs = [
        {"evaluacion_id": "E01", "proyecto_id": "P02", "etiquetas": [etiqueta("R01", "vieja", True)]},
        {"evaluacion_id": "E02", "proyecto_id": "P03", "resumen": "sin etiquetas"},  # no cuenta
        {"evaluacion_id": "E03", "proyecto_id": "P02", "etiquetas": [
            etiqueta("R01", "sesión", True, "lexica"),
            {**etiqueta("R02", "jalar", False), "nota": "campo extra del módulo de evaluación"},
            {"req_id": "R03", "termino": "checar"},  # sin «ambiguo»: inválida
            "no es un objeto",
            etiqueta("R01", "Sesión", False),  # misma clave: gana la última
        ]},
        {"proyecto_id": "P04", "etiquetas": [etiqueta("R09", "cuenta", True)]},  # sin evaluacion_id
    ]
    fuentes, etiquetas, invalidas = seleccionar_etiquetas(docs)
    assert fuentes == [{"proyecto_id": "P02", "evaluacion_id": "E03", "n_etiquetas": 3},
                       {"proyecto_id": "P04", "evaluacion_id": None, "n_etiquetas": 1}]
    assert invalidas == 2
    assert [(e["req_id"], e["termino"], e["ambiguo"]) for e in etiquetas] == [
        ("R01", "Sesión", False), ("R02", "jalar", False), ("R09", "cuenta", True)]
    assert seleccionar_etiquetas([]) == ([], [], 0)


# ---------------------------------------------------------------- informe

TRAZAS = [
    traza("R01", clasificacion(("sesión", "lexica")), similitud("sesión", 0.9)),
    traza("R02", clasificacion(("jalar", "lexica")), similitud("jalar", 0.3),
          ("consenso", 1, {"termino": "jalar", "motivo": "una_interpretacion"})),
    traza("R03", similitud(None, None)),
]


def informe(docs=(), **ajustes):
    parametros = {"umbral_configurado": 0.75, "max_rondas": 2, "desde": 0.5, "hasta": 0.95, "paso": 0.1,
                  "proyecto_id": "P01", **ajustes}
    salida = informe_calibracion(TRAZAS, docs, **parametros)
    formas.Calibracion.model_validate(salida)
    return salida


def test_informe_sin_etiquetas():
    r = informe()
    assert (r["proyecto_id"], r["umbral_configurado"], r["max_rondas"], r["n_valores"]) == ("P01", 0.75, 2, 2)
    assert r["parametros"] == {"desde": 0.5, "hasta": 0.95, "paso": 0.1}
    assert [f["umbral"] for f in r["rejilla"]] == [0.5, 0.6, 0.7, 0.75, 0.8, 0.9]
    assert [f["umbral"] for f in r["rejilla"] if f["configurado"]] == [0.75]
    configurada = next(f for f in r["rejilla"] if f["configurado"])
    assert (configurada["directos"], configurada["debates"], configurada["cambian"]) == (1, 1, [])
    assert r["con_ground_truth"] is None
    assert (r["umbrales_usados"], r["modelos_embeddings"], r["reprocesados"]) == ([0.75], ["embeddings-falsos"], [])
    assert r["distribucion"]["n"] == 2 and r["distribucion"]["origen"] == 0.5 and r["distribucion"]["ancho_bin"] == 0.1
    assert r["avisos"] == [] and r["nota"] == NOTA


def test_informe_con_etiquetas():
    docs = [{"evaluacion_id": "E01", "proyecto_id": "P01",
             "etiquetas": [etiqueta("R01", "sesión", False), etiqueta("R02", "jalar", True), {"req_id": "R03"}]}]
    gt = informe(docs)["con_ground_truth"]
    assert gt["fuentes"] == [{"proyecto_id": "P01", "evaluacion_id": "E01", "n_etiquetas": 2}]
    assert (gt["n_invalidas"], gt["n_emparejados"], gt["separacion"]["separa"]) == (1, 2, True)
    assert [f["umbral"] for f in gt["por_umbral"] if f["configurado"]] == [0.75]
    assert all(f["f1"] == 1.0 for f in gt["por_umbral"] if 0.3 < f["umbral"] <= 0.9)


def test_informe_avisa_lo_que_no_es_comparable():
    trazas = [traza("R01", clasificacion(("sesión", "lexica")), similitud("sesión", 0.9, umbral=0.8, modelo="otro")),
              traza("R02", clasificacion(("jalar", "lexica")), similitud("jalar", 0.3))]
    docs = [{"proyecto_id": "P01", "etiquetas": [etiqueta("R01", "sesión", True), etiqueta("R02", "jalar", False)]}]
    r = informe_calibracion(trazas, docs, umbral_configurado=0.75, max_rondas=2, desde=0.5, hasta=0.95, paso=0.05)
    formas.Calibracion.model_validate(r)
    assert r["proyecto_id"] is None
    assert r["umbrales_usados"] == [0.75, 0.8] and r["modelos_embeddings"] == ["embeddings-falsos", "otro"]
    assert len(r["avisos"]) == 3
    assert "2 modelos de embeddings" in r["avisos"][0] and "0.8" in r["avisos"][1] and "no separa" in r["avisos"][2]


def test_informe_vacio():
    r = informe_calibracion([], [], umbral_configurado=0.75, max_rondas=2, desde=0.5, hasta=0.95, paso=0.05)
    formas.Calibracion.model_validate(r)
    assert (r["n_valores"], r["valores"], r["distribucion"]["bins"]) == (0, [], [])
    assert all(f["directos"] == f["debates"] == 0 for f in r["rejilla"])
    assert r["avisos"] == ["sin similitudes calculadas: ningún término con interpretaciones llegó al mecanismo de "
                           "divergencia"]


@pytest.mark.parametrize("umbral", [0.72, 0.3])
def test_informe_umbral_configurado_fuera_de_la_rejilla(umbral):
    r = informe(umbral_configurado=umbral)
    assert [f["umbral"] for f in r["rejilla"] if f["configurado"]] == [umbral]
