"""Rutas de corpus y evaluación con TestClient (grafo real, LLM y embeddings falsos)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import evaluacion
from app.api.routes import evaluaciones, proyectos
from app.evaluacion import formas
from tests.escenarios import montar
from tests.evaluacion.ayudantes import GROUND_TRUTH, REQUISITOS, escribir_corpus, guiones


def cliente_de(srv) -> TestClient:
    app = FastAPI()
    app.include_router(evaluaciones.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    return TestClient(app)


@pytest.fixture
def entorno(tmp_path, analizador):
    srv, llm, repo = montar(tmp_path, analizador, guiones(), corpus_dir=str(tmp_path / "corpus"))
    escribir_corpus(tmp_path / "corpus", "escenario", descripcion={"descripcion": "cuatro casos", "ejemplo": True})
    escribir_corpus(tmp_path / "corpus", "roto", REQUISITOS, GROUND_TRUTH[:3])
    yield cliente_de(srv), srv
    srv.detener()


def test_corpus_disponibles_y_detalle(entorno):
    c, _ = entorno
    r = c.get("/corpus")
    assert r.status_code == 200
    escenario, roto = [formas.ResumenCorpus.model_validate(x) for x in r.json()]
    assert (escenario.nombre, escenario.valido, escenario.ejemplo, escenario.conteo.n_requisitos) == ("escenario", True,
                                                                                                      True, 4)
    assert (roto.nombre, roto.valido, roto.errores) == ("roto", False, ["requisitos sin ground truth: D"])

    r = c.get("/corpus/escenario")
    assert r.status_code == 200
    d = formas.DetalleCorpus.model_validate(r.json())
    assert [(it.id, it.ground_truth.ambiguo) for it in d.items] == [("A", True), ("B", True), ("C", True), ("D", False)]
    assert d.descripcion == "cuatro casos" and d.conteo.n_sin_ambiguedad == 1

    r = c.get("/corpus/roto")
    assert r.status_code == 422
    assert r.json()["detail"] == {"mensaje": "El corpus «roto» no es válido", "errores": ["requisitos sin ground truth: D"]}
    assert c.get("/corpus/no-existe").status_code == 404
    assert c.get("/corpus/..%2Fresultados").status_code == 404


def test_crear_errores(entorno):
    c, srv = entorno
    assert c.post("/evaluaciones", json={"corpus": "no-existe"}).status_code == 404
    r = c.post("/evaluaciones", json={"corpus": "roto"})
    assert r.status_code == 422 and r.json()["detail"]["errores"] == ["requisitos sin ground truth: D"]
    assert c.post("/evaluaciones", json={"corpus": "../corpus"}).status_code == 422
    assert c.post("/evaluaciones", json={"corpus": "escenario", "otro": 1}).status_code == 422
    assert c.post("/evaluaciones", json={"corpus": "escenario", "nombre": ""}).status_code == 422
    cliente = srv.deps.llm_agente_unico
    srv.deps.llm_agente_unico = None
    try:
        r = c.post("/evaluaciones", json={"corpus": "escenario"})
        assert r.status_code == 503 and "AGENTE_UNICO_MODEL" in r.json()["detail"]
    finally:
        srv.deps.llm_agente_unico = cliente
    # ninguno de los intentos fallidos dejó proyectos, requisitos ni evaluaciones
    assert [p.proyecto_id for p in srv.proyectos.listar()] == ["P00"]
    assert srv.trazas() == [] and c.get("/evaluaciones").json() == []
    assert c.get("/evaluaciones/E99").status_code == 404


def test_flujo_completo_por_la_cola(entorno):
    c, srv = entorno
    r = c.post("/evaluaciones", json={"corpus": "escenario", "nombre": "Primera corrida"})
    assert r.status_code == 202
    assert r.json() == {"evaluacion_id": "E01", "proyecto_id": "P01", "total": 4}

    # sin trabajador todavía: nada corrió
    r = c.get("/evaluaciones/E01")
    assert r.status_code == 200
    en_cola = formas.InformeEvaluacion.model_validate(r.json())
    assert (en_cola.estado, en_cola.nombre, en_cola.ejemplo) == ("en_proceso", "Primera corrida", True)
    assert en_cola.progreso.model_dump() == {"total": 4, "listos_sistema": 0, "listos_linea_base": 0}
    assert en_cola.resumen.sistema.n == 0 and en_cola.resumen.sistema.deteccion.precision is None
    assert en_cola.etiquetas == [] and not any(f.sistema.listo for f in en_cola.requisitos)
    assert en_cola.avisos[:2] == [
        "corpus de EJEMPLO: muestra el formato, no es el corpus de la tesis; sus resultados no se reportan",
        "evaluación incompleta: sistema 0/4, línea base 0/4; cada resumen cubre solo los requisitos listos de su lado"]

    srv.cola.iniciar()
    assert srv.cola.esperar(20)
    r = c.get("/evaluaciones/E01")
    informe = formas.InformeEvaluacion.model_validate(r.json())
    assert informe.estado == "terminada"
    assert informe.progreso.model_dump() == {"total": 4, "listos_sistema": 4, "listos_linea_base": 4}
    assert informe.resumen.sistema.deteccion.f1 == 0.888889 and informe.resumen.linea_base.deteccion.f1 == 0.666667
    assert len(informe.etiquetas) == 8

    [resumen] = c.get("/evaluaciones").json()
    assert formas.ResumenEvaluacion.model_validate(resumen).estado == "terminada"
    assert c.get("/proyectos/P01").json()["tipo"] == "evaluacion"
    assert [t["origen"]["marca"] for t in c.get("/proyectos/P01/requisitos").json()] == ["A", "B", "C", "D"]

    # una segunda corrida del mismo corpus es otro proyecto y otra evaluación, la más reciente primero
    assert c.post("/evaluaciones", json={"corpus": "escenario"}).json() == {"evaluacion_id": "E02",
                                                                             "proyecto_id": "P02", "total": 4}
    assert srv.cola.esperar(20)
    assert [e["evaluacion_id"] for e in c.get("/evaluaciones").json()] == ["E02", "E01"]


def test_recuperar_tras_reinicio(tmp_path, analizador):
    """Si el servidor se cae con la evaluación a medias, los grafos los retoma el servicio y la
    línea base que faltaba la vuelve a encolar `evaluacion.recuperar`."""
    srv, _, _ = montar(tmp_path, analizador, guiones(), corpus_dir=str(tmp_path / "corpus"))
    escribir_corpus(tmp_path / "corpus", "escenario")
    ev = evaluacion.crear(srv, "escenario")  # registrada pero sin línea base encolada ni trabajador

    reiniciado, _, _ = montar(tmp_path, analizador, guiones(), corpus_dir=str(tmp_path / "corpus"))
    reiniciado.iniciar()
    try:
        assert evaluacion.recuperar(reiniciado) == [ev.evaluacion_id]
        assert reiniciado.cola.esperar(20)
        informe = evaluacion.informe(reiniciado, ev.evaluacion_id)
        assert informe["estado"] == "terminada"
        assert informe["resumen"]["sistema"]["deteccion"]["f1"] == 0.888889
        assert evaluacion.recuperar(reiniciado) == []  # terminada: no se vuelve a encolar
    finally:
        reiniciado.detener()


def test_tras_un_reinicio_el_informe_vuelve_a_encolar_la_linea_base(tmp_path, analizador):
    """Sin `evaluacion.recuperar` al arrancar, la línea base perdida en la cola la vuelve a
    encolar la primera consulta del informe, una sola vez."""
    srv, _, _ = montar(tmp_path, analizador, guiones(), corpus_dir=str(tmp_path / "corpus"))
    escribir_corpus(tmp_path / "corpus", "escenario")
    ev = evaluacion.crear(srv, "escenario")  # el proceso se cae antes de encolar la línea base

    reiniciado, llm, _ = montar(tmp_path, analizador, guiones(), corpus_dir=str(tmp_path / "corpus"))
    reiniciado.recuperar()  # lo que hace `Servicio.iniciar`: retoma los grafos, no la línea base
    c = cliente_de(reiniciado)
    try:
        for _ in range(2):
            r = c.get(f"/evaluaciones/{ev.evaluacion_id}")
            assert r.status_code == 200 and r.json()["estado"] == "en_proceso"
        claves = [t["clave"] for t in reiniciado.cola.estado()["pendientes"]]
        assert claves == ["R01", "R02", "R03", "R04", "E01:A", "E01:B", "E01:C", "E01:D", "E01"]

        reiniciado.cola.iniciar()
        assert reiniciado.cola.esperar(20)
        informe = formas.InformeEvaluacion.model_validate(c.get(f"/evaluaciones/{ev.evaluacion_id}").json())
        assert informe.estado == "terminada" and informe.resumen.sistema.deteccion.f1 == 0.888889
        assert len(llm.llamadas["agente_unico_v1"]) == 5  # una por requisito y el reintento de D
        c.get(f"/evaluaciones/{ev.evaluacion_id}")
        assert reiniciado.cola.estado()["pendientes"] == []  # terminada: no se vuelve a encolar
    finally:
        reiniciado.detener()


def test_al_arrancar_la_api_retoma_las_evaluaciones_pendientes(tmp_path, analizador):
    """Con la API real, el lifespan del router llama a `evaluacion.recuperar`: la evaluación
    a medias termina sin que nadie consulte su informe."""
    from app.api.main import create_app

    srv, _, _ = montar(tmp_path, analizador, guiones(), corpus_dir=str(tmp_path / "corpus"))
    escribir_corpus(tmp_path / "corpus", "escenario")
    ev = evaluacion.crear(srv, "escenario")  # el proceso se cae antes de encolar la línea base

    reiniciado, llm, _ = montar(tmp_path, analizador, guiones(), corpus_dir=str(tmp_path / "corpus"))
    with TestClient(create_app(reiniciado)):
        assert reiniciado.cola.esperar(20)
        assert evaluacion.obtener(reiniciado, ev.evaluacion_id).estado == "terminada"
    assert len(llm.llamadas["agente_unico_v1"]) == 5  # una por requisito y el reintento de D: nada doble
