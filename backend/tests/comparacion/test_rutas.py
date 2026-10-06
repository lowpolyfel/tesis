"""Rutas de comparaciones con TestClient sobre una app mínima; la corrida pasa por la cola."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import comparaciones, proyectos
from app.models import Estado
from tests.comparacion.ayudantes import juicio, montar_comparacion, requisito

CIERRE_15 = "La sesión del usuario debe cerrarse a los 15 minutos de inactividad."
SIN_CIERRE = "La sesión del usuario nunca debe cerrarse automáticamente."


@pytest.fixture
def entorno(tmp_path, analizador):
    juicios = {("R01", "R02"): juicio("contradiccion", "debe cerrarse a los 15 minutos", "nunca debe cerrarse")}
    srv, llm, repo, pid = montar_comparacion(tmp_path, analizador, juicios=juicios,
                                             vectores={CIERRE_15: [1, 0, 0], SIN_CIERRE: [0.8, 0.6, 0]})
    app = FastAPI()
    app.include_router(comparaciones.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    yield srv, repo, pid, TestClient(app)
    srv.cola.detener()


def test_solicitar_encola_y_la_cola_la_termina(entorno):
    srv, repo, pid, cliente = entorno
    requisito(repo, pid, CIERRE_15)
    requisito(repo, pid, SIN_CIERRE)

    r = cliente.post(f"/proyectos/{pid}/comparaciones")
    assert r.status_code == 202 and r.json() == {"comparacion_id": "C01", "estado": "en_cola"}
    en_cola = cliente.get("/comparaciones/C01").json()
    assert en_cola["estado"] == "en_cola" and en_cola["hallazgos"] == [] and en_cola["terminado"] is None
    assert srv.cola.estado()["pendientes"] == [{"tipo": "analisis", "clave": "C01"}]

    srv.cola.iniciar()
    assert srv.cola.esperar(10)
    c = cliente.get("/comparaciones/C01").json()
    assert c["estado"] == "terminada" and c["error"] is None
    assert set(c) == {"comparacion_id", "proyecto_id", "estado", "creado", "terminado", "config", "requisitos",
                      "excluidos", "pares_totales", "pares_candidatos", "pares_evaluados", "pares_fuera_por_limite",
                      "fuera_por_limite", "pares_con_error", "avance", "matriz_similitud", "hallazgos",
                      "relaciones_por_par", "error"}
    assert c["requisitos"] == [{"req_id": "R01", "base": "original", "texto": CIERRE_15},
                               {"req_id": "R02", "base": "original", "texto": SIN_CIERRE}]
    [h] = c["hallazgos"]
    assert h["tipo"] == "contradiccion" and [e["verificada"] for e in h["evidencia"]] == [True, True]
    assert c["relaciones_por_par"][0]["relacion"] == "contradiccion"


def test_listar_mas_reciente_primero(entorno):
    srv, repo, pid, cliente = entorno
    requisito(repo, pid, CIERRE_15)
    requisito(repo, pid, SIN_CIERRE)
    assert cliente.get(f"/proyectos/{pid}/comparaciones").json() == []
    for _ in range(2):
        assert cliente.post(f"/proyectos/{pid}/comparaciones").status_code == 202
    srv.cola.iniciar()
    assert srv.cola.esperar(10)
    lista = cliente.get(f"/proyectos/{pid}/comparaciones").json()
    assert [x["comparacion_id"] for x in lista] == ["C02", "C01"]
    assert set(lista[0]) == {"comparacion_id", "proyecto_id", "estado", "creado", "terminado", "config", "n_requisitos",
                             "pares_evaluados", "pares_fuera_por_limite", "pares_con_error", "hallazgos_por_tipo",
                             "error"}
    assert lista[0]["n_requisitos"] == 2 and lista[0]["hallazgos_por_tipo"]["contradiccion"] == 1
    assert cliente.get("/proyectos/P00/comparaciones").json() == []


def test_errores_de_la_api(entorno):
    srv, repo, pid, cliente = entorno
    assert cliente.post("/proyectos/P99/comparaciones").status_code == 404
    assert cliente.get("/proyectos/P99/comparaciones").status_code == 404
    for cid in ("C99", "xyz"):
        assert cliente.get(f"/comparaciones/{cid}").status_code == 404
    requisito(repo, pid, CIERRE_15)
    requisito(repo, pid, SIN_CIERRE, Estado.RECHAZADO)
    r = cliente.post(f"/proyectos/{pid}/comparaciones")
    assert r.status_code == 422 and "al menos 2" in r.json()["detail"]
    assert cliente.get(f"/proyectos/{pid}/comparaciones").json() == []
