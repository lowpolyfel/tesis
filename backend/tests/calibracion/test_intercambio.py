"""Revisión de calidad fuera del sistema: exportar a ciegas, contestar e importar (ADR 0030)."""
from __future__ import annotations

import io
import json
import re
import zipfile

from app.calibracion import intercambio
from app.calibracion import pruebas_modelos as pm
from app.calibracion.rubrica import ACLARACIONES
from tests.calibracion.test_pruebas_modelos import (  # noqa: F401 — el fixture se usa por nombre
    _esperar,
    cliente,
)

ITEMS = ["B01", "B05", "B33", "B51"]  # dos polisemias (B05 con tres lecturas), un regionalismo y un control


def _prueba(c) -> tuple[str, dict]:
    r = c.post("/pruebas-modelos", json={"modelos": [{"proveedor": "ollama", "modelo": "bueno"},
                                                      {"proveedor": "ollama", "modelo": "flojo"},
                                                      {"proveedor": "ollama", "modelo": "roto"}], "items": ITEMS})
    assert r.status_code == 201, r.text
    pid = r.json()["prueba_id"]
    return pid, _esperar(c, pid)


def _contestar(plantilla: dict, **cambios) -> dict:
    """Llena la plantilla: todo cumple, la primera lectura aparece y los falsos negativos son
    «contexto_cierra», salvo lo que se pida por id."""
    d = json.loads(json.dumps(plantilla))
    for x in d["respuestas"]:
        x.update({"fidelidad": True, "delimitacion": True, "intencion": True})
        if "lecturas" in x:
            x["lecturas"] = [1]
        x.update(cambios.get(x["id"], {}))
    for x in d["modos"]:
        x["modo"] = x["modo"] or "contexto_cierra"
    return d


def test_el_archivo_es_a_ciegas_y_trae_la_rubrica_y_la_plantilla(cliente):  # noqa: F811
    c = cliente
    pid, _ = _prueba(c)
    md = c.get(f"/pruebas-modelos/{pid}/revision-calidad/exportar")
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert re.search(r'filename="revision-P\d+-v2-[0-9a-f]{6}\.md"', md.headers["content-disposition"])
    texto = md.text
    # sin proveedor, modelo ni id interno de modelo
    for prohibido in ("ollama", "bueno", "flojo", "roto", '"M1"', "M2"):
        assert prohibido not in texto, prohibido
    assert all(t in texto for _, t in ACLARACIONES) and "## Respuesta" in texto
    datos = intercambio.leer(texto)
    assert datos["formato"] == intercambio.FORMATO and isinstance(datos["semilla"], int)
    # 4 ítems × 2 modelos que respondieron (el roto no tiene salida que revisar)
    assert [x["id"] for x in datos["respuestas"]] == [f"S{k:03d}" for k in range(1, 9)]
    assert all(x["fidelidad"] is None for x in datos["respuestas"])
    # el control (B51) no trae lecturas que marcar; los ambiguos sí
    js = c.get(f"/pruebas-modelos/{pid}/revision-calidad/exportar?formato=json").json()
    por_id = {s["id"]: s for s in js["salidas"]}
    assert {len(s["lecturas"]) for s in por_id.values()} == {0, 2, 3}
    assert all(("lecturas" in x) == bool(por_id[x["id"]]["lecturas"]) for x in js["plantilla"]["respuestas"])
    # falsos negativos: el flojo en los 3 ambiguos y el roto en los 3; los del roto ya traen «formato»
    assert len(js["falsos_negativos"]) == 6
    assert sum(1 for m in js["plantilla"]["modos"] if m["modo"] == "formato") == 3
    # exportar no crea la revisión
    assert c.get(f"/pruebas-modelos/{pid}/revision-calidad").json() is None
    assert c.get(f"/pruebas-modelos/{pid}/revision-calidad/exportar?formato=pdf").status_code == 422


def test_importar_lo_que_contesto_una_ia_crea_la_revision_y_queda_dicho(cliente):  # noqa: F811
    c = cliente
    pid, _ = _prueba(c)
    texto = c.get(f"/pruebas-modelos/{pid}/revision-calidad/exportar").text
    datos = intercambio.leer(texto)
    respuesta = _contestar(datos, S002={"delimitacion": False, "nota": "junta dos sentidos"})
    # la IA contesta envuelto en prosa: se toma el bloque JSON
    chat = f"Claro, aquí tienes:\n\n```json\n{json.dumps(respuesta, ensure_ascii=False)}\n```\n¿Algo más?"
    r = c.post(f"/pruebas-modelos/{pid}/revision-calidad/importar",
               json={"contenido": chat, "tipo": "ia", "quien": "google · gemini-x"})
    assert r.status_code == 200, r.text
    inf = r.json()
    assert inf["aplicadas"] == 8 and inf["conservadas"] == 0 and inf["errores"] == [] and inf["acuerdo"] is None
    assert inf["modos_aplicados"] == 6 and inf["revisadas"] == 8 == inf["total"]

    doc = c.get(f"/pruebas-modelos/{pid}/revision-calidad").json()
    assert doc["semilla"] == datos["semilla"] and doc["a_ciegas"] and doc["revisor_tipo"] == "ia"
    o = doc["orden"][1]  # S002 = la segunda salida del orden
    marca = doc["marcas"][o["modelo"]][o["item"]]
    assert marca["delimitacion"] is False and marca["nota"] == "junta dos sentidos"
    assert marca["origen"] == {"tipo": "ia", "quien": "google · gemini-x", "importacion": 1}
    assert doc["importaciones"][0]["aplicadas"] == 8 and len(doc["importaciones"][0]["respuestas"]) == 8

    res = c.get(f"/pruebas-modelos/{pid}").json()["resumen"]
    assert any("LLM como juez" in a and "8 de 8" in a for a in res["avisos"])
    assert res["modelos"][2]["falsos_negativos"]["por_modo"]["formato"] == 3
    assert res["modelos"][1]["falsos_negativos"]["sin_clasificar"] == 0
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/pruebas-modelos/{pid}/overleaf.zip").content))
    main = z.read("main.tex").decode()
    assert "8 de IA como juez (google · gemini-x)" in main and "Casos frecuentes" in z.read("apendice/rubrica.tex").decode()


