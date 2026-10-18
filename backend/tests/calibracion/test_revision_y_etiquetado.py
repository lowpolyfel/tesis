"""Revisión de calidad, etiquetado por varias personas, ids no reutilizables, rúbrica y paquetes LaTeX
que compilan (ADR 0029)."""
from __future__ import annotations

import io
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.calibracion import calidad as cal
from app.calibracion import pruebas_modelos as pm
from app.calibracion.anotaciones import (
    consolidar,
    kappa,
    nueva_anotacion,
    responder,
    terminos_para_etiquetar,
)
from app.calibracion.estadistica import banda_roc
from app.calibracion.informe_entrevistas import informe_entrevistas, nueva_corrida
from app.calibracion.latex import paquete_overleaf as paquete_calibracion
from app.calibracion.latex_modelos import paquete_overleaf as paquete_modelos
from app.calibracion.rubrica import markdown
from tests.fakes import como_usuario
from tests.fases.escenario import ENTREVISTA, montar

RAIZ = Path(__file__).resolve().parents[3]


class _S:
    llm_temperature, llm_seed, significado_max_palabras = 0, 42, 12


def _prueba(resultados: dict[str, dict], items: list[str]) -> dict:
    p = pm.nueva_prueba("P01", usuario_id="U00", modelos=[{"proveedor": "ollama", "modelo": "a"},
                                                          {"proveedor": "google", "modelo": "b"}],
                        items=items, nota=None, version="2.4.0", settings=_S)
    p["resultados"], p["estado"] = resultados, "terminada"
    return p


def _r(n: int) -> dict:
    return {"ok": True, "ms": 10, "intentos": 1, "ambiguo": n > 1,
            "intenciones": [{"id": f"I{k}", "significado": "s", "intencion": "i", "parafrasis": "p"} for k in range(1, n + 1)]}


# ---------------------------------------------------------------- revisión de calidad

def test_el_orden_de_la_revision_es_reconstruible_y_agrupa_los_modelos_por_item():
    items = [f"B{i:02d}" for i in range(1, 11)]
    p = _prueba({"M1": {i: _r(2) for i in items}, "M2": {i: _r(1) for i in items[:8]}}, items)
    a = cal.nueva_revision(p, revisor="T", a_ciegas=True, semilla=99)
    b = cal.nueva_revision(p, revisor="T", a_ciegas=True, semilla=99)
    assert a["orden"] == b["orden"] and a["letras"] == b["letras"] and a["a_ciegas"] and a["esquema"] == 2
    assert len(a["orden"]) == 18 and [o["item"] for o in a["orden"]] != sorted(o["item"] for o in a["orden"])
    vistos = []  # las salidas de un mismo ítem van juntas
    for o in a["orden"]:
        if not vistos or vistos[-1] != o["item"]:
            assert o["item"] not in vistos
            vistos.append(o["item"])
    # se reintentaron dos errores: las salidas nuevas van al final y lo demás no se mueve
    p["resultados"]["M2"].update({"B09": _r(1), "B10": _r(1)})
    antes = list(a["orden"])
    assert cal.completar_orden(a, p) and a["orden"][:18] == antes and len(a["orden"]) == 20
    assert not cal.completar_orden(a, p)


def test_mcnemar_de_la_deteccion_y_criterios_solo_con_igual_numero_de_intenciones():
    items = [f"B{i:02d}" for i in range(1, 41)]  # B01–B40: ambiguos del banco v2
    p = _prueba({"M1": {i: _r(2) for i in items}, "M2": {i: _r(2 if k >= 34 else 1) for k, i in enumerate(items)}}, items)
    terminos = {t["id"]: t for t in pm.banco()["terminos"]}
    pares = cal.pares(p, None, terminos, pm.es_ambiguo)[0]
    assert pares["deteccion"]["solo_a"] == 34 and pares["deteccion"]["solo_b"] == 0
    assert pares["deteccion"]["p"] == pytest.approx(2 * 0.5 ** 34) and pares["deteccion"]["p"] < 1.2e-10
    doc = cal.nueva_revision(p, revisor="T", a_ciegas=True, semilla=1)
    for o in doc["orden"]:
        t = terminos[o["item"]]
        cal.marcar(doc, modelo=o["modelo"], item=o["item"], criterios={"fidelidad": o["modelo"] == "M1",
                   "delimitacion": True, "intencion": True}, cobertura=[0], n_lecturas=len(t["lecturas"]),
                   ambiguo=True, nota=None)
    q = cal.pares(p, doc, terminos, pm.es_ambiguo)[0]
    assert q["revisados_en_ambos"] == 40 and q["excluidos_por_intenciones"] == 34
    assert q["calidad"]["fidelidad"] == {"n": 6, "solo_a": 6, "solo_b": 0, "p": pytest.approx(2 / 64)}
    with pytest.raises(ValueError):
        cal.marcar(doc, modelo="M1", item="B01", criterios={"fidelidad": True}, cobertura=[], n_lecturas=2,
                   ambiguo=True, nota=None)


