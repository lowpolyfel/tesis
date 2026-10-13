"""El flujo de la versión 2 por la API (ADR 0024): entrevista → LEL → mapa → metas → requisitos."""
import json

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from tests.fases.escenario import ENTREVISTA, montar
from tests.fakes import como_usuario


@pytest.fixture
def cliente(tmp_path, analizador):
    srv, llm, p = montar(tmp_path, analizador)
    with TestClient(como_usuario(create_app(srv))) as c:
        c.esperar = lambda: srv.cola.esperar(10)
        c.pid, c.llm = p.proyecto_id, llm
        yield c


def flujo(c, ruta):
    r = c.post(ruta)
    assert r.status_code == 200, r.text
    eventos = [json.loads(x) for x in r.text.splitlines() if x.strip()]
    assert eventos[-1]["tipo"] == "resultado", eventos[-1]
    return eventos


def fase(c, f):
    return next(x for x in c.get(f"/proyectos/{c.pid}/fases").json()["fases"] if x["id"] == f)


def test_de_la_entrevista_a_la_especificacion(cliente):
    c, pid = cliente, cliente.pid
    previa = c.post(f"/proyectos/{pid}/entrevistas/vista-previa", json={"texto": ENTREVISTA}).json()
    assert previa["modo"] == "hablantes" and len(previa["turnos"]) == 7
    assert previa["hablantes"][0] == {"nombre": "Entrevistador", "turnos": 3, "preguntas": 3, "rol_probable": "entrevistador"}

    assert fase(c, "lexico")["disponible"] is False
    r = c.post(f"/proyectos/{pid}/entrevistas", json={"titulo": "Dra. Ruiz", "texto": ENTREVISTA})
    assert r.status_code == 202 and r.json()["entrevista_id"] == "E01" and "turnos" not in r.json()
    c.esperar()
    e = c.get("/entrevistas/E01").json()
    assert e["estado"] == "lista" and e["n_turnos"] == 7
    eventos = c.get("/entrevistas/E01/eventos").text
    assert "event: mensaje" in eventos and "event: fin" in eventos

    # el mapa no se abre hasta validar el léxico
    assert c.post(f"/proyectos/{pid}/fases/mapa/generar").status_code == 409
    lex = c.get(f"/proyectos/{pid}/lexico").json()
    assert lex["resumen"]["propuesto"] == 7 and lex["entradas"][0]["simbolo"] == "consulta"  # lo ambiguo primero
    ids = {x["simbolo"]: x["entrada_id"] for x in lex["entradas"]}

    corregida = c.post(f"/lexico/{ids['consulta']}/corregir", json={"alternativa": "I1", "cambios": {
        "impacto": ["Queda en el expediente del paciente."]}}).json()
    assert corregida["estado"] == "corregido" and corregida["nocion"] == ["cita médica con un paciente"]
    assert corregida["impacto"] == ["Queda en el expediente del paciente."]
    assert c.post(f"/lexico/{ids['consulta']}/corregir", json={"alternativa": "I9"}).status_code == 409
    assert c.post(f"/lexico/{ids['receta']}/descartar", json={"motivo": "no"}).json()["estado"] == "descartado"
    assert c.post(f"/lexico/{ids['receta']}/validar").status_code == 409
    assert c.post(f"/lexico/{ids['receta']}/restaurar").json()["estado"] == "propuesto"
    assert c.post(f"/lexico/{ids['receta']}/validar").json()["estado"] == "validado"
    hechas = c.post(f"/proyectos/{pid}/lexico/validar-sin-ambiguedad").json()["validadas"]
    assert len(hechas) == 4  # paciente, asistente, cita, expediente (dar de alta tuvo dos intenciones)
    assert fase(c, "lexico")["hecho"] is False
    c.post(f"/lexico/{ids['dar de alta']}/validar")
    nuevo = c.post(f"/proyectos/{pid}/lexico", json={"simbolo": "diagnóstico", "tipo": "objeto",
                                                      "nocion": ["Lo que concluye el doctor."], "intencion": "Saber qué tiene"})
    assert nuevo.status_code == 201 and nuevo.json()["via"] == "persona"
    assert c.post(f"/proyectos/{pid}/lexico", json={"simbolo": "Consultas", "tipo": "objeto", "nocion": ["x"],
                                                    "intencion": "x"}).status_code == 409
    memoria = c.get(f"/proyectos/{pid}/memoria").json()
    assert {a["simbolo"] for a in memoria} >= {"consulta", "dar de alta", "diagnóstico"}
    assert fase(c, "lexico")["hecho"] is True

    # mapa conceptual con propósito
    ev = flujo(c, f"/proyectos/{pid}/fases/mapa/generar")
    mapa = ev[-1]["documento"]
    contenido = mapa["contenido"]
    assert contenido["proposito"].startswith("¿Cómo")
    assert {x["etiqueta"]: x["simbolo"] for x in contenido["conceptos"]} == {
        "Consulta": "consulta", "Paciente": "paciente", "Expediente": "expediente", "Receta": "receta",
        "Asistente": "asistente"}  # «Nube» no tenía relaciones y no está en el LEL
    assert [r["id"] for r in contenido["relaciones"]] == ["R1", "R2", "R3", "R4"]  # sin repetidas ni lazos
    assert mapa["estado"] == "propuesto" and fase(c, "metas")["disponible"] is False
    assert "-- \"recibe\" -->" in c.get(f"/proyectos/{pid}/fases/mapa/mermaid").text

    contenido["conceptos"][0]["etiqueta"] = "Consulta médica"
    contenido["conceptos"][0]["x"], contenido["conceptos"][0]["y"] = 10.0, 20.0
    contenido["relaciones"].append({"id": "R5", "origen": "C3", "enlace": "pertenece a", "destino": "C2",
                                    "validado": True, "autor": "persona"})
    malo = {**contenido, "relaciones": [*contenido["relaciones"], {"id": "R6", "origen": "C3", "enlace": "x",
                                                                    "destino": "C99"}]}
    assert c.put(f"/proyectos/{pid}/fases/mapa", json={"contenido": malo}).status_code == 422
    for x in contenido["conceptos"] + contenido["relaciones"]:
        x["validado"] = True
    contenido["proposito_validado"] = True
    editado = c.put(f"/proyectos/{pid}/fases/mapa", json={"contenido": contenido}).json()
    assert editado["documento"]["estado"] == "validado" and editado["hecho"] is True
    cambios = editado["documento"]["historial"][-1]["cambios"]
    assert "renombró «Consulta» como «Consulta médica»" in cambios and any(x.startswith("unió") for x in cambios)

    # metas en tres niveles
    metas = flujo(c, f"/proyectos/{pid}/fases/metas/generar")[-1]["documento"]
    ms = {m["id"]: m for m in metas["contenido"]["metas"]}
    assert [m["nivel"] for m in ms.values()] == ["organizacional", "estrategica", "estrategica", "especifica",
                                                 "especifica", "especifica"]
    assert ms["MS1"]["evidencia"] == ["E01:T3", "E01:T7"] and ms["MS2"]["evidencia"] == ["E01:T7"]
    assert ms["ME1"]["simbolos"] == ["consulta"] and ms["MS1"]["indicador"]
    assert any("nube" in a for a in metas["avisos"])
    todas = metas["contenido"]["metas"]
    for m in todas:
        m["validada"] = True
    huerfana = [*todas, {"id": "MS9", "nivel": "especifica", "enunciado": "x", "contribuye_a": "MO1"}]
    assert c.put(f"/proyectos/{pid}/fases/metas", json={"contenido": {"metas": huerfana}}).status_code == 422
    assert c.put(f"/proyectos/{pid}/fases/metas", json={"contenido": {"metas": todas}}).json()["hecho"] is True

    # requisitos
    reqs = flujo(c, f"/proyectos/{pid}/fases/requisitos/generar")[-1]["documento"]
    rs = {r["id"]: r for r in reqs["contenido"]["requisitos"]}
    assert list(rs) == ["RF01", "RNF01", "RF02"]
    assert rs["RNF01"]["categoria"] == "rendimiento" and "expresión vaga: rápido" in rs["RNF01"]["avisos"]
    assert rs["RF01"]["simbolos"] == ["consulta", "paciente", "receta", "diagnóstico"] and rs["RF01"]["avisos"] == []
    assert rs["RF02"]["supuestos"] == ["Una cita dura 30 minutos."]
    lista = reqs["contenido"]["requisitos"]
    lista[1]["texto"] = "El sistema debe mostrar el expediente de un paciente en menos de 2 segundos."
    lista[1]["criterios"] = ["Se abre en menos de 2 segundos."]
    for r in lista:
        r["validado"] = True
    hecho = c.put(f"/proyectos/{pid}/fases/requisitos", json={"contenido": {"requisitos": lista}}).json()
    assert hecho["hecho"] is True and hecho["documento"]["contenido"]["requisitos"][1]["avisos"] == []
    estado = c.get(f"/proyectos/{pid}/fases").json()
    assert estado["siguiente"] is None and all(f["hecho"] for f in estado["fases"])

    md = c.get(f"/proyectos/{pid}/fases/requisitos/markdown")
    assert md.headers["content-type"].startswith("text/markdown")
    for parte in ("# Especificación de requisitos — Consultorio", "### RF01", "## Matriz de trazabilidad",
                  "**consulta**: llevar el registro de las atenciones. No significa: búsqueda en la base de datos.",
                  "- **MS1** Registrar cada consulta"):
        assert parte in md.text, parte

    # si el léxico cambia, el mapa deja de estar al día y lo que sigue también
    c.post(f"/lexico/{ids['cita']}/corregir", json={"cambios": {"intencion": "Apartar un horario con la doctora"}})
    f = c.get(f"/proyectos/{pid}/fases").json()
    assert [x["hecho"] for x in f["fases"]] == [True, True, False, False, False]
    assert c.post(f"/proyectos/{pid}/fases/mapa/conservar").json()["al_dia"] is True
    assert fase(c, "metas")["al_dia"] is False

    # borrar el proyecto se lleva todo
    assert c.delete(f"/proyectos/{pid}").status_code == 204
    srv = c.app.state.servicio
    for coleccion in ("entrevistas", "bitacoras", "lexico", "memoria", "fase_mapa", "fase_metas", "fase_requisitos"):
        assert srv.repo.listar_docs(coleccion, proyecto_id=pid) == [], coleccion


