"""Rutas de documentos con TestClient sobre una app mínima (proyectos + documentos)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import documentos, proyectos
from app.documentos import almacen, extraccion
from tests.documentos.muestras import (
    DESCARTADOS_SRS,
    ENCABEZADO,
    REQUISITOS_SRS,
    pdf_srs,
)
from tests.documentos.pdf_prueba import pdf_con_operadores, pdf_con_tounicode, pdf_sin_texto
from tests.escenarios import montar

CAMPOS_DOCUMENTO = {"documento_id", "proyecto_id", "archivo", "tipo", "paginas", "caracteres", "creado",
                    "requisitos_propuestos", "fragmentos_descartados", "total_descartados", "advertencias",
                    "texto_por_pagina"}
CAMPOS_REQUISITO = {"indice", "texto", "pagina", "marca", "texto_original", "advertencias"}


def _cliente(tmp_path, analizador, **ajustes):
    srv, _, _ = montar(tmp_path, analizador, {}, **ajustes)
    app = FastAPI()
    app.include_router(proyectos.router)
    app.include_router(documentos.router)
    app.state.servicio = srv
    cliente = TestClient(app)
    cliente.srv = srv
    assert cliente.post("/proyectos", json={"nombre": "Nómina"}).json()["proyecto_id"] == "P01"
    return cliente


@pytest.fixture
def cliente(tmp_path, analizador):
    return _cliente(tmp_path, analizador)


def _subir(cliente, nombre, contenido, tipo="application/pdf", proyecto="P01"):
    return cliente.post(f"/proyectos/{proyecto}/documentos", files={"archivo": (nombre, contenido, tipo)})


def test_cargar_pdf_listar_y_obtener(cliente):
    r = _subir(cliente, "srs.pdf", pdf_srs())
    assert r.status_code == 201
    d = r.json()
    assert set(d) == CAMPOS_DOCUMENTO
    assert (d["documento_id"], d["proyecto_id"], d["archivo"], d["tipo"], d["paginas"]) == ("D01", "P01", "srs.pdf", "pdf", 3)
    assert all(set(x) == CAMPOS_REQUISITO for x in d["requisitos_propuestos"])
    assert [(x["marca"], x["pagina"], x["texto"]) for x in d["requisitos_propuestos"]] == REQUISITOS_SRS
    assert [(f["texto"], f["pagina"], f["marca"], f["motivo"]) for f in d["fragmentos_descartados"]] == DESCARTADOS_SRS
    assert d["total_descartados"] == 4
    assert f"Encabezado o pie de página quitado (3 de 3 páginas): «{ENCABEZADO}»." in d["advertencias"]

    resumenes = cliente.get("/proyectos/P01/documentos").json()
    assert resumenes == [{"documento_id": "D01", "proyecto_id": "P01", "archivo": "srs.pdf", "tipo": "pdf", "paginas": 3,
                          "caracteres": d["caracteres"], "creado": d["creado"], "total_requisitos": 5,
                          "total_descartados": 4}]
    assert cliente.get("/proyectos/P00/documentos").json() == []
    assert cliente.get("/documentos/D01").json() == d
    assert cliente.get("/documentos/D02").status_code == 404
    assert cliente.get("/proyectos/P42/documentos").status_code == 404


def test_confirmar_lo_propuesto_conserva_el_origen(cliente):
    d = _subir(cliente, "srs.pdf", pdf_srs()).json()
    requisitos = [{"texto": x["texto"], "origen": {"documento_id": d["documento_id"], "archivo": d["archivo"],
                                                   "pagina": x["pagina"], "indice": x["indice"], "marca": x["marca"],
                                                   "texto_original": x["texto_original"]}}
                  for x in d["requisitos_propuestos"]]
    requisitos[0]["texto"] = "El sistema deberá calcular la nómina quincenal de cada empleado."  # el humano edita
    r = cliente.post("/proyectos/P01/requisitos", json={"requisitos": requisitos})
    assert r.status_code == 202 and r.json()["req_ids"] == ["R01", "R02", "R03", "R04", "R05"]
    traza = cliente.srv.traza("R01")
    assert traza.texto == "El sistema deberá calcular la nómina quincenal de cada empleado."
    assert (traza.origen.documento_id, traza.origen.pagina, traza.origen.marca, traza.origen.indice) == ("D01", 1, "RF-01", 1)
    assert traza.origen.texto_original.startswith("RF-01: El sistema deberá calcular")
    assert cliente.srv.traza("R05").origen.marca == "REQ-12"


def test_txt_latin1(cliente):
    texto = "Módulo de nómina\nEl cajero podrá cobrar en pesos.\nEl año fiscal empieza en enero."
    r = _subir(cliente, "requisitos.txt", texto.encode("latin-1"), "text/plain")
    assert r.status_code == 201
    d = r.json()
    assert (d["tipo"], d["paginas"]) == ("txt", 1)
    assert [(x["texto"], x["pagina"], x["marca"]) for x in d["requisitos_propuestos"]] == [
        ("El cajero podrá cobrar en pesos.", None, None)]
    assert [(f["texto"], f["motivo"]) for f in d["fragmentos_descartados"]] == [
        ("Módulo de nómina", "titulo"), ("El año fiscal empieza en enero.", "sin_verbo_obligacion")]
    assert "no estaba en UTF-8" in d["advertencias"][0]


def test_pdf_sin_texto_422(cliente):
    r = _subir(cliente, "escaneo.pdf", pdf_sin_texto(2))
    assert r.status_code == 422 and "OCR" in r.json()["detail"] and "CONTEXTO §9" in r.json()["detail"]
    assert cliente.get("/proyectos/P01/documentos").json() == []


def test_pdf_ilegible_422(cliente):
    assert _subir(cliente, "roto.pdf", b"%PDF-1.4 sin objetos").status_code == 422


def test_tipo_no_soportado_415(cliente):
    r = _subir(cliente, "srs.docx", b"PK\x03\x04datos",
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert r.status_code == 415


def test_proyecto_inexistente_404(cliente):
    assert _subir(cliente, "srs.pdf", pdf_srs(), proyecto="P42").status_code == 404


def test_sin_archivo_422(cliente):
    assert cliente.post("/proyectos/P01/documentos").status_code == 422


def test_tamano_excedido_413(tmp_path, analizador):
    cliente = _cliente(tmp_path, analizador, documento_max_mb=0.001)  # 1048 bytes
    assert len(pdf_srs()) > 1048
    r = _subir(cliente, "srs.pdf", pdf_srs())
    assert r.status_code == 413 and "DOCUMENTO_MAX_MB" in r.json()["detail"]
    assert cliente.post("/requisitos/separar", json={"texto": "El sistema debe x. " * 100}).status_code == 413
    assert _subir(cliente, "corto.txt", b"El sistema debe guardar.", "text/plain").status_code == 201


def test_separar_texto_sin_guardar(cliente):
    r = cliente.post("/requisitos/separar", json={"texto": "Requisitos\nRF-01 El sistema debe registrar la sesión.\n"
                                                          "Esto es contexto. El usuario podrá salir."})
    assert r.status_code == 200
    assert r.json() == {
        "requisitos_propuestos": [
            {"indice": 1, "texto": "El sistema debe registrar la sesión.", "pagina": None, "marca": "RF-01",
             "texto_original": "RF-01 El sistema debe registrar la sesión.", "advertencias": []},
            {"indice": 2, "texto": "El usuario podrá salir.", "pagina": None, "marca": None,
             "texto_original": "El usuario podrá salir.", "advertencias": []}],
        "fragmentos_descartados": [
            {"texto": "Requisitos", "pagina": None, "marca": None, "motivo": "titulo"},
            {"texto": "Esto es contexto.", "pagina": None, "marca": None, "motivo": "sin_verbo_obligacion"}],
        "total_descartados": 2,
        "advertencias": []}
    assert cliente.srv.repo.listar_docs("documentos") == []
    assert cliente.post("/requisitos/separar", json={"texto": ""}).status_code == 422
    assert cliente.post("/requisitos/separar", json={"texto": "x", "otro": 1}).status_code == 422


def test_lo_que_la_separacion_advierte_por_largo_es_lo_que_la_carga_rechaza(cliente):
    def oracion(n: int) -> str:
        return "El sistema debe registrar " + ", ".join(f"el campo {i} del formulario" for i in range(n)) + "."

    propuestos = cliente.post("/requisitos/separar", json={"texto": f"{oracion(100)}\n{oracion(60)}\n{oracion(3)}"}
                              ).json()["requisitos_propuestos"]
    largos = [p for p in propuestos if any("lo más que acepta la carga" in a for a in p["advertencias"])]
    aceptables = [p for p in propuestos if p not in largos]
    assert len(largos) == 1 and len(aceptables) == 2
    cargar = cliente.post("/proyectos/P01/requisitos", json={"requisitos": [{"texto": p["texto"]} for p in aceptables]})
    assert cargar.status_code == 202
    assert cliente.post("/proyectos/P01/requisitos", json={"requisitos": [{"texto": largos[0]["texto"]}]}).status_code == 422


def test_pdf_con_media_pareja_sustituta_201(cliente):
    r = _subir(cliente, "emoji.pdf", pdf_con_tounicode("El sistema debe registrar A usuarios.", {"A": 0xD83D}))
    assert r.status_code == 201
    d = r.json()
    assert d["requisitos_propuestos"][0]["texto"] == "El sistema debe registrar � usuarios."
    assert cliente.get(f"/documentos/{d['documento_id']}").json() == d


def test_documento_que_no_cabe_413_sin_guardar(cliente, monkeypatch):
    monkeypatch.setattr(almacen, "MAX_BYTES_GUARDADOS", 20_000)
    lista = ("El sistema deberá permitir:\n" + "- registrar usuarios\n" * 200).encode()
    r = _subir(cliente, "lista.txt", lista, "text/plain")
    assert r.status_code == 413 and "divide el archivo" in r.json()["detail"]
    assert cliente.get("/proyectos/P01/documentos").json() == []


def test_pdf_pesado_422_explicado(cliente, monkeypatch):
    monkeypatch.setattr(extraccion, "MAX_BYTES_OPERADORES_PAGINA", 2**19)
    r = _subir(cliente, "dibujo.pdf", pdf_con_operadores([b"0 0 m\n" * 100_000]))
    assert r.status_code == 422 and "operadores de dibujo" in r.json()["detail"]
    assert "escaneo" not in r.json()["detail"]
