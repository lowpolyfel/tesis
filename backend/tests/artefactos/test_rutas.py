"""Rutas de artefactos con TestClient sobre una app mínima y un repositorio JSON
sembrado a mano con el proyecto de ejemplo."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import artefactos, proyectos
from app.artefactos import artefactos_requisito, big_picture_proyecto, metas_proyecto
from tests.artefactos.ayudantes import documentos, lel, sembrar
from tests.escenarios import montar


@pytest.fixture(scope="module")
def entorno(tmp_path_factory, analizador):
    srv, _, repo = montar(tmp_path_factory.mktemp("artefactos"), analizador, {})
    p = srv.proyectos.crear("Artefactos")
    sembrar(repo, p.proyecto_id)
    vacio = srv.proyectos.crear("Sin formalizados")
    app = FastAPI()
    app.include_router(artefactos.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    return TestClient(app), srv, repo, p.proyecto_id, vacio.proyecto_id


def _insumos(repo, pid):
    return repo.listar_docs("formalizados", proyecto_id=pid), repo.listar_lel(pid), repo.listar_trazas(pid)


def test_metas_del_proyecto(entorno):
    cliente, srv, repo, pid, _ = entorno
    r = cliente.get(f"/proyectos/{pid}/metas")
    assert r.status_code == 200
    formalizados, entradas, trazas = _insumos(repo, pid)
    assert r.json() == metas_proyecto(formalizados, entradas, trazas, srv.deps.analizador)
    m = r.json()
    assert [x["id"] for x in m["metas"]] == ["R01.M1", "R01.M2", "R02.M1", "R02.M2", "R03.M1", "R03.M2", "R03.M3"]
    # el servicio tiene spaCy: «Los Usuarios» se une al sujeto «usuario» del LEL
    assert [a["nombre"] for a in m["actores"]] == ["administrador", "sistema", "usuario"]
    assert [(f["req_id"], f["motivo"]) for f in m["requisitos_fuera"]] == [
        ("R04", "en_proceso"), ("R05", "rechazado"), ("R06", "reprocesado"), ("R07", "en_proceso"),
        ("R08", "sin_formalizacion"), ("R09", "sin_traza")]


def test_big_picture_del_proyecto(entorno):
    cliente, srv, repo, pid, _ = entorno
    r = cliente.get(f"/proyectos/{pid}/big-picture")
    assert r.status_code == 200
    formalizados, entradas, trazas = _insumos(repo, pid)
    bp = r.json()
    assert bp == big_picture_proyecto(formalizados, entradas, trazas, srv.deps.analizador)
    assert {"R01", "R02", "R03", "simbolo:sesion", "actor:usuario"} <= {n["id"] for n in bp["nodos"]}
    assert bp["panorama"]["dependencias"] == [{"de": "R01", "a": "R02", "por": "usuario"},
                                              {"de": "R03", "a": "R01", "por": "sesión"}]
    assert bp["mermaid"].startswith("flowchart LR\n") and bp["plantuml"].startswith("@startuml\n")
    assert cliente.get(f"/proyectos/{pid}/big-picture").json() == bp


def test_artefactos_de_un_requisito(entorno):
    cliente, srv, _, pid, _ = entorno
    r = cliente.get("/requisitos/R02/artefactos")
    assert r.status_code == 200
    a = r.json()
    assert a == artefactos_requisito("R02", pid, "formalizado", documentos(pid)[1], lel(pid), srv.deps.analizador)
    assert a["formalizado"]["requisito_reescrito"] == documentos(pid)[1]["requisito_reescrito"]
    assert [e["simbolo"] for e in a["entradas_lel"]] == ["usuario", "bitácora"]
    assert [(m["id"], m["actor"]) for m in a["metas"]] == [("R02.M1", "usuario"), ("R02.M2", None)]

    en_debate = cliente.get("/requisitos/R04/artefactos").json()
    assert (en_debate["estado"], en_debate["formalizado"], en_debate["entradas_lel"], en_debate["metas"]) == (
        "en_debate", None, [], [])
    anterior = cliente.get("/requisitos/R08/artefactos").json()
    assert anterior["formalizado"] is None and [e["simbolo"] for e in anterior["entradas_lel"]] == ["expediente"]


@pytest.mark.parametrize("ruta", ["/requisitos/R99/artefactos", "/requisitos/xyz/artefactos",
                                  "/proyectos/P99/metas", "/proyectos/P99/big-picture"])
def test_inexistentes(entorno, ruta):
    assert entorno[0].get(ruta).status_code == 404


def test_proyecto_sin_formalizados(entorno):
    cliente, *_, vacio = entorno
    m = cliente.get(f"/proyectos/{vacio}/metas").json()
    assert m["metas"] == [] and m["actores"] == [] and m["requisitos_fuera"] == []
    assert set(m["por_tipo"].values()) == {0}
    bp = cliente.get(f"/proyectos/{vacio}/big-picture").json()
    assert bp["nodos"] == [] and bp["aristas"] == [] and bp["panorama"]["requisitos"] == []
    assert cliente.get("/proyectos/P00/big-picture").status_code == 200
