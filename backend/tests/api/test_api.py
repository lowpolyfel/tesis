"""API con el servicio armado sobre dobles (LLM y embeddings falsos, JSON en tmp).

Con TestClient, las tareas en segundo plano terminan antes de que regrese la
petición, así que cada respuesta ya refleja el grafo ejecutado.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from tests.escenarios import guiones_sesion_cercana, montar
from tests.fakes import interp

SESION = "El sistema debe registrar la sesión del usuario."


@pytest.fixture
def cliente(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, guiones_sesion_cercana())
    with TestClient(create_app(srv)) as c:
        yield c


def eventos_sse(texto: str) -> list[tuple[str, dict]]:
    salida = []
    for bloque in texto.strip().split("\n\n"):
        campos = dict(linea.split(": ", 1) for linea in bloque.splitlines() if ": " in linea and not linea.startswith(":"))
        if "event" in campos:
            salida.append((campos["event"], json.loads(campos["data"])))
    return salida


def test_procesar_validar_y_lel(cliente):
    r = cliente.post("/procesar", json={"texto": f"  {SESION}  "})
    assert r.status_code == 202 and r.json() == {"req_id": "R01", "estado": "cargado"}

    t = cliente.get("/traza/R01").json()
    assert t["estado"] == "pendiente_validacion" and t["texto"] == SESION
    assert [m["tipo"] for m in t["mensajes"]][-1] == "solicitud_validacion"

    r = cliente.post("/validar/R01", json={"decision": "aprobar"})
    assert r.status_code == 202
    assert cliente.get("/traza/R01").json()["estado"] == "formalizado"
    lel = cliente.get("/lel").json()
    assert [(e["simbolo"], e["req_id"], e["via"]) for e in lel] == [("sesión", "R01", "aceptado_directo")]
    assert [(d["req_id"], d["estado"]) for d in cliente.get("/trazas").json()] == [("R01", "formalizado")]


def test_eventos_repite_la_traza_y_cierra_en_estado_terminal(cliente):
    cliente.post("/procesar", json={"texto": SESION})
    cliente.post("/validar/R01", json={"decision": "rechazar", "comentario": "no"})
    r = cliente.get("/eventos/R01")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = eventos_sse(r.text)
    mensajes = [d for e, d in ev if e == "mensaje"]
    assert [m["secuencia"] for m in mensajes] == list(range(1, len(mensajes) + 1))
    assert {m["tipo"] for m in mensajes} >= {"extraccion", "filtrado", "similitud", "validacion"}
    assert ev[-2] == ("estado", {"estado": "rechazado", "secuencia": len(mensajes)})
    assert ev[-1] == ("fin", {"estado": "rechazado"})

    # reconexión: Last-Event-ID evita repetir mensajes
    r = cliente.get("/eventos/R01", headers={"Last-Event-ID": str(len(mensajes) - 1)})
    assert [d["secuencia"] for e, d in eventos_sse(r.text) if e == "mensaje"] == [len(mensajes)]


def test_validar_con_edicion(cliente):
    cliente.post("/procesar", json={"texto": SESION})
    editada = interp("I1", "periodo autenticado", "El sistema debe registrar el periodo autenticado del usuario.")
    r = cliente.post("/validar/R01", json={"decision": "aprobar", "interpretaciones_editadas": {"sesión": editada}})
    assert r.status_code == 202
    entrada = cliente.get("/lel").json()[0]
    assert entrada["editada_por_humano"] and entrada["interpretacion"]["significado"] == "periodo autenticado"


def test_errores_http(cliente):
    assert cliente.get("/traza/R09").status_code == 404
    assert cliente.get("/eventos/R09").status_code == 404
    assert cliente.post("/validar/R09", json={"decision": "aprobar"}).status_code == 404
    assert cliente.post("/procesar", json={"texto": "   "}).status_code == 422

    cliente.post("/procesar", json={"texto": SESION})
    assert cliente.post("/validar/R01", json={"decision": "quizá"}).status_code == 422
    r = cliente.post("/validar/R01", json={"decision": "aprobar",
                                           "interpretaciones_editadas": {"usuario": interp("I1", "x", "y")}})
    assert r.status_code == 422 and "usuario" in r.json()["detail"]
    assert cliente.post("/validar/R01", json={"decision": "aprobar"}).status_code == 202
    assert cliente.post("/validar/R01", json={"decision": "aprobar"}).status_code == 409


def test_sandbox_y_salud(cliente):
    r = cliente.get("/sandbox")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert cliente.get("/", follow_redirects=False).headers["location"] == "/sandbox"
    salud = cliente.get("/salud").json()
    assert salud["persistencia"].startswith("json:") and salud["config"]["similarity_threshold"] == 0.75