def test_subenumeracion_y_falsos_negativos():
    terminos = {t["id"]: t for t in pm.banco()["terminos"]}
    tres = [i for i, t in terminos.items() if pm.es_ambiguo(t) and len(t["lecturas"]) == 3]
    items = tres + ["B01", "B51"]
    err = {"ok": False, "ms": 1, "intentos": 2, "error": "significado tiene 14 palabras"}
    p = _prueba({"M1": {**{i: _r(2) for i in tres}, tres[0]: _r(3), "B01": err, "B51": _r(1)},
                 "M2": {i: _r(1) for i in items}}, items)
    sub = cal.subenumeracion(p, terminos, pm.es_ambiguo)
    assert sub["M1"]["con_tres"] == {"n": len(tres), "marcados": len(tres), "tres_o_mas": 1}
    fn = cal.falsos_negativos(p, None, terminos, pm.es_ambiguo)
    assert [x["item"] for x in fn["M1"]["items"]] == ["B01"] and fn["M1"]["items"][0]["sugerido"] == "formato"
    assert len(fn["M2"]["items"]) == len(tres) + 1  # el control B51 no cuenta: no es ambiguo


def test_las_colisiones_entre_bases_se_detectan_y_las_lapidas_tambien():
    v1 = {"prueba_id": "P01", "uid": None, "banco": {"version": "v1", "huella": "aaa"}}
    v2 = {"prueba_id": "P01", "uid": "u2", "banco": {"version": "v2", "huella": "bbb"}}
    mismo = {"prueba_id": "P02", "uid": "u3", "banco": {"version": "v2", "huella": "bbb"}}
    col = pm.colisiones(("json local", [v1, mismo]), ("mongo", [v2, mismo]))
    assert [c["prueba_id"] for c in col] == ["P01"]
    assert {f["codigo"] for f in col[0]["fuentes"]} == {"P01-v1-aaa", "P01-v2-bbb"}
    lap = pm.lapida({**mismo, "usuario_id": "U00", "creado": "x"})
    assert lap["borrada"] and lap["codigo"] == "P02-v2-bbb" and "resultados" not in lap


def test_la_rubrica_del_apendice_es_la_misma_que_sirve_la_pantalla():
    assert (RAIZ / "docs" / "rubrica-revision.md").read_text(encoding="utf-8") == markdown(), \
        "docs/rubrica-revision.md está desactualizada: regénerala con app.calibracion.rubrica.markdown()"


# ---------------------------------------------------------------- etiquetado de entrevistas

def _entrevista(n: int = 6):
    terms = [f"termino{i}" for i in range(n)]
    e = {"entrevista_id": "E01", "proyecto_id": "P01", "titulo": "t", "estado": "lista",
         "turnos": [{"n": i + 1, "hablante": "Ana", "texto": f"Aquí usamos el {t} a diario."} for i, t in enumerate(terms)]}
    msgs = [{"tipo": "filtrado", "payload": {"terminos": [{"termino": t, "turnos": [i + 1]} for i, t in enumerate(terms)]}}]
    for i, t in enumerate(terms):
        s = 0.6 + 0.05 * i
        msgs.append({"tipo": "similitud", "ronda": 0, "modelo": "nomic", "payload": {
            "termino": t, "similitud": s, "umbral": 0.75, "decision": "en_debate" if s < 0.75 else "aceptado_directo"}})
    return e, {"mensajes": msgs}, terms


def test_kappa_de_cohen():
    a = {"x": True, "y": True, "z": False, "w": False}
    b = {"x": True, "y": False, "z": False, "w": False}
    assert kappa(a, b) == {"n": 4, "acuerdo_observado": 0.75, "kappa": 0.5}
    assert kappa(a, {})["kappa"] is None
    assert kappa({"x": True}, {"x": True})["kappa"] is None  # una sola clase: no se define


