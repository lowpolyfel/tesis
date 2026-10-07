"""Una persona corrige un resultado ya formalizado (ADR 0017): el requisito reescrito,
su tipo y supuestos, y la entrada del LEL. Cada corrección queda en la traza."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import analisis, artefactos, proyectos, requisitos
from tests.escenarios import SESION, guiones_sesion_cercana, montar


@pytest.fixture
def entorno(tmp_path, analizador):
    guiones = {k: v * 2 for k, v in guiones_sesion_cercana().items()}
    srv, _, repo = montar(tmp_path, analizador, guiones, validacion_humana="si_hay_arbitraje")
    p = srv.proyectos.crear("Correcciones", contexto="Control de asistencia de una maquiladora.")
    req = srv.procesar(SESION, p.proyecto_id)
    app = FastAPI()
    for r in (requisitos.router, proyectos.router, artefactos.router, analisis.router):
        app.include_router(r)
    app.state.servicio = srv
    return TestClient(app), srv, repo, p.proyecto_id, req


def ediciones(srv, req):
    return [m for m in srv.traza(req).mensajes if m.tipo == "edicion"]


def test_corregir_el_requisito_formalizado(entorno):
    cliente, srv, repo, pid, req = entorno
    r = cliente.patch(f"/requisitos/{req}/formalizacion", json={
        "requisito_reescrito": "El sistema debe registrar la hora de entrada y salida de cada empleado.",
        "tipo_requisito": "no_funcional", "categoria": "fiabilidad", "supuestos": ["«sesión» es el turno"]})
    assert r.status_code == 200, r.text
    doc = repo.obtener_doc("formalizados", req)
    assert (doc["tipo_requisito"], doc["categoria"], doc["supuestos"]) == ("no_funcional", "fiabilidad", ["«sesión» es el turno"])
    assert doc["corregido"] and doc["requisito_reescrito"].startswith("El sistema debe registrar la hora")
    [m] = ediciones(srv, req)
    assert (m.emisor, m.receptor, m.payload["objeto"]) == ("humano", "sistema", "formalizacion")
    assert m.payload["antes"]["tipo_requisito"] == "funcional" and m.payload["despues"]["categoria"] == "fiabilidad"

    # volver a funcional borra la categoría; la especificación refleja la corrección
    assert cliente.patch(f"/requisitos/{req}/formalizacion", json={"tipo_requisito": "funcional"}).status_code == 200
    e = cliente.get(f"/proyectos/{pid}/especificacion").json()
    assert [(x["clave"], x["categoria"], x["corregido"] is not None) for x in e["funcionales"]] == [("RF-01", None, True)]
    assert len(ediciones(srv, req)) == 2

    # sin cambios no se registra nada
    cliente.patch(f"/requisitos/{req}/formalizacion", json={"tipo_requisito": "funcional"})
    assert len(ediciones(srv, req)) == 2
    v = cliente.get(f"/proyectos/{pid}/big-picture?req_ids={req}").json()
    assert v["panorama"]["requisitos"][0]["requisito_reescrito"].startswith("El sistema debe registrar la hora")


def test_corregir_la_entrada_del_lel(entorno):
    cliente, srv, repo, pid, req = entorno
    r = cliente.patch(f"/requisitos/{req}/lel/sesion", json={"simbolo": "turno", "nocion": ["Jornada de trabajo."]})
    assert r.status_code == 200, r.text
    [e] = repo.listar_lel(pid)
    assert (e.simbolo, e.nocion, e.termino) == ("turno", ["Jornada de trabajo."], "sesión") and e.corregida
    assert repo.obtener_doc("formalizados", req)["entradas_lel"] == ["turno"]
    [m] = ediciones(srv, req)
    assert m.payload["objeto"] == "lel" and m.payload["antes"]["simbolo"] == "sesión"
    # la vista del requisito y las del proyecto siguen armándose con el mensaje de edición en la traza
    v = cliente.get(f"/requisitos/{req}").json()
    assert v["validacion"]["automatica"] is True and v["validacion"]["motivo"] == "sin_arbitraje"
    assert v["config"]["contexto_proyecto"] == "Control de asistencia de una maquiladora."
    for ruta in ("especificacion", "resumen", "ambiguedades", "flujo"):
        assert cliente.get(f"/proyectos/{pid}/{ruta}").status_code == 200, ruta


def test_correcciones_invalidas(entorno, tmp_path):
    cliente, srv, _, pid, req = entorno
    assert cliente.patch("/requisitos/R99/formalizacion", json={"tipo_requisito": "funcional"}).status_code == 404
    assert cliente.patch(f"/requisitos/{req}/formalizacion", json={}).status_code == 422
    assert cliente.patch(f"/requisitos/{req}/formalizacion", json={"tipo_requisito": "deseable"}).status_code == 422
    assert cliente.patch(f"/requisitos/{req}/lel/bitacora", json={"tipo": "objeto"}).status_code == 404
    assert cliente.patch(f"/requisitos/{req}/lel/sesion", json={"nocion": []}).status_code == 422
    # un requisito que no está formalizado no se corrige
    evaluacion = srv.proyectos.crear("Corrida", tipo="evaluacion")
    pendiente = srv.procesar(SESION, evaluacion.proyecto_id)
    assert cliente.patch(f"/requisitos/{pendiente}/formalizacion", json={"tipo_requisito": "funcional"}).status_code == 409


def test_el_contexto_se_crea_y_se_edita_por_la_api(entorno):
    cliente, *_ = entorno
    p = cliente.post("/proyectos", json={"nombre": "Ferretería", "contexto": "  Punto de venta.  "}).json()
    assert p["contexto"] == "Punto de venta."
    assert cliente.patch(f"/proyectos/{p['proyecto_id']}", json={"contexto": "Inventario."}).json()["contexto"] == "Inventario."
    assert cliente.patch(f"/proyectos/{p['proyecto_id']}", json={"contexto": "x" * 4001}).status_code == 422
