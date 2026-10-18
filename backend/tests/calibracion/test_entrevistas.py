"""Calibración sobre entrevistas (ADR 0026): similitudes de la bitácora, ground truth, medidas
(ROC, AUC, bootstrap, por tipo), corridas guardadas y el paquete para Overleaf."""
import io
import json
import re
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.calibracion.entrevistas import similitudes_de_entrevista, terminos_de_entrevista
from app.calibracion.estadistica import auc, bootstrap, confusion, emparejar, por_tipo, roc
from app.calibracion.informe_entrevistas import informe_entrevistas, nueva_corrida
from app.calibracion.latex import paquete_overleaf, tex
from tests.fases.escenario import ENTREVISTA, montar
from tests.fakes import como_usuario

ENTREVISTA_DOC = {"entrevista_id": "E01", "proyecto_id": "P01", "titulo": "Dra. Ruiz", "estado": "lista"}


def sim(termino, s, ronda=0, decision=None, modelo="nomic"):
    decision = decision or ("aceptado_directo" if s is not None and s >= 0.75 else "en_debate")
    return {"tipo": "similitud", "ronda": ronda, "modelo": modelo,
            "payload": {"termino": termino, "similitud": s, "umbral": 0.75, "decision": decision, "modelo_embeddings": modelo}}


def par(s, ambiguo, tipo=None, termino=None, eid="E01"):
    return ({"entrevista_id": eid, "termino": termino or f"t{s}", "similitud": s, "tipo_ambiguedad": "lexica"},
            {"entrevista_id": eid, "termino": termino or f"t{s}", "ambiguo": ambiguo, "tipo": tipo})


# ---------------------------------------------------------------- de la bitácora

def test_similitudes_iniciales_con_su_via_y_sin_rondas_de_debate():
    b = {"mensajes": [
        {"tipo": "interpretaciones", "ronda": 0, "modelo": "qwen", "payload": {"resultados": [
            {"termino": "consultas", "tipo_ambiguedad": "lexica"}, {"termino": "da de alta", "tipo_ambiguedad": "regional"}]}},
        sim("consultas", 0.40),
        sim("da de alta", 0.91),
        sim("sin similitud", None),
        sim("consultas", 0.62, ronda=1),  # una ronda de debate: no es la similitud inicial
        {"tipo": "arbitraje", "ronda": 2, "payload": {"termino": "Consultas"}},
    ]}
    vs = {v["termino"]: v for v in similitudes_de_entrevista(ENTREVISTA_DOC, b)}
    assert set(vs) == {"consultas", "da de alta"}
    assert vs["consultas"]["similitud"] == 0.40 and vs["consultas"]["via"] == "arbitraje"
    assert vs["consultas"]["modelo_clasificador"] == "qwen" and vs["consultas"]["decision_real"] == "en_debate"
    assert vs["da de alta"]["via"] == "aceptado_directo" and vs["da de alta"]["tipo_ambiguedad"] == "regional"


def test_si_un_nodo_se_repitio_cuenta_el_ultimo_mensaje():
    b = {"mensajes": [sim("cita", 0.30), sim("cita", 0.80)]}
    [v] = similitudes_de_entrevista(ENTREVISTA_DOC, b)
    assert v["similitud"] == 0.80 and v["decision_real"] == "aceptado_directo"


def test_terminos_para_etiquetar_salen_del_ultimo_filtrado_sin_repetidos():
    b = {"mensajes": [{"tipo": "filtrado", "payload": {"terminos": [{"termino": "viejo"}]}},
                      {"tipo": "filtrado", "payload": {"terminos": [
                          {"termino": "Cita", "decision_filtro": "candidato"}, {"termino": "cita", "decision_filtro": "candidato"},
                          {"termino": "ahorita", "decision_filtro": "vaguedad"}]}}]}
    assert terminos_de_entrevista(b) == [{"termino": "Cita", "decision_filtro": "candidato"},
                                         {"termino": "ahorita", "decision_filtro": "vaguedad"}]


# ---------------------------------------------------------------- medidas

def test_auc_cuenta_los_empates_como_medio_y_vale_uno_si_separa():
    assert auc([par(0.2, True), par(0.9, False)]) == 1.0
    assert auc([par(0.9, True), par(0.2, False)]) == 0.0
    assert auc([par(0.5, True), par(0.5, False)]) == 0.5
    assert auc([par(0.5, True)]) is None  # falta una clase


def test_roc_va_de_cero_a_uno_y_es_monotona():
    pares = [par(0.2, True), par(0.4, False), par(0.5, True), par(0.9, False)]
    puntos = roc(pares)
    assert (puntos[0]["fpr"], puntos[0]["tpr"]) == (0.0, 0.0) and (puntos[-1]["fpr"], puntos[-1]["tpr"]) == (1.0, 1.0)
    assert all(a["fpr"] <= b["fpr"] and a["tpr"] <= b["tpr"] for a, b in zip(puntos, puntos[1:]))
    assert roc([par(0.2, True)]) == []


