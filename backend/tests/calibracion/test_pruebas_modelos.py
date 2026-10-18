"""Prueba de modelos con el banco de términos ambiguos (ADR 0027)."""
from __future__ import annotations

import io
import re
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.calibracion import pruebas_modelos as pm
from app.calibracion.latex_modelos import paquete_overleaf
from tests.fakes import LLMFalso, como_usuario
from tests.fases.escenario import montar


def test_el_banco_v1_tiene_50_terminos_ambiguos_bien_formados():
    b = pm.banco("v1")
    ids = [t["id"] for t in b["terminos"]]
    assert len(ids) == 50 and ids == [f"B{i:02d}" for i in range(1, 51)]
    assert len({t["termino"].lower() for t in b["terminos"]}) == 50
    for t in b["terminos"]:
        assert t["clase"] in b["clases"] and len(t["lecturas"]) >= 2 and pm.es_ambiguo(t)
        assert t["termino"].split()[-1].lower()[:4] in t["cita"].lower(), t["id"]  # el término aparece en su cita
    assert len(b["huella"]) == 64


def test_el_banco_v2_suma_controles_inequivocos_sin_tocar_los_50_ambiguos():
    v1, v2 = pm.banco("v1"), pm.banco()
    assert v2["version"] == "v2" and v2["versiones"] == ["v1", "v2"] and v1["huella"] != v2["huella"]
    terminos = {t["id"]: t for t in v2["terminos"]}
    assert [{k: v for k, v in t.items() if k != "ambiguo"} for t in v2["terminos"][:50]] == v1["terminos"]
    negativos = [t for t in v2["terminos"] if not pm.es_ambiguo(t)]
    assert len(v2["terminos"]) == 73 and len(negativos) == 23  # con n < 20 la tasa de falsas alarmas no sirve
    assert len({t["termino"].lower() for t in v2["terminos"]}) == 73
    for t in negativos:
        assert t["clase"] == "inequivoco" and len(t["lecturas"]) == 1
        assert t["termino"].split()[-1].lower()[:4] in t["cita"].lower(), t["id"]
        if t["pareja"]:  # su pareja es un ambiguo del mismo dominio
            assert pm.es_ambiguo(terminos[t["pareja"]]) and terminos[t["pareja"]]["dominio"] == t["dominio"], t["id"]
    assert terminos["B63"]["termino"] == "caja registradora" and terminos["B63"]["pareja"] == "B16"


def test_wilson_y_mcnemar():
    w = pm.wilson(8, 10)
    assert w["valor"] == 0.8 and 0.490 < w["bajo"] < 0.491 and 0.943 < w["alto"] < 0.944
    assert pm.wilson(0, 5)["bajo"] == 0 and pm.wilson(5, 5)["alto"] == 1 and pm.wilson(0, 0)["valor"] is None
    assert pm.mcnemar(0, 0) is None
    assert pm.mcnemar(5, 5) == 1.0
    assert pm.mcnemar(0, 6) == pytest.approx(2 / 64)


def _respuesta(n):
    def responder(prompt):
        termino = re.search(r'"termino": "([^"]+)"', prompt.usuario).group(1)
        intenciones = [{"id": f"I{k}", "significado": f"sentido {k} de {termino}", "intencion": "registrar algo",
                        "parafrasis": f"cita con el sentido {k}"} for k in range(1, n + 1)]
        return {"resultados": [{"termino": termino, "tipo_ambiguedad": "lexica" if n > 1 else None, "intenciones": intenciones}]}
    return responder


@pytest.fixture
def cliente(tmp_path, analizador, monkeypatch):
    srv, _, _ = montar(tmp_path, analizador)
    falsos = {"bueno": LLMFalso({"clasificador_intencion_v1": _respuesta(2)}, "ollama-bueno"),
              "flojo": LLMFalso({"clasificador_intencion_v1": _respuesta(1)}, "ollama-flojo"),
              "roto": LLMFalso({"clasificador_intencion_v1": lambda p: "no es json"}, "ollama-roto")}
    monkeypatch.setattr(pm, "crear_cliente_de", lambda e, s: falsos[e["modelo"]])
    with TestClient(como_usuario(create_app(srv))) as c:
        c.srv = srv
        yield c


def _esperar(c, prueba_id, segundos=10):
    fin = time.monotonic() + segundos
    while pm.EJECUTOR.activa(prueba_id):
        assert time.monotonic() < fin, "la prueba no terminó"
        time.sleep(0.02)
    return c.get(f"/pruebas-modelos/{prueba_id}").json()


