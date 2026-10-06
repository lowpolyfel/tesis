"""Rutas de la calibración sobre trazas reales del grafo (LLM y embeddings falsos).

P01 (normal): R01 aceptado directo (similitud 0.9987), R02 debatido hasta consenso
(similitud exactamente 0.0: paráfrasis ortogonales) y R03 sin interpretaciones.
P02 (evaluación): R04 debatido (0.0) y R05 directo, con etiquetas de ground truth
sembradas a mano en `evaluaciones`, como las dejaría el módulo de evaluación.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import calibracion, proyectos
from app.calibracion import COLECCION_EVALUACIONES, NOTA, formas
from tests.escenarios import EXTRACCION_SESION, I1, I2, P1_CERCANA, SESION, clasificacion, montar
from tests.fakes import interp, r3_todas

UNIVOCO = {"resultados": [{"termino": t, "univoco": True} for t in ("sistema", "registrar", "sesión")]}
RETIRA_I2 = {"interpretaciones": [I1], "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega red"}]}
REJILLA_POR_OMISION = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]


class EmbeddingsQueNoSeUsan:
    modelo = "no-debe-usarse"

    def vectorizar(self, textos):
        raise AssertionError("la calibración no debe recalcular embeddings")


@pytest.fixture(scope="module")
def entorno(tmp_path_factory, analizador):
    cercana = clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))
    srv, _, repo = montar(tmp_path_factory.mktemp("calibracion"), analizador, {
        "extractor_v1": [EXTRACCION_SESION] * 5,
        "clasificador_v2": [cercana, clasificacion(I1, I2), UNIVOCO, clasificacion(I1, I2), cercana],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [RETIRA_I2, RETIRA_I2],
    })
    normal = srv.proyectos.crear("Banca", "proyecto normal")
    corpus = srv.proyectos.crear("Corpus", "corrida de evaluación", tipo="evaluacion")
    ids = [srv.procesar(SESION, normal.proyecto_id) for _ in range(3)]
    ids += [srv.procesar(SESION, corpus.proyecto_id) for _ in range(2)]
    srv.deps.embeddings = EmbeddingsQueNoSeUsan()

    etiquetas = [{"req_id": ids[3], "termino": "Sesion", "ambiguo": True, "tipo_ambiguedad": "lexica"},
                 {"req_id": ids[4], "termino": "sesión", "ambiguo": False, "tipo_ambiguedad": None},
                 {"req_id": "R99", "termino": "ahorita", "ambiguo": True, "tipo_ambiguedad": None},
                 {"req_id": ids[3]}]  # incompleta: se cuenta como inválida
    repo.guardar_doc(COLECCION_EVALUACIONES, "E01", {"evaluacion_id": "E01", "proyecto_id": corpus.proyecto_id,
                                                     "etiquetas": [{**etiquetas[0], "ambiguo": False}]})
    repo.guardar_doc(COLECCION_EVALUACIONES, "E02", {"evaluacion_id": "E02", "proyecto_id": corpus.proyecto_id,
                                                     "etiquetas": etiquetas})

    app = FastAPI()
    app.include_router(calibracion.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    return TestClient(app), srv, normal.proyecto_id, corpus.proyecto_id, ids


def obtener(cliente, ruta, **params):
    r = cliente.get(ruta, params=params)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    formas.Calibracion.model_validate(cuerpo)
    return cuerpo


def fila(cuerpo, umbral, clave="rejilla"):
    filas = cuerpo[clave] if clave == "rejilla" else cuerpo["con_ground_truth"]["por_umbral"]
    return next(f for f in filas if f["umbral"] == umbral)


def test_calibracion_de_un_proyecto(entorno):
    cliente, srv, normal, _, ids = entorno
    c = obtener(cliente, f"/proyectos/{normal}/calibracion")
    assert (c["proyecto_id"], c["umbral_configurado"], c["max_rondas"]) == (normal, 0.75, 2)
    assert c["parametros"] == {"desde": 0.5, "hasta": 0.95, "paso": 0.05}
    assert c["n_valores"] == 2 and [v["req_id"] for v in c["valores"]] == ids[:2]  # R03 no tiene similitud
    directo, debatido = c["valores"]
    assert (directo["termino"], directo["decision_real"], directo["via"]) == ("sesión", "aceptado_directo",
                                                                              "aceptado_directo")
    assert directo["similitud"] == pytest.approx(0.99873, abs=1e-5)
    assert (debatido["similitud"], debatido["decision_real"], debatido["via"]) == (0.0, "en_debate", "consenso")
    assert (debatido["tipo_ambiguedad"], debatido["estado_requisito"], debatido["umbral_usado"]) == \
        ("lexica", "pendiente_validacion", 0.75)

    assert [f["umbral"] for f in c["rejilla"]] == REJILLA_POR_OMISION
    assert all(f["configurado"] == (f["umbral"] == 0.75) for f in c["rejilla"])
    assert all((f["directos"], f["debates"], f["cambian"]) == (1, 1, []) for f in c["rejilla"])
    assert c["distribucion"]["bins"][0] == {"desde": 0.0, "hasta": 0.05, "n": 1}
    assert c["distribucion"]["bins"][-1] == {"desde": 0.95, "hasta": 1.0, "n": 1}
    assert c["con_ground_truth"] is None
    assert (c["umbrales_usados"], c["modelos_embeddings"]) == ([0.75], ["embeddings-falsos"])
    assert c["avisos"] == [] and c["nota"] == NOTA
    assert srv.deps.settings.similarity_threshold == 0.75  # nunca cambia la configuración


def test_rejilla_por_parametros_con_bordes_reales(entorno):
    cliente, _, normal, _, ids = entorno
    c = obtener(cliente, f"/proyectos/{normal}/calibracion", desde=0.0, hasta=1.0, paso=0.25)
    assert [f["umbral"] for f in c["rejilla"]] == [0.0, 0.25, 0.5, 0.75, 1.0]
    # 0.0 >= 0.0: con umbral 0 el término debatido se habría aceptado directo
    assert fila(c, 0.0)["cambian"] == [{"req_id": ids[1], "termino": "sesión", "similitud": 0.0,
                                        "decision_real": "en_debate", "decision_con_umbral": "aceptado_directo"}]
    assert [x["req_id"] for x in fila(c, 1.0)["cambian"]] == [ids[0]]  # 0.9987 < 1: se habría debatido
    assert fila(c, 0.75)["configurado"] and fila(c, 0.75)["cambian"] == []
    assert [b["n"] for b in c["distribucion"]["bins"]] == [1, 0, 0, 1]
    assert c["distribucion"]["bins"][-1] == {"desde": 0.75, "hasta": 1.0, "n": 1}


def test_calibracion_con_ground_truth(entorno):
    cliente, _, _, corpus, ids = entorno
    c = obtener(cliente, f"/proyectos/{corpus}/calibracion")
    assert [v["req_id"] for v in c["valores"]] == ids[3:]
    gt = c["con_ground_truth"]
    assert gt["fuentes"] == [{"proyecto_id": corpus, "evaluacion_id": "E02", "n_etiquetas": 3}]  # la más reciente
    assert (gt["n_invalidas"], gt["n_etiquetas"], gt["n_emparejados"], gt["n_ambiguos"], gt["n_no_ambiguos"]) == \
        (1, 3, 2, 1, 1)
    assert gt["etiquetas_sin_similitud"] == [{"req_id": "R99", "termino": "ahorita", "ambiguo": True,
                                              "tipo_ambiguedad": None}]
    assert gt["valores_sin_etiqueta"] == []
    assert gt["separacion"]["separa"] is True and gt["separacion"]["max_ambiguos"] == 0.0
    assert [f["umbral"] for f in gt["por_umbral"]] == REJILLA_POR_OMISION
    configurada = fila(c, 0.75, "gt")
    assert configurada["configurado"] and (configurada["vp"], configurada["vn"], configurada["f1"]) == (1, 1, 1.0)

    bordes = obtener(cliente, f"/proyectos/{corpus}/calibracion", desde=0.0, hasta=1.0, paso=0.5)
    cero, uno = fila(bordes, 0.0, "gt"), fila(bordes, 1.0, "gt")
    assert (cero["fn"], cero["precision"], cero["exhaustividad"], cero["f1"]) == (1, None, 0.0, None)
    assert cero["mal_separados"][0]["tipo_error"] == "falso_negativo"
    assert (uno["vp"], uno["fp"], uno["precision"], uno["exhaustividad"]) == (1, 1, 0.5, 1.0)


def test_calibracion_general_excluye_proyectos_de_evaluacion(entorno):
    cliente, _, _, _, ids = entorno
    c = obtener(cliente, "/calibracion")
    assert c["proyecto_id"] is None
    assert [v["req_id"] for v in c["valores"]] == ids[:2]
    assert c["con_ground_truth"] is None  # las etiquetas son del proyecto de evaluación


@pytest.mark.parametrize("params", [
    {"desde": 0.8, "hasta": 0.8},
    {"desde": 0.9, "hasta": 0.5},
    {"desde": 0.99},  # contra hasta = 0.95 de la configuración
    {"paso": 0},
    {"paso": -0.1},
    {"paso": 0.0005},  # bajo la resolución mínima: rejilla e histograma de miles de filas
    {"desde": 0.5, "hasta": 0.5000001, "paso": 1e-8},
    {"desde": 1.5},
    {"desde": -0.1},
    {"hasta": "x"},
])
def test_parametros_invalidos(entorno, params):
    cliente, _, normal, _, _ = entorno
    assert cliente.get(f"/proyectos/{normal}/calibracion", params=params).status_code == 422
    assert cliente.get("/calibracion", params=params).status_code == 422


def test_paso_minimo_es_valido(entorno):
    cliente, _, normal, _, _ = entorno
    c = obtener(cliente, f"/proyectos/{normal}/calibracion", desde=0.7, hasta=0.8, paso=0.001)
    umbrales = [f["umbral"] for f in c["rejilla"]]
    assert len(umbrales) == 101 and umbrales[0] == 0.7 and umbrales[-1] == 0.8 and 0.75 in umbrales
    assert len(c["distribucion"]["bins"]) == 999  # de [0.0, 0.001) a [0.998, 0.999): 0.0 y 0.9987


def test_proyecto_inexistente(entorno):
    cliente = entorno[0]
    assert cliente.get("/proyectos/P99/calibracion").status_code == 404


def test_proyecto_sin_trazas(entorno):
    cliente = entorno[0]
    c = obtener(cliente, "/proyectos/P00/calibracion")
    assert (c["n_valores"], c["distribucion"]["n"], c["con_ground_truth"]) == (0, 0, None)
    assert len(c["avisos"]) == 1