def test_confusion_y_por_tipo_con_el_umbral():
    pares = [par(0.3, True, "regional"), par(0.8, True, "lexica"), par(0.5, False), par(0.95, False)]
    c = confusion(pares, 0.75)
    assert (c["vp"], c["fn"], c["fp"], c["vn"]) == (1, 1, 1, 1)
    assert {m["tipo_error"] for m in c["mal_separados"]} == {"falso_negativo", "falso_positivo"}
    filas = {f["tipo"]: f for f in por_tipo(pares, 0.75)}
    assert filas["regional"]["a_debate"] == 1 and filas["lexica"]["a_debate"] == 0
    assert filas["no_ambiguo"] == {"tipo": "no_ambiguo", "ambiguo": False, "n": 2, "a_debate": 1, "proporcion": 0.5}


def test_el_bootstrap_es_reproducible_con_la_semilla():
    pares = [par(s / 20, s % 3 != 0) for s in range(20)]
    a, b = bootstrap(pares, 0.75, 300, 7), bootstrap(pares, 0.75, 300, 7)
    assert a == b and a["medidas"]["auc"]["bajo"] <= auc(pares) <= a["medidas"]["auc"]["alto"]
    assert bootstrap(pares, 0.75, 300, 8) != a


def test_el_informe_avisa_muestra_chica_y_etiquetas_vistas_con_el_sistema():
    b = {"mensajes": [sim("a", 0.3), sim("b", 0.9), sim("c", 0.6)]}
    docs = [{"entrevista_id": "E01", "anotador": "T", "a_ciegas": False,
             "etiquetas": [{"termino": "A", "ambiguo": True}, {"termino": "b", "ambiguo": False},
                           {"termino": "nunca llegó", "ambiguo": True}]}]
    r = informe_entrevistas([(ENTREVISTA_DOC, b)], docs, umbral_configurado=0.75, max_rondas=2, desde=0.5, hasta=0.95,
                            paso=0.05, remuestreos=100, semilla=1, proyecto_id="P01")
    gt = r["con_ground_truth"]
    assert gt["n_emparejados"] == 2 and gt["auc"] == 1.0 and gt["separacion"]["separa"] is True
    assert [e["termino"] for e in gt["etiquetas_sin_similitud"]] == ["nunca llegó"]
    assert [v["termino"] for v in gt["valores_sin_etiqueta"]] == ["c"]
    assert any("muestra chica" in a for a in r["avisos"]) and any("sesgado" in a for a in r["avisos"])
    assert [f["umbral"] for f in r["rejilla"] if f["configurado"]] == [0.75]
    assert {v["termino"]: v["ambiguo"] for v in r["valores"]} == {"a": True, "b": False, "c": None}


def test_sin_etiquetas_no_hay_contraste_y_se_dice():
    r = informe_entrevistas([(ENTREVISTA_DOC, {"mensajes": [sim("a", 0.3)]})], [], umbral_configurado=0.75, max_rondas=2,
                            desde=0.5, hasta=0.95, paso=0.05, remuestreos=100, semilla=1)
    assert r["con_ground_truth"] is None and any("sin ground truth" in a for a in r["avisos"])


# ---------------------------------------------------------------- paquete LaTeX

def _paquete(etiquetado=True):
    b = {"mensajes": [sim("consulta & 50%", 0.3), sim("cita_#1", 0.9), sim("alta", 0.6)]}
    docs = [{"entrevista_id": "E01", "anotador": "T", "a_ciegas": True,
             "etiquetas": [{"termino": "consulta & 50%", "ambiguo": True}, {"termino": "cita_#1", "ambiguo": False}]}] if etiquetado else []
    r = informe_entrevistas([(ENTREVISTA_DOC, b)], docs, umbral_configurado=0.75, max_rondas=2, desde=0.5, hasta=0.95,
                            paso=0.05, remuestreos=100, semilla=1, proyecto_id="P01")
    c = nueva_corrida("C01", r, nota="n", version="2.2.0", configuracion={"umbral": 0.75}, docs_etiquetas=docs)
    z = zipfile.ZipFile(io.BytesIO(paquete_overleaf(c)))
    return {n: z.read(n).decode() for n in z.namelist()}


