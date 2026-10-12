"""Cancelar el análisis y descartar los requisitos por completo: los que esperan turno se
borran ya; el que corre se detiene antes del nodo siguiente y se borra; los demás, también."""
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import proyectos
from app.models import Estado
from tests.escenarios import SESION, guiones_sesion_cercana, montar
from tests.fakes import como_usuario


def test_la_cola_quita_los_pendientes():
    from app.orchestration.cola import Cola
    c = Cola()
    for clave in ("R1", "R2", "R3"):
        c.encolar("ejecutar", clave, lambda: None)
    assert c.quitar({"R2", "R9"}) == {"R2"}
    assert [t["clave"] for t in c.estado()["pendientes"]] == ["R1", "R3"]
    c.iniciar()
    assert c.esperar(5)  # el contador de pendientes cuadra
    c.detener()


def test_en_cola_y_terminado_se_descartan(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, guiones_sesion_cercana(), validacion_humana="si_hay_arbitraje")
    hecho = srv.procesar(SESION)
    assert srv.traza(hecho).estado == Estado.FORMALIZADO
    _, (en_cola,) = srv.solicitar_lote([(SESION, None)], "P00")  # la cola no está corriendo
    r = srv.cancelar("P00", [en_cola, hecho])
    assert r == {"descartados": [en_cola, hecho], "deteniendo": []}
    assert repo.obtener_traza(en_cola) is None and repo.obtener_traza(hecho) is None
    assert repo.obtener_doc("formalizados", hecho) is None and repo.listar_lel() == []
    assert srv.cola.estado()["pendientes"] == []
    with pytest.raises(ValueError, match="no es un requisito de este proyecto"):
        srv.cancelar("P00", ["R99"])


def test_el_que_corre_se_detiene_antes_del_nodo_siguiente(tmp_path, analizador):
    guiones = guiones_sesion_cercana()
    entra, sigue = threading.Event(), threading.Event()
    extraccion = guiones["extractor_v1"][0]

    def extractor_lento(prompt):  # el Extractor está «llamando al modelo» cuando llega la cancelación
        entra.set()
        sigue.wait(5)
        return extraccion
    guiones["extractor_v1"] = extractor_lento
    srv, llm, repo = montar(tmp_path, analizador, guiones, validacion_humana="si_hay_arbitraje")
    req = srv.registrar(SESION)
    hilo = threading.Thread(target=srv.ejecutar, args=(req,))
    hilo.start()
    assert entra.wait(5)
    assert srv.cancelar("P00", [req]) == {"descartados": [], "deteniendo": [req]}
    sigue.set()
    hilo.join(10)
    assert repo.obtener_traza(req) is None  # se borró al terminar el paso en curso
    assert "clasificador_v3" not in llm.llamadas  # no siguió al Clasificador
    assert req not in srv._cancelados and req not in srv._ocupados


def test_ruta(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, guiones_sesion_cercana())
    app = como_usuario(FastAPI())
    app.include_router(proyectos.router)
    app.state.servicio = srv
    c = TestClient(app)
    ids = c.post("/proyectos/P00/requisitos", json={"requisitos": [{"texto": SESION}]}).json()["req_ids"]
    r = c.post("/proyectos/P00/cancelar", json={"req_ids": ids})
    assert r.status_code == 200 and r.json() == {"descartados": ids, "deteniendo": []}
    assert repo.obtener_traza(ids[0]) is None
    assert c.post("/proyectos/P00/cancelar", json={"req_ids": ["R77"]}).status_code == 422