def test_archivo_y_errores(cliente):
    c, pid = cliente, cliente.pid
    r = c.post(f"/proyectos/{pid}/entrevistas/archivo",
               files={"archivo": ("dra-ruiz.txt", ENTREVISTA.encode(), "text/plain")}).json()
    assert r["titulo"] == "dra-ruiz" and r["origen"]["tipo"] == "txt"
    again = c.post(f"/proyectos/{pid}/entrevistas/vista-previa", json={"texto": r["texto"]}).json()
    assert [t["texto"] for t in again["turnos"]] == [t["texto"] for t in r["vista"]["turnos"]]
    assert c.post(f"/proyectos/{pid}/entrevistas/archivo",
                  files={"archivo": ("x.docx", b"PK..", "application/vnd.openxmlformats")}).status_code == 415
    assert c.post(f"/proyectos/{pid}/entrevistas", json={"titulo": " ", "texto": "x"}).status_code == 422
    assert c.get("/entrevistas/E42").status_code == 404
    assert c.get("/lexico/S42").status_code in (404, 405)
    assert c.post("/lexico/S42/validar").status_code == 404
    assert c.get(f"/proyectos/{pid}/fases/mapa").json() == {
        "documento": None, "al_dia": False, "disponible": False, "motivo": "Primero valida el léxico.",
        "hecho": False, "generando": False}
    assert c.put(f"/proyectos/{pid}/fases/mapa", json={"contenido": {}}).status_code == 404
    assert c.post(f"/proyectos/{pid}/entrevistas/E01/x").status_code == 404