def test_etiquetado_a_ciegas_y_consolidacion_de_varias_personas():
    e, b, terms = _entrevista()
    ts = terminos_para_etiquetar(e, b)
    assert [t["termino"] for t in ts] == terms and all(set(t) == {"termino", "clave", "citas"} for t in ts)
    assert ts[0]["citas"][0]["turno"] == 1 and "termino0" in ts[0]["citas"][0]["fragmento"]
    a = nueva_anotacion("A01", e, ts, anotador="Tesista", a_ciegas=True, semilla=3)
    b2 = nueva_anotacion("A02", e, ts, anotador="Asesora", a_ciegas=True, semilla=4)
    assert a["orden"] != b2["orden"] and sorted(a["orden"]) == sorted(b2["orden"])
    for k, t in enumerate(terms):
        responder(a, termino=t, respuesta="si" if k < 3 else "no")
        responder(b2, termino=t, respuesta=["si", "no", "no_se", "no", "no", "no"][k])
    with pytest.raises(ValueError):
        responder(a, termino="termino0", respuesta="quizá")
    c = consolidar([a, b2])
    assert [x["termino"] for x in c["etiquetas"]] == ["termino0", "termino2", "termino3", "termino4", "termino5"]
    assert c["desacuerdos"][0]["termino"] == "termino1" and c["solo_no_se"] == 0
    assert c["acuerdo"][0]["n"] == 5 and c["acuerdo"][0]["kappa"] is not None
    inf = informe_entrevistas([(e, b)], [], umbral_configurado=0.75, max_rondas=2, desde=0.5, hasta=0.95, paso=0.05,
                              remuestreos=200, semilla=7, proyecto_id="P01", anotaciones=[a, b2])
    gt = inf["con_ground_truth"]
    assert gt["n_emparejados"] == 5 and gt["auc"] == 1.0 and len(gt["desacuerdos"]) == 1
    assert gt["roc_banda"] and gt["roc_banda"][0]["fpr"] == 0 and gt["roc_banda"][-1]["alto"] == 1
    assert inf["entrevistas"][0]["anotadores"] == ["Tesista", "Asesora"]
    assert any("desacuerdo" in x for x in inf["avisos"])
    # la huella de las etiquetas, sin anotaciones por persona, es la misma de la v2.2 (las corridas viejas se reproducen)
    vieja = nueva_corrida("C01", inf, nota=None, version="x", configuracion={}, docs_etiquetas=[{"entrevista_id": "E01", "etiquetas": []}])
    nueva = nueva_corrida("C02", inf, nota=None, version="x", configuracion={}, docs_etiquetas=[], anotaciones=[a, b2])
    assert vieja["entrevistas"][0]["huella_etiquetas"] != nueva["entrevistas"][0]["huella_etiquetas"]


def test_la_banda_roc_es_reproducible():
    pares = [({"similitud": 0.5 + 0.05 * i}, {"ambiguo": i % 3 != 0}) for i in range(12)]
    assert banda_roc(pares, 200, 5) == banda_roc(pares, 200, 5)
    assert banda_roc(pares[:2], 50, 5) == [] or all(x["bajo"] <= x["alto"] for x in banda_roc(pares[:2], 50, 5))
    assert banda_roc([(p, {"ambiguo": True}) for p, _ in pares], 50, 5) == []


@pytest.fixture
def cliente(tmp_path, analizador):
    srv, _, p = montar(tmp_path, analizador)
    with TestClient(como_usuario(create_app(srv))) as c:
        c.srv, c.pid = srv, p.proyecto_id
        yield c


def test_etiquetar_por_la_api_y_las_corridas_no_reutilizan_ids(cliente):
    c, pid = cliente, cliente.pid
    eid = c.post(f"/proyectos/{pid}/entrevistas", json={"titulo": "Dra. Ruiz", "texto": ENTREVISTA}).json()["entrevista_id"]
    c.srv.cola.esperar(10)
    a = c.post(f"/entrevistas/{eid}/anotaciones", json={"anotador": "Tesista"})
    assert a.status_code == 201 and a.json()["a_ciegas"] is True
    aid = a.json()["anotacion_id"]
    assert c.post(f"/entrevistas/{eid}/anotaciones", json={"anotador": "tesista"}).json()["anotacion_id"] == aid  # se retoma
    vista = c.get(f"/anotaciones/{aid}").json()
    terminos = [t["termino"] for t in vista["terminos"]]
    assert sorted(terminos) == ["consultas", "da de alta"] and "semilla" in vista
    assert all("similitud" not in t and "decision" not in t for t in vista["terminos"])  # a ciegas
    for t, r in zip(terminos, ("si", "no")):
        assert c.put(f"/anotaciones/{aid}/respuesta", json={"termino": t, "respuesta": r}).status_code == 200
    assert c.put(f"/anotaciones/{aid}/respuesta", json={"termino": "consultas", "respuesta": "tal vez"}).status_code == 422
    otra = c.post(f"/entrevistas/{eid}/anotaciones", json={"anotador": "Asesora"}).json()["anotacion_id"]
    for t, r in zip(terminos, ("si", "no")):
        c.put(f"/anotaciones/{otra}/respuesta", json={"termino": t, "respuesta": r})
    resumen = c.get(f"/entrevistas/{eid}/anotaciones").json()
    assert [x["hechas"] for x in resumen["anotaciones"]] == [2, 2] and resumen["acuerdo"][0]["acuerdo_observado"] == 1
    vivo = c.get(f"/proyectos/{pid}/calibracion/entrevistas").json()
    assert vivo["con_ground_truth"]["n_emparejados"] == 2 and vivo["con_ground_truth"]["roc_banda"]
    cid = c.post(f"/proyectos/{pid}/calibraciones", json={}).json()["calibracion_id"]
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/calibraciones/{cid}/overleaf.zip").content))
    assert {"figuras/roc.tex", "datos/roc_banda.csv", "tablas/acuerdo.tex"} <= set(z.namelist())
    assert c.delete(f"/calibraciones/{cid}").status_code == 204
    assert c.get(f"/calibraciones/{cid}").status_code == 404
    otra_corrida = c.post(f"/proyectos/{pid}/calibraciones", json={}).json()["calibracion_id"]
    assert otra_corrida != cid and [x["calibracion_id"] for x in c.get(f"/proyectos/{pid}/calibraciones").json()] == [otra_corrida]
    # borrar la entrevista borra también el etiquetado de cada persona
    assert c.delete(f"/entrevistas/{eid}").status_code == 200
    assert c.get(f"/anotaciones/{aid}").status_code == 404


