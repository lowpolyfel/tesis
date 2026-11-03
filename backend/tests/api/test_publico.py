"""Servidor de publicación: la interfaz compilada en / y la API en /api."""
from fastapi.testclient import TestClient

from app.api.publico import crear_publico


def _dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Dudamel</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path.parent / "secreto.txt").write_text("no")
    return tmp_path


def test_sirve_la_interfaz_y_las_rutas_de_react(tmp_path):
    c = TestClient(crear_publico(_dist(tmp_path)))  # sin `with`: no arranca la cola
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert "Dudamel" in c.get("/proyectos/abc/lexico").text
    assert "Dudamel" in c.get("/").text
    assert c.get("/salud").json() == {"ok": True}


def test_no_sale_de_la_carpeta_de_la_interfaz(tmp_path):
    c = TestClient(crear_publico(_dist(tmp_path)))
    r = c.get("/%2e%2e/secreto.txt")
    assert "no" != r.text and "Dudamel" in r.text


def test_la_api_va_bajo_api(tmp_path):
    c = TestClient(crear_publico(_dist(tmp_path)))
    r = c.get("/api/openapi.json")  # el esquema de la API, no el index.html de la interfaz
    assert r.status_code == 200 and "/proyectos" in r.json()["paths"]


def test_sin_compilar_avisa(tmp_path):
    c = TestClient(crear_publico(tmp_path / "no-existe"))
    assert c.get("/").status_code == 503