def test_correr_revisar_y_exportar_una_prueba(cliente):
    c = cliente
    assert len(c.get("/bancos/ambiguedad").json()["terminos"]) == 73  # el más nuevo: v2
    r = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"},
                                                      {"proveedor": "ollama", "modelo": "flojo"},
                                                      {"proveedor": "ollama", "modelo": "roto"}],
                                         "items": ["B03", "B01", "B40", "B33"], "nota": "primera"})
    assert r.status_code == 201, r.text
    pid = r.json()["prueba_id"]
    assert r.json()["items"] == ["B01", "B03", "B33", "B40"]  # en el orden del banco

    p = _esperar(c, pid)
    assert p["estado"] == "terminada" and p["avance"] == {"hechos": 12, "total": 12}
    m1, m2, m3 = p["resumen"]["modelos"]
    assert m1["deteccion"]["valor"] == 1 and m1["intenciones_media"] == 2
    assert m2["deteccion"]["valor"] == 0
    assert m3["errores"] == 4 and m3["deteccion"]["valor"] == 0 and p["resultados"]["M3"]["B01"]["intentos"] == 2
    assert m1["por_clase"]["polisemia"]["n"] == 2 and m1["por_clase"]["regionalismo"]["n"] == 2
    assert any("error" in a for a in p["resumen"]["avisos"]) and any("Solo 4" in a for a in p["resumen"]["avisos"])

    for item in ("B01", "B03", "B33", "B40"):
        assert c.put(f"/pruebas-modelos/{pid}/revision", json={"modelo": "M1", "item": item, "bueno": True, "revisor": "Tesista"}).status_code == 200
        c.put(f"/pruebas-modelos/{pid}/revision", json={"modelo": "M2", "item": item, "bueno": False, "revisor": "Tesista"})
    r = c.put(f"/pruebas-modelos/{pid}/revision", json={"modelo": "M2", "item": "B40", "bueno": None, "revisor": "Tesista",
                                                        "a_ciegas": False})
    res = r.json()["resumen"]
    assert res["modelos"][0]["aprobacion"]["valor"] == 1 and res["modelos"][1]["revisados"] == 3
    assert res["pares"][0] == {"a": "M1", "b": "M2", "comunes": 3, "solo_a": 3, "solo_b": 0, "p": 0.25}
    assert r.json()["revisiones"]["a_ciegas"] is False
    assert c.put(f"/pruebas-modelos/{pid}/revision", json={"modelo": "M9", "item": "B01", "bueno": True,
                                                           "revisor": "x"}).status_code == 422

    listado = c.get("/pruebas-modelos").json()
    assert listado[0]["prueba_id"] == pid and listado[0]["modelos"][0]["aprobacion"] == 1

    z = c.get(f"/pruebas-modelos/{pid}/overleaf.zip")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    nombres = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert {"main.tex", "estilo-dudamel.tex", "figuras/modelos.tex", "tablas/modelos.tex", "tablas/pares.tex",
            "tablas/banco.tex", "tablas/respuestas.tex", "datos/modelos.csv", "prueba.json"} <= set(nombres)

    # reanudar solo los que fallaron: el modelo roto vuelve a correr sus 4 términos
    r = c.post(f"/pruebas-modelos/{pid}/reanudar", params={"errores": True})
    assert r.status_code == 200 and r.json()["avance"]["hechos"] == 8
    assert _esperar(c, pid)["estado"] == "terminada"

    assert c.delete(f"/pruebas-modelos/{pid}").status_code == 204
    assert c.get(f"/pruebas-modelos/{pid}").status_code == 404


def test_validaciones_al_crear(cliente):
    c = cliente
    assert c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"}],
                                            "items": ["B99"]}).status_code == 422
    r = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "google", "modelo": "gemini-x"}]})
    assert r.status_code == 422 and "clave" in r.json()["detail"]
    assert c.post("/pruebas-modelos", json={"modelos": []}).status_code == 422


def test_con_controles_hay_precision_falsas_alarmas_y_parejas(cliente):
    c = cliente
    r = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"},
                                                      {"proveedor": "ollama", "modelo": "flojo"}],
                                         "items": ["B16", "B63", "B01", "B61", "B33"]})
    assert r.status_code == 201 and r.json()["banco"]["version"] == "v2"
    p = _esperar(c, r.json()["prueba_id"])
    alarmista, callado = p["resumen"]["modelos"]
    # el que dice «ambiguo» a todo ya no sale perfecto: exhaustividad 1, pero falsas alarmas 1
    assert alarmista["deteccion"]["valor"] == 1 and alarmista["falsas_alarmas"]["valor"] == 1
    assert alarmista["precision"]["valor"] == 0.6 and alarmista["confusion"] == {"vp": 3, "fn": 0, "fp": 2, "vn": 0}
    assert alarmista["parejas"] == {"n": 2, "discrimina": 0}
    assert callado["deteccion"]["valor"] == 0 and callado["falsas_alarmas"]["valor"] == 0
    assert callado["precision"]["valor"] is None
    assert alarmista["por_clase"]["inequivoco"] == {"n": 2, "ambiguo": False, "deteccion": alarmista["falsas_alarmas"],
                                                    "aprobacion": pm.wilson(0, 0)}
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/pruebas-modelos/{p['prueba_id']}/overleaf.zip").content))
    assert "tablas/confusion.tex" in z.namelist() and "Falsas alarmas" in z.read("figuras/modelos.tex").decode()
    assert "0/2" in z.read("tablas/confusion.tex").decode()


