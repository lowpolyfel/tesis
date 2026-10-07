"""Especificación funcional / no funcional y Big Picture de una selección de requisitos (ADR 0017)."""
from app.artefactos import big_picture_proyecto, especificacion_proyecto, formas, metas_proyecto
from tests.artefactos.ayudantes import documentos, lel, trazas


def _docs_clasificados():
    docs = documentos()
    docs[0].update(tipo_requisito="funcional", categoria=None, supuestos=[])
    docs[1].update(tipo_requisito="no_funcional", categoria="rendimiento",
                   supuestos=["«ahorita» se concretó como «en menos de 5 segundos»"], corregido="2026-10-07")
    docs[2].update(tipo_requisito="funcional", categoria="seguridad", supuestos=[])  # categoría que sobra
    return docs


def test_especificacion_separa_funcionales_y_no_funcionales():
    e = especificacion_proyecto(_docs_clasificados(), lel(), trazas())
    formas.Especificacion.model_validate(e)
    assert [(r["clave"], r["req_id"]) for r in e["funcionales"]] == [("RF-01", "R01"), ("RF-02", "R03")]
    assert [(r["clave"], r["req_id"], r["categoria"]) for r in e["no_funcionales"]] == [("RNF-01", "R02", "rendimiento")]
    assert e["funcionales"][1]["categoria"] is None  # un funcional no lleva categoría
    nf = e["no_funcionales"][0]
    assert nf["supuestos"] and nf["corregido"] == "2026-10-07" and nf["reescrito"] == nf["original"]
    assert e["sin_clasificar"] == []
    assert {g["simbolo"] for g in e["glosario"]} >= {"sesión", "usuario", "bitácora"}
    assert [f["req_id"] for f in e["requisitos_fuera"]] == ["R04", "R05", "R06", "R07", "R08", "R09"]


def test_documentos_anteriores_a_la_clasificacion_quedan_sin_clasificar():
    e = especificacion_proyecto(documentos(), lel(), trazas())
    assert e["funcionales"] == [] and e["no_funcionales"] == []
    assert [(r["clave"], r["tipo_requisito"]) for r in e["sin_clasificar"]] == [("R01", None), ("R02", None), ("R03", None)]


def test_especificacion_de_una_seleccion():
    e = especificacion_proyecto(_docs_clasificados(), lel(), trazas(), solo={"R02", "R05"})
    assert e["funcionales"] == [] and [r["req_id"] for r in e["no_funcionales"]] == ["R02"]
    assert [f["req_id"] for f in e["requisitos_fuera"]] == ["R05"]


def test_big_picture_de_una_seleccion():
    completo = big_picture_proyecto(documentos(), lel(), trazas())
    bp = big_picture_proyecto(documentos(), lel(), trazas(), solo={"R01"})
    formas.BigPicture.model_validate(bp)
    requisitos = [n["id"] for n in bp["nodos"] if n["tipo"] == "requisito"]
    assert requisitos == ["R01"]
    assert all(m["req_ids"] == ["R01"] for m in bp["nodos"] if m["tipo"] in ("meta", "tarea"))
    simbolos = {n["etiqueta"] for n in bp["nodos"] if n["tipo"] == "simbolo"}
    assert "sesión" in simbolos and "dar de alta" not in simbolos and "expediente" not in simbolos
    assert len(simbolos) < sum(n["tipo"] == "simbolo" for n in completo["nodos"])
    ids = {n["id"] for n in bp["nodos"]}
    assert all(a["origen"] in ids and a["destino"] in ids for a in bp["aristas"])
    assert "R02" not in bp["mermaid"] and "R03" not in bp["mermaid"]
    assert [r["req_id"] for r in bp["panorama"]["requisitos"]] == ["R01"]
    assert bp["requisitos_fuera"] == []


def test_metas_de_una_seleccion():
    m = metas_proyecto(documentos(), lel(), trazas(), solo={"R03"})
    assert {x["req_id"] for x in m["metas"]} == {"R03"}
