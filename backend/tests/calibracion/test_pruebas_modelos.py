"""Prueba de modelos con el banco de términos ambiguos (ADR 0027)."""
from __future__ import annotations

import io
import re
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.calibracion import calidad as cal
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

    # la revisión ✓/✗ de la v2.3 ya no se escribe
    assert c.put(f"/pruebas-modelos/{pid}/revision", json={"modelo": "M1", "item": "B01", "bueno": True,
                                                           "revisor": "T"}).status_code in (404, 405)
    # revisión de calidad: a ciegas por omisión, con semilla y orden guardados; los errores no se revisan
    rev = c.post(f"/pruebas-modelos/{pid}/revision-calidad", json={"revisor": "Tesista"}).json()
    assert rev["a_ciegas"] is True and isinstance(rev["semilla"], int) and len(rev["orden"]) == 8
    assert {o["modelo"] for o in rev["orden"]} == {"M1", "M2"} and sorted(rev["letras"]) == ["M1", "M2", "M3"]
    for o in rev["orden"]:
        r = c.put(f"/pruebas-modelos/{pid}/revision-calidad/marca", json={
            **o, "fidelidad": o["modelo"] == "M1", "delimitacion": True, "intencion": o["item"] != "B03",
            "cobertura": [0, 1, 7]})
        assert r.status_code == 200, r.text
    assert r.json() == {**r.json(), "revisadas": 8, "total": 8}
    assert c.put(f"/pruebas-modelos/{pid}/revision-calidad/marca", json={
        "modelo": "M3", "item": "B01", "fidelidad": True, "delimitacion": True, "intencion": True}).status_code == 422
    res = c.get(f"/pruebas-modelos/{pid}").json()["resumen"]
    q1, q2 = res["modelos"][0]["calidad"], res["modelos"][1]["calidad"]
    assert q1["criterios"]["fidelidad"]["valor"] == 1 and q2["criterios"]["fidelidad"]["valor"] == 0
    assert q1["criterios"]["intencion"]["valor"] == 0.75 and q1["revisadas"] == 4
    assert q1["cobertura"]["cubiertas"] == 8 and q1["cobertura"]["esperadas"] == 8  # el índice 7 no existe: no cuenta
    par = res["pares"][0]
    assert par["deteccion"] == {"n": 4, "solo_a": 4, "solo_b": 0, "p": 0.125}
    # M1 dio 2 intenciones y M2 una: la calidad no se compara entre ellos (se excluyen y se cuentan)
    assert par["calidad"]["fidelidad"]["n"] == 0 and par["excluidos_por_intenciones"] == 4
    assert "aprobacion" not in res["modelos"][0] and res["aprobacion_legado"] is None
    fn = res["modelos"][1]["falsos_negativos"]
    assert len(fn["items"]) == 4 and fn["sin_clasificar"] == 4
    assert res["modelos"][2]["falsos_negativos"]["items"][0]["sugerido"] == "formato"
    assert c.put(f"/pruebas-modelos/{pid}/modos", json={"modelo": "M2", "item": "B01", "modo": "documento_hecho"}).status_code == 200
    assert c.put(f"/pruebas-modelos/{pid}/modos", json={"modelo": "M1", "item": "B01", "modo": "otro"}).status_code == 422
    assert c.put(f"/pruebas-modelos/{pid}/modos", json={"modelo": "M2", "item": "B03", "modo": "inventado"}).status_code == 422
    res = c.get(f"/pruebas-modelos/{pid}").json()["resumen"]
    assert res["modelos"][1]["falsos_negativos"]["por_modo"]["documento_hecho"] == 1

    listado = c.get("/pruebas-modelos").json()
    assert listado[0]["prueba_id"] == pid and listado[0]["modelos"][0]["revisadas"] == 4
    assert listado[0]["codigo"].startswith(f"{pid}-v2-") and listado[0]["uid"]

    z = c.get(f"/pruebas-modelos/{pid}/overleaf.zip")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    nombres = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert {"main.tex", "estilo-dudamel.tex", "figuras/modelos.tex", "figuras/calidad.tex", "figuras/confusion.tex",
            "figuras/cobertura.tex", "figuras/modos.tex", "figuras/latencia.tex", "figuras/subenumeracion.tex",
            "tablas/modelos.tex", "tablas/pares.tex", "tablas/calidad.tex", "tablas/banco.tex", "tablas/respuestas.tex",
            "datos/modelos.csv", "apendice/rubrica.tex", "rubrica.md", "prueba.json"} <= set(nombres)
    assert z.headers["content-disposition"].endswith(f'{c.get(f"/pruebas-modelos/{pid}").json()["codigo"]}.zip"')

    # reanudar solo los que fallaron: el modelo roto vuelve a correr sus 4 términos
    r = c.post(f"/pruebas-modelos/{pid}/reanudar", params={"errores": True})
    assert r.status_code == 200 and r.json()["avance"]["hechos"] == 8
    assert _esperar(c, pid)["estado"] == "terminada"

    assert c.delete(f"/pruebas-modelos/{pid}").status_code == 204
    assert c.get(f"/pruebas-modelos/{pid}").status_code == 404
    assert c.srv.repo.obtener_doc(cal.COLECCION_CALIDAD, pid) is None
    # el número no se reutiliza: queda una lápida y la prueba nueva toma el siguiente
    assert c.srv.repo.obtener_doc(pm.COLECCION_PRUEBAS, pid)["borrada"] is True
    assert pid not in [x["prueba_id"] for x in c.get("/pruebas-modelos").json()]
    nueva = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"}], "items": ["B01"]})
    assert int(nueva.json()["prueba_id"][1:]) > int(pid[1:])
    _esperar(c, nueva.json()["prueba_id"])


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
    assert {k: alarmista["parejas"][k] for k in ("n", "discrimina")} == {"n": 2, "discrimina": 0}
    assert callado["deteccion"]["valor"] == 0 and callado["falsas_alarmas"]["valor"] == 0
    assert callado["precision"]["valor"] is None
    assert alarmista["por_clase"]["inequivoco"] == {"n": 2, "ambiguo": False, "deteccion": alarmista["falsas_alarmas"]}
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
    assert "Falsas alarmas" not in z.read("figuras/modelos.tex").decode()
    assert "& --- & --- & ---" in z.read("tablas/confusion.tex").decode()  # sin controles: ni FP ni VN
    assert c.get("/bancos/ambiguedad", params={"version": "v1"}).json()["version"] == "v1"
    assert c.get("/bancos/ambiguedad", params={"version": "v9"}).status_code == 404