def test_una_prueba_del_banco_v1_se_sigue_midiendo_con_su_banco(cliente):
    c = cliente
    r = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"}], "banco": "v1",
                                         "items": ["B01", "B63"]})
    assert r.status_code == 422  # B63 no existe en v1
    r = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"}], "banco": "v1",
                                         "items": ["B01", "B02"]})
    p = _esperar(c, r.json()["prueba_id"])
    m = p["resumen"]["modelos"][0]
    assert p["banco"]["version"] == "v1" and m["falsas_alarmas"] is None and m["precision"] is None
    assert any("Sin controles inequívocos" in a for a in p["resumen"]["avisos"]) and p["resumen"]["banco"]["coincide"]
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/pruebas-modelos/{p['prueba_id']}/overleaf.zip").content))
    assert "tablas/confusion.tex" not in z.namelist() and "Falsas alarmas" not in z.read("figuras/modelos.tex").decode()
    assert c.get("/bancos/ambiguedad", params={"version": "v1"}).json()["version"] == "v1"
    assert c.get("/bancos/ambiguedad", params={"version": "v9"}).status_code == 404


def test_rehacer_la_revision_borra_las_marcas(cliente):
    c = cliente
    pid = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"}],
                                           "items": ["B01"]}).json()["prueba_id"]
    _esperar(c, pid)
    c.put(f"/pruebas-modelos/{pid}/revision", json={"modelo": "M1", "item": "B01", "bueno": True, "revisor": "T",
                                                    "a_ciegas": False})
    assert any("viendo el nombre" in a for a in c.get(f"/pruebas-modelos/{pid}").json()["resumen"]["avisos"])
    assert c.delete(f"/pruebas-modelos/{pid}/revision").status_code == 204
    p = c.get(f"/pruebas-modelos/{pid}").json()
    assert p["revisiones"] is None and p["resumen"]["modelos"][0]["revisados"] == 0


def test_una_prueba_sin_hilo_queda_interrumpida(cliente):
    c = cliente
    p = pm.nueva_prueba("P07", usuario_id="U00", modelos=[{"proveedor": "ollama", "modelo": "bueno"}],
                        items=["B01"], nota=None, version="x", settings=c.srv.deps.settings)
    c.srv.repo.guardar_doc(pm.COLECCION_PRUEBAS, "P07", p)
    assert c.get("/pruebas-modelos/P07").json()["estado"] == "interrumpida"
    assert c.post("/pruebas-modelos/P07/reanudar").status_code == 200
    assert _esperar(c, "P07")["estado"] == "terminada"


def test_el_paquete_escapa_y_limpia_lo_que_responde_el_modelo():
    p = pm.nueva_prueba("P01", usuario_id="U00", modelos=[{"proveedor": "ollama", "modelo": "qwen2.5:7b"}],
                        items=["B01"], nota=None, version="2.3.0", settings=type("S", (), {
                            "llm_temperature": 0, "llm_seed": 1, "significado_max_palabras": 12})())
    p["resultados"] = {"M1": {"B01": {"ok": True, "ms": 10, "intentos": 1, "ambiguo": True, "tipo": "lexica",
                                      "intenciones": [{"id": "I1", "significado": "cita 100% médica 🙂 → sí", "intencion": "x",
                                                       "parafrasis": "x"}, {"id": "I2", "significado": "búsqueda_en BD",
                                                                            "intencion": "x", "parafrasis": "x"}]}}}
    z = zipfile.ZipFile(io.BytesIO(paquete_overleaf(p, pm.resumen(p, None), None)))
    respuestas = z.read("tablas/respuestas.tex").decode()
    assert r"cita 100\% médica ? ? sí / búsqueda\_en BD" in respuestas
    assert "tablas/pares.tex" not in z.namelist()  # un solo modelo: no hay pares
    figura = z.read("figuras/modelos.tex").decode()
    assert "Aprobación" not in figura and figura.count("\\begin{") == figura.count("\\end{")