# ---------------------------------------------------------------- los paquetes compilan

def _compila(paquete: bytes, destino: Path, motor: str) -> None:
    destino.mkdir(parents=True)
    zipfile.ZipFile(io.BytesIO(paquete)).extractall(destino)
    r = subprocess.run([motor, "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=destino,
                       capture_output=True, text=True, errors="replace", timeout=300, check=False)
    assert r.returncode == 0, f"{motor} falló:\n" + "\n".join(x for x in r.stdout.splitlines() if x.startswith("!"))[:2000]


@pytest.mark.parametrize("motor", ["pdflatex", "xelatex"])
def test_los_paquetes_compilan(tmp_path, motor):
    if not shutil.which(motor):
        pytest.skip(f"{motor} no está instalado")
    items = [t["id"] for t in pm.banco()["terminos"]]
    terminos = {t["id"]: t for t in pm.banco()["terminos"]}
    p = _prueba({"M1": {i: _r(3 if k % 7 == 0 else (2 if k % 3 else 1)) for k, i in enumerate(items)},
                 "M2": {i: (_r(1) if k % 5 else {"ok": False, "ms": 1, "intentos": 2, "error": "100% → ✓"})
                        for k, i in enumerate(items)}}, items)
    doc = cal.nueva_revision(p, revisor="T", a_ciegas=True, semilla=1)
    for o in doc["orden"]:
        t = terminos[o["item"]]
        cal.marcar(doc, modelo=o["modelo"], item=o["item"], criterios={"fidelidad": True, "delimitacion": False,
                   "intencion": True}, cobertura=[0], n_lecturas=len(t["lecturas"]), ambiguo=pm.es_ambiguo(t), nota=None)
    p2 = {**p, "prueba_id": "P02", "corrida": 2, "serie": "P01"}
    from app.calibracion.estabilidad import estabilidad
    _compila(paquete_modelos(p, pm.resumen(p, None, doc, None), None, doc, estabilidad([p, p2])), tmp_path / "m", motor)
    e, b, terms = _entrevista(8)
    ts = terminos_para_etiquetar(e, b)
    a = nueva_anotacion("A01", e, ts, anotador="T", a_ciegas=True, semilla=1)
    for k, t in enumerate(terms):
        responder(a, termino=t, respuesta="si" if k < 4 else "no")
    inf = informe_entrevistas([(e, b)], [], umbral_configurado=0.75, max_rondas=2, desde=0.5, hasta=0.95, paso=0.05,
                              remuestreos=100, semilla=7, proyecto_id="P01", anotaciones=[a])
    _compila(paquete_calibracion(nueva_corrida("C01", inf, nota="n", version="2.4.0", configuracion={},
                                               docs_etiquetas=[], anotaciones=[a])), tmp_path / "c", motor)


def test_el_verificador_de_ids_reporta_sin_uid_y_huella_distinta():
    from app.calibracion.verificar_ids import informe

    vieja = {"prueba_id": "P01", "banco": {"version": "v1", "huella": pm.banco("v1")["huella"]}}
    rara = {"prueba_id": "P02", "uid": "u", "banco": {"version": "v2", "huella": "otra"}}
    r = informe([("json local", [vieja, rara, {"prueba_id": "P03", "borrada": True}]),
                 ("mongo", [{**rara, "uid": "u9"}])])
    assert r["sin_uid"] == [f"json local: P01-v1-{pm.banco('v1')['huella'][:6]}"]
    assert len(r["huella_distinta"]) == 2 and [c["prueba_id"] for c in r["colisiones"]] == ["P02"]