def test_el_paquete_trae_figuras_tablas_y_datos_bien_formados():
    a = _paquete()
    assert {"main.tex", "estilo-dudamel.tex", "corrida.json", "LEEME.md", "figuras/roc.tex", "figuras/metricas.tex",
            "figuras/distribucion.tex", "figuras/debates.tex", "tablas/metricas.tex", "tablas/confusion.tex",
            "tablas/rejilla.tex", "tablas/por_tipo.tex", "tablas/valores.tex", "datos/rejilla.csv", "datos/roc.csv"} <= set(a)
    for nombre, texto in a.items():
        if nombre.endswith(".tex"):
            assert texto.count("{") == texto.count("}"), nombre
            assert sorted(re.findall(r"\\begin\{(\w+)\}", texto)) == sorted(re.findall(r"\\end\{(\w+)\}", texto)), nombre
    # cada figura que se usa existe, y cada CSV que una figura lee está en el paquete
    for usada in re.findall(r"\\input\{\\dudameldir/(figuras/\w+|tablas/\w+)\}", a["main.tex"]):
        assert f"{usada}.tex" in a
    for f in [x for x in a if x.startswith("figuras/")]:
        for csv_ in re.findall(r"\\dudameldir/(datos/[\w.]+)", a[f]):
            assert csv_ in a, (f, csv_)
    assert r"consulta \& 50\%" in a["tablas/valores.tex"] and r"cita\_\#1" in a["tablas/valores.tex"]
    assert json.loads(a["corrida.json"])["calibracion_id"] == "C01"


def test_sin_ground_truth_el_paquete_omite_lo_que_no_hay():
    a = _paquete(etiquetado=False)
    assert "figuras/roc.tex" not in a and "tablas/metricas.tex" not in a
    assert "figuras/roc" not in a["main.tex"] and "figuras/debates" in a["main.tex"]


def test_tex_escapa_los_caracteres_especiales():
    assert tex(r"a&b%c$d#e_f{g}h~i^j\k") == r"a\&b\%c\$d\#e\_f\{g\}h\textasciitilde{}i\textasciicircum{}j\textbackslash{}k"


# ---------------------------------------------------------------- por la API

@pytest.fixture
def cliente(tmp_path, analizador):
    srv, llm, p = montar(tmp_path, analizador)
    with TestClient(como_usuario(create_app(srv))) as c:
        c.srv, c.pid = srv, p.proyecto_id
        yield c


def test_etiquetar_guardar_una_corrida_y_exportarla(cliente):
    c, pid = cliente, cliente.pid
    eid = c.post(f"/proyectos/{pid}/entrevistas", json={"titulo": "Dra. Ruiz", "texto": ENTREVISTA}).json()["entrevista_id"]
    c.srv.cola.esperar(10)

    vivo = c.get(f"/proyectos/{pid}/calibracion/entrevistas").json()
    assert vivo["n_valores"] == 2 and vivo["con_ground_truth"] is None

    a_ciegas = c.get(f"/entrevistas/{eid}/etiquetas").json()
    assert a_ciegas["terminos"] and all("similitud" not in t for t in a_ciegas["terminos"])
    con_sistema = c.get(f"/entrevistas/{eid}/etiquetas", params={"sistema": True}).json()
    assert {t["termino"] for t in con_sistema["terminos"] if "similitud" in t} == {"consultas", "da de alta"}

    r = c.put(f"/entrevistas/{eid}/etiquetas", json={"anotador": "Tesista", "a_ciegas": True, "etiquetas": [
        {"termino": "consultas", "ambiguo": True, "tipo": "lexica"},
        {"termino": "da de alta", "ambiguo": False, "tipo": "regional"}]})
    assert r.status_code == 200 and r.json()["etiquetas"][1]["tipo"] is None  # no ambiguo: sin tipo

    gt = c.get(f"/proyectos/{pid}/calibracion/entrevistas").json()["con_ground_truth"]
    assert gt["n_emparejados"] == 2 and gt["auc"] == 1.0

    corrida = c.post(f"/proyectos/{pid}/calibraciones", json={"nota": "primera"})
    assert corrida.status_code == 201, corrida.text
    cid = corrida.json()["calibracion_id"]
    assert corrida.json()["auc"] == 1.0 and corrida.json()["n_emparejados"] == 2
    assert [x["calibracion_id"] for x in c.get(f"/proyectos/{pid}/calibraciones").json()] == [cid]
    completa = c.get(f"/calibraciones/{cid}").json()
    assert completa["version_app"] == "2.4.0" and completa["entrevistas"][0]["huella_similitudes"]

    z = c.get(f"/calibraciones/{cid}/overleaf.zip")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    assert "main.tex" in zipfile.ZipFile(io.BytesIO(z.content)).namelist()

    assert c.delete(f"/calibraciones/{cid}").status_code == 204
    assert c.get(f"/calibraciones/{cid}").status_code == 404


def test_sin_similitudes_no_se_guarda_una_corrida_y_borrar_la_entrevista_quita_sus_etiquetas(cliente):
    c, pid = cliente, cliente.pid
    assert c.post(f"/proyectos/{pid}/calibraciones", json={}).status_code == 422
    eid = c.post(f"/proyectos/{pid}/entrevistas", json={"titulo": "Dra. Ruiz", "texto": ENTREVISTA}).json()["entrevista_id"]
    c.srv.cola.esperar(10)
    c.put(f"/entrevistas/{eid}/etiquetas", json={"anotador": "T", "etiquetas": [{"termino": "consultas", "ambiguo": True}]})
    assert c.delete(f"/entrevistas/{eid}").status_code in (200, 204)
    assert c.srv.repo.obtener_doc("etiquetas_entrevista", eid) is None