def test_rehacer_borra_solo_la_revision_nueva_y_la_vieja_queda_con_su_criterio(cliente):
    c = cliente
    pid = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"}],
                                           "items": ["B01", "B02"]}).json()["prueba_id"]
    _esperar(c, pid)
    legado = {"prueba_id": pid, "usuario_id": "U00", "revisor": "T", "a_ciegas": False,
              "marcas": {"M1": {"B01": {"bueno": True, "nota": None, "fecha": "x"}, "B02": {"bueno": False, "nota": None, "fecha": "x"}}}}
    c.srv.repo.guardar_doc(pm.COLECCION_REVISIONES, pid, legado)  # una revisión hecha con la v2.3
    c.post(f"/pruebas-modelos/{pid}/revision-calidad", json={"revisor": "T", "a_ciegas": False})
    c.put(f"/pruebas-modelos/{pid}/revision-calidad/marca", json={"modelo": "M1", "item": "B01", "fidelidad": True,
                                                                  "delimitacion": True, "intencion": True})
    p = c.get(f"/pruebas-modelos/{pid}").json()
    leg = p["resumen"]["aprobacion_legado"]
    assert leg["por_modelo"]["M1"]["valor"] == 0.5 and "v2.3" in leg["criterio"]
    assert any("criterio viejo" in a for a in p["resumen"]["avisos"])
    assert any("nombres de los modelos a la vista" in a for a in p["resumen"]["avisos"])
    assert c.post(f"/pruebas-modelos/{pid}/revision-calidad", json={"revisor": "T"}).status_code == 409
    assert c.delete(f"/pruebas-modelos/{pid}/revision-calidad").status_code == 204
    p = c.get(f"/pruebas-modelos/{pid}").json()
    assert p["revision_calidad"] is None and p["revisiones"] == legado  # la vieja no se toca ni se traduce
    assert p["resumen"]["modelos"][0]["calidad"]["revisadas"] == 0
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/pruebas-modelos/{pid}/overleaf.zip").content))
    assert "tablas/aprobacion_legado.tex" in z.namelist() and "figuras/calidad.tex" not in z.namelist()
    assert "Figura omitida: calidad" in z.read("main.tex").decode()


def test_una_serie_mide_la_estabilidad(cliente, monkeypatch):
    c = cliente
    r = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"}], "items": ["B01", "B02"],
                                         "repeticiones": 2})
    assert r.status_code == 201 and len(r.json()["serie_creada"]) == 2
    primera, segunda = r.json()["serie_creada"]
    for pid in (primera, segunda):
        _esperar(c, pid)
    p2 = c.get(f"/pruebas-modelos/{segunda}").json()
    assert p2["serie"] == primera and p2["corrida"] == 2 and p2["uid"] != c.get(f"/pruebas-modelos/{primera}").json()["uid"]
    # una corrida más que, esta vez, no detecta nada: la detección varía y el rango lo dice
    monkeypatch.setattr(pm, "crear_cliente_de", lambda e, s: LLMFalso({"clasificador_intencion_v1": _respuesta(1)}, "x"))
    r = c.post(f"/pruebas-modelos/{primera}/repetir", json={"veces": 1})
    assert r.status_code == 201 and r.json()["serie"] == primera
    _esperar(c, r.json()["creadas"][0])
    e = c.get(f"/pruebas-modelos/series/{primera}").json()
    assert [x["corrida"] for x in e["corridas"]] == [1, 2, 3] and e["misma_configuracion"]
    m = e["modelos"][0]
    assert m["detecciones"] == [2, 2, 0] and (m["minimo"], m["maximo"], m["rango"]) == (0, 2, 2)
    assert any("cambió entre corridas" in a for a in e["avisos"])
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/pruebas-modelos/{primera}/overleaf.zip").content))
    assert {"figuras/estabilidad.tex", "tablas/estabilidad.tex", "datos/estabilidad.csv"} <= set(z.namelist())
    assert c.get("/pruebas-modelos/series/P99").status_code == 404


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
