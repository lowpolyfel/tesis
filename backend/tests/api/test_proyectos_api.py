"""Endpoints de proyectos y cola."""
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from tests.escenarios import SESION, guiones_sesion_cercana, montar


@pytest.fixture
def cliente(tmp_path, analizador):
    guiones = guiones_sesion_cercana()
    for clave in guiones:
        guiones[clave] = guiones[clave] * 3
    srv, _, _ = montar(tmp_path, analizador, guiones)
    with TestClient(create_app(srv)) as c:
        c.esperar = lambda: srv.cola.esperar(10)
        yield c


def test_crear_listar_y_cargar_requisitos(cliente):
    assert [p["proyecto_id"] for p in cliente.get("/proyectos").json()] == ["P00"]
    p = cliente.post("/proyectos", json={"nombre": "Banca", "descripcion": "app móvil"}).json()
    assert p["proyecto_id"] == "P01" and p["tipo"] == "normal"
    assert cliente.patch("/proyectos/P01", json={"nombre": "Banca en línea"}).json()["nombre"] == "Banca en línea"

    r = cliente.post("/proyectos/P01/requisitos", json={"requisitos": [
        {"texto": SESION, "origen": {"documento_id": "D01", "archivo": "srs.pdf", "pagina": 2, "indice": 1}},
        {"texto": SESION}]})
    assert r.status_code == 202 and r.json() == {"proyecto_id": "P01", "ciclo": 1, "req_ids": ["R01", "R02"]}
    cliente.esperar()
    lista = cliente.get("/proyectos/P01/requisitos").json()
    assert [(x["req_id"], x["proyecto_id"], x["ciclo"], x["estado"]) for x in lista] == [
        ("R01", "P01", 1, "pendiente_validacion"), ("R02", "P01", 1, "pendiente_validacion")]
    assert cliente.post("/proyectos/P01/requisitos", json={"requisitos": [{"texto": SESION}]}).json()["ciclo"] == 2
    cliente.esperar()
    assert cliente.get("/traza/R01").json()["origen"]["pagina"] == 2
    assert cliente.get("/trazas", params={"proyecto_id": "P00"}).json() == []
    assert cliente.get("/cola").json() == {"en_proceso": None, "pendientes": []}


def test_errores_de_proyecto(cliente):
    assert cliente.get("/proyectos/P42").status_code == 404
    assert cliente.post("/proyectos/P42/requisitos", json={"requisitos": [{"texto": "x"}]}).status_code == 404
    assert cliente.post("/proyectos", json={"nombre": " "}).status_code == 422
    assert cliente.post("/proyectos/P00/requisitos", json={"requisitos": []}).status_code == 422
