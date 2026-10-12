"""Volver a analizar requisitos que terminaron en error por algo ajeno al texto: una versión
nueva (reproceso) con su texto, origen y triaje; la del error se conserva y deja de contar."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analisis import resumen_proyecto
from app.api.routes import proyectos
from app.models import Estado, Origen
from tests.escenarios import SESION, guiones_sesion_cercana, montar
from tests.fakes import como_usuario


@pytest.fixture
def entorno(tmp_path, analizador):
    # sin guiones el Extractor falla: la traza termina en error, como con una clave sin acceso
    srv, llm, _ = montar(tmp_path, analizador, {}, validacion_humana="si_hay_arbitraje")
    req = srv.registrar(SESION, origen=Origen(archivo="srs.pdf", pagina=2), triaje={"veredicto": "claro"})
    srv.ejecutar(req)
    assert srv.traza(req).estado == Estado.ERROR
    return srv, llm, req


def test_reanalizar_crea_una_version_nueva(entorno):
    srv, llm, req = entorno
    llm.guiones.update(guiones_sesion_cercana())  # ahora sí responde (la clave ya sirve)
    ciclo, (nuevo,) = srv.reanalizar("P00", [req])
    srv.ejecutar(nuevo)
    t = srv.traza(nuevo)
    assert t.estado == Estado.FORMALIZADO and t.texto == SESION and ciclo == 2
    assert (t.origen.reproceso_de, t.origen.archivo, t.origen.pagina) == (req, "srs.pdf", 2)
    assert t.config["triaje"] == {"veredicto": "claro"}
    assert srv.traza(req).estado == Estado.ERROR  # el historial se conserva
    assert srv.reemplazados("P00") == {req: nuevo}

    r = resumen_proyecto(srv.proyectos.obtener("P00"), [srv.traza(x) for x in (req, nuevo)], [])
    assert r["contadores"]["errores"] == 0
    assert {x["req_id"]: x["reemplazado_por"] for x in r["requisitos"]} == {req: nuevo, nuevo: None}


def test_reglas(entorno):
    srv, _, req = entorno
    srv.reanalizar("P00", [req])
    with pytest.raises(ValueError, match="ya se volvió a analizar"):
        srv.reanalizar("P00", [req])
    otro = srv.proyectos.crear("Otro")
    with pytest.raises(ValueError, match="no es un requisito de este proyecto"):
        srv.reanalizar(otro.proyecto_id, [req])


def test_ruta(entorno):
    srv, _, req = entorno
    app = como_usuario(FastAPI())
    app.include_router(proyectos.router)
    app.state.servicio = srv
    c = TestClient(app)
    r = c.post("/proyectos/P00/reanalizar", json={"req_ids": [req]})
    assert r.status_code == 202 and len(r.json()["req_ids"]) == 1
    nuevo = r.json()["req_ids"][0]
    assert c.post("/proyectos/P00/reanalizar", json={"req_ids": [req]}).status_code == 422
    srv.cola.detener()
    assert srv.repo.obtener_traza(nuevo).estado in (Estado.CARGADO, Estado.ERROR, Estado.FORMALIZADO, Estado.EXTRAIDO)