def test_no_pisa_lo_marcado_en_pantalla_y_mide_el_acuerdo(cliente):  # noqa: F811
    c = cliente
    pid, _ = _prueba(c)
    rev = c.post(f"/pruebas-modelos/{pid}/revision-calidad", json={"revisor": "Tesista"}).json()
    terminos = {t["id"]: t for t in pm.banco()["terminos"]}
    for o in rev["orden"][:4]:  # en pantalla: todo cumple salvo la intención
        c.put(f"/pruebas-modelos/{pid}/revision-calidad/marca", json={
            **o, "fidelidad": True, "delimitacion": True, "intencion": False,
            "cobertura": [0] if pm.es_ambiguo(terminos[o["item"]]) else []})
    datos = intercambio.leer(c.get(f"/pruebas-modelos/{pid}/revision-calidad/exportar").text)
    assert datos["semilla"] == rev["semilla"]  # el orden del archivo es el de la revisión
    respuesta = _contestar(datos)  # la persona dijo que la intención sí cumple
    inf = c.post(f"/pruebas-modelos/{pid}/revision-calidad/importar",
                 json={"contenido": json.dumps(respuesta), "tipo": "persona", "quien": "Ana"}).json()
    assert inf["aplicadas"] == 4 and inf["conservadas"] == 4
    ac = inf["acuerdo"]
    assert ac["fidelidad"]["n"] == 4 and ac["fidelidad"]["acuerdo_observado"] == 1
    assert ac["intencion"]["acuerdo_observado"] == 0 and ac["lecturas"]["iguales"] == ac["lecturas"]["n"]
    doc = c.get(f"/pruebas-modelos/{pid}/revision-calidad").json()
    o = rev["orden"][0]
    assert doc["marcas"][o["modelo"]][o["item"]]["intencion"] is False  # lo de pantalla se conservó
    assert "origen" not in doc["marcas"][o["modelo"]][o["item"]] and doc["revisor"] == "Tesista"
    assert any("fuera del sistema" in a and "(Ana)" in a for a in c.get(f"/pruebas-modelos/{pid}").json()["resumen"]["avisos"])

    # sólo pendientes: ya no queda nada de calidad
    pend = intercambio.leer(c.get(f"/pruebas-modelos/{pid}/revision-calidad/exportar?pendientes=true").text)
    assert pend["respuestas"] == []
    # sobrescribir pisa lo de pantalla
    inf = c.post(f"/pruebas-modelos/{pid}/revision-calidad/importar",
                 json={"contenido": json.dumps(respuesta), "tipo": "persona", "quien": "Ana", "sobrescribir": True}).json()
    assert inf["aplicadas"] == 8
    doc = c.get(f"/pruebas-modelos/{pid}/revision-calidad").json()
    assert doc["marcas"][o["modelo"]][o["item"]]["intencion"] is True and len(doc["importaciones"]) == 2


def test_archivos_ajenos_o_mal_contestados(cliente):  # noqa: F811
    c = cliente
    pid, _ = _prueba(c)
    datos = intercambio.leer(c.get(f"/pruebas-modelos/{pid}/revision-calidad/exportar").text)
    url = f"/pruebas-modelos/{pid}/revision-calidad/importar"

    def importar(d, **extra):
        return c.post(url, json={"contenido": json.dumps(d), "tipo": "ia", "quien": "x", **extra})

    assert importar({**datos, "prueba": "P99-v2-000000"}).status_code == 422
    assert importar({**datos, "huella": "0" * 16}).status_code == 422
    assert c.post(url, json={"contenido": "no hay json aquí", "tipo": "ia", "quien": "x"}).status_code == 422
    assert importar(datos, tipo="robot").status_code == 422
    # sin contestar no cuenta; lecturas fuera de rango o mal escritas son errores por id
    ambiguo = next(x["id"] for x in datos["respuestas"] if "lecturas" in x and x["id"] != "S001")
    d = _contestar(datos, **{ambiguo: {"lecturas": [9]}, "S001": {"fidelidad": None}})
    d["respuestas"].append({"id": "S999", "fidelidad": True, "delimitacion": True, "intencion": True})
    d["modos"][0]["modo"] = "inventado"
    inf = importar(d).json()
    assert inf["sin_contestar"] == 1 and inf["aplicadas"] == 6
    assert {e["id"] for e in inf["errores"]} == {ambiguo, "S999", d["modos"][0]["id"]}
    # «sí»/«no» escritos como texto también valen
    otro, _ = _prueba(c)
    d2 = intercambio.leer(c.get(f"/pruebas-modelos/{otro}/revision-calidad/exportar").text)
    for x in d2["respuestas"]:
        x.update({"fidelidad": "sí", "delimitacion": "no", "intencion": "true"})
    assert c.post(f"/pruebas-modelos/{otro}/revision-calidad/importar",
                  json={"contenido": json.dumps(d2), "tipo": "ia", "quien": "x"}).json()["aplicadas"] == 8
