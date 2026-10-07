"""Registro de documentos en la colección `documentos` (sin servicio ni spaCy)."""
import pytest

from app.config import Settings
from app.db import RepositorioJson
from app.documentos import COLECCION, Documentos, SinTexto, almacen
from tests.documentos.muestras import REQUISITOS_SRS, pdf_srs
from tests.documentos.pdf_prueba import pdf_sin_texto


@pytest.fixture
def documentos(tmp_path):
    settings = Settings(_env_file=None, resultados_dir=str(tmp_path / "resultados"), documento_max_mb=1)
    return Documentos(RepositorioJson(settings.ruta(settings.resultados_dir)), settings)


def test_cargar_guarda_documento_con_texto_por_pagina(documentos):
    d = documentos.cargar("P01", "C:\\fakepath\\srs.pdf", pdf_srs(), "application/pdf")
    assert (d.documento_id, d.proyecto_id, d.archivo, d.tipo, d.paginas) == ("D01", "P01", "srs.pdf", "pdf", 3)
    assert len(d.texto_por_pagina) == 3 and d.caracteres == sum(len(p) for p in d.texto_por_pagina)
    assert [(r.marca, r.pagina, r.texto) for r in d.requisitos_propuestos] == REQUISITOS_SRS
    guardado = documentos.repo.obtener_doc(COLECCION, "D01")
    assert guardado["texto_por_pagina"] == d.texto_por_pagina and documentos.obtener("D01") == d

    documentos.cargar("P02", "otro.txt", b"El sistema debe salir.", "text/plain")
    assert [(r.documento_id, r.total_requisitos, r.total_descartados) for r in documentos.listar("P01")] == [("D01", 5, 4)]
    assert [r.documento_id for r in documentos.listar("P02")] == ["D02"]
    assert documentos.obtener("D99") is None and documentos.obtener("../x") is None


def test_origen_listo_para_registrar_el_requisito(documentos):
    d = documentos.cargar("P01", "srs.pdf", pdf_srs())
    origen = d.origen(d.requisitos_propuestos[0])
    assert origen.model_dump(exclude_none=True) == {
        "documento_id": "D01", "archivo": "srs.pdf", "pagina": 1, "indice": 1, "marca": "RF-01",
        "texto_original": d.requisitos_propuestos[0].texto_original}


def test_error_no_guarda_nada(documentos):
    with pytest.raises(SinTexto):
        documentos.cargar("P01", "escaneo.pdf", pdf_sin_texto())
    assert documentos.repo.listar_docs(COLECCION) == []


def test_texto_muy_grande_no_se_guarda_y_se_advierte(documentos, monkeypatch):
    monkeypatch.setattr(almacen, "MAX_CARACTERES_GUARDADOS", 10)
    d = documentos.cargar("P01", "a.txt", "El sistema debe guardar la bitácora.".encode())
    assert d.texto_por_pagina is None and d.advertencias[-1].startswith("El texto por página no se guardó")
    assert len(d.requisitos_propuestos) == 1


def test_documento_sin_requisitos_se_guarda_con_advertencia(documentos):
    d = documentos.cargar("P01", "notas.txt", "Introducción\nEste documento describe el sistema.".encode())
    assert d.requisitos_propuestos == [] and d.total_descartados == 2
    assert d.advertencias == [("No se encontró ninguna oración con verbo de obligación o capacidad: "
                               "revisa los fragmentos descartados.")]
