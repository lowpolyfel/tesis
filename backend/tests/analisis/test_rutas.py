"""Rutas de lectura del módulo de análisis, con TestClient sobre una app mínima
que comparte el servicio del proyecto de dos ciclos."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analisis import (
    ambiguedades_proyecto,
    flujo_proyecto,
    leer_catalogos,
    resumen_proyecto,
    vista_requisito,
)
from app.api.routes import analisis, proyectos
from app.config import RAIZ_REPO


@pytest.fixture(scope="module")
def cliente(proyecto):
    srv = proyecto[0]
    app = FastAPI()
    app.include_router(analisis.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    return TestClient(app)


def test_requisito_devuelve_la_vista_sin_alterarla(cliente, proyecto):
    srv, repo, *_ = proyecto
    for req_id in ("R01", "R02", "R05", "R07"):
        r = cliente.get(f"/requisitos/{req_id}")
        assert r.status_code == 200
        assert r.json() == vista_requisito(srv.traza(req_id), repo.obtener_doc("formalizados", req_id))
    v = cliente.get("/requisitos/R02").json()
    assert v["formalizacion"]["requisito_reescrito"] and v["formalizacion"]["entradas_lel"] == ["sesión"]
    sesion = next(t for t in v["terminos"] if t["termino"] == "sesión")
    assert [i["estado"] for i in sesion["interpretaciones"]] == ["vigente", "retirada"]
    assert sesion["validacion"]["cambio"] == "eleccion"


@pytest.mark.parametrize("req_id", ["R99", "xyz", "R"])
def test_requisito_inexistente(cliente, req_id):
    assert cliente.get(f"/requisitos/{req_id}").status_code == 404


def test_rutas_de_proyecto(cliente, proyecto):
    _, repo, p, _ = proyecto
    trazas, lel = repo.trazas_completas(p.proyecto_id), repo.listar_lel(p.proyecto_id)
    base = f"/proyectos/{p.proyecto_id}"
    assert cliente.get(f"{base}/resumen").json() == json.loads(json.dumps(resumen_proyecto(p, trazas, lel)))
    assert cliente.get(f"{base}/ambiguedades").json() == ambiguedades_proyecto(trazas, lel)
    assert cliente.get(f"{base}/flujo").json() == flujo_proyecto(trazas, lel)
    for ruta in ("resumen", "ambiguedades", "flujo"):
        assert cliente.get(f"/proyectos/P99/{ruta}").status_code == 404


def test_proyecto_general_sin_requisitos(cliente):
    r = cliente.get("/proyectos/P00/resumen").json()
    assert r["proyecto"]["proyecto_id"] == "P00" and r["contadores"]["requisitos"] == 0
    assert cliente.get("/proyectos/P00/flujo").json()["ciclos"] == []


def test_configuracion_vigente(cliente, proyecto):
    srv = proyecto[0]
    c = cliente.get("/configuracion").json()
    assert (c["umbral"], c["max_rondas"], c["temperatura"], c["semilla"]) == (0.75, 2, 0.0, 42)
    assert c["modelos"]["critico"] == "ollama:qwen2.5:7b" and c["proveedor_critico"] == "ollama"
    assert c["modelo_embeddings"] == "nomic-embed-text" and c["significado_max_palabras"] == 12
    assert c["modelos_auxiliares"] == {"comparador": "qwen2.5:7b", "agente_unico": "qwen2.5:7b"}
    assert c["calibracion"]["umbrales"][0] == 0.5 and c["calibracion"]["umbrales"][-1] == 0.95
    assert c["comparacion"] == {"relacion_umbral": 0.6, "duplicado_umbral": 0.92, "max_pares": 60}
    assert c["catalogos"] == {"regionales": "v1-semilla", "vaguedad": "v1-semilla"}
    assert c["persistencia"] == srv.repo.descripcion and c["nota"] == "se cambia en .env; cada traza guarda la suya"


def test_catalogos_tal_cual(cliente):
    c = cliente.get("/catalogos").json()
    en_disco = {n: json.loads((RAIZ_REPO / "data" / "catalogos" / f"{n}.json").read_text(encoding="utf-8"))
                for n in ("regionales", "vaguedad")}
    assert c["regionales"] == en_disco["regionales"] and c["vaguedad"] == en_disco["vaguedad"]
    assert c["versiones"] == {"regionales": "v1-semilla", "vaguedad": "v1-semilla"} and c["nota"]
    assert "jalar" in [t["expresion"] for t in c["regionales"]["terminos"]]


def test_catalogo_ausente(tmp_path):
    (tmp_path / "vaguedad.json").write_text('{"version": "v9", "terminos": []}', encoding="utf-8")
    c = leer_catalogos(tmp_path)
    assert c["regionales"] is None and c["versiones"] == {"regionales": None, "vaguedad": "v9"}


def test_las_rutas_estan_en_la_app_real_con_sus_formas(proyecto):
    from app.api.main import create_app

    esquema = create_app(proyecto[0]).openapi()
    respuestas = {ruta: esquema["paths"][ruta]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
                  for ruta in ("/requisitos/{req_id}", "/proyectos/{proyecto_id}/resumen",
                               "/proyectos/{proyecto_id}/ambiguedades", "/proyectos/{proyecto_id}/flujo",
                               "/configuracion", "/catalogos")}
    assert respuestas["/requisitos/{req_id}"]["$ref"].endswith("/VistaRequisito")
    assert respuestas["/proyectos/{proyecto_id}/flujo"]["$ref"].endswith("/FlujoProyecto")
