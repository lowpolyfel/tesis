"""Registro de documentos en la colección `documentos` (sin servicio ni spaCy)."""
import pytest

from app.config import Settings
from app.db import RepositorioJson
from app.documentos import COLECCION, DemasiadoGrande, Documentos, SinTexto, almacen
from tests.documentos.muestras import REQUISITOS_SRS, pdf_srs
from tests.documentos.pdf_prueba import pdf_con_tounicode, pdf_sin_texto


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


def _lista(n: int) -> bytes:
    return ("El sistema deberá permitir:\n" + "- registrar usuarios\n" * n).encode()


def test_documento_que_no_cabe_se_rechaza_sin_guardar(documentos, monkeypatch):
    """Lo propuesto puede pesar varias veces el archivo (una lista bajo una frase introductoria):
    Mongo no acepta un documento de más de 16 MiB."""
    monkeypatch.setattr(almacen, "MAX_BYTES_GUARDADOS", 20_000)
    with pytest.raises(DemasiadoGrande) as e:
        documentos.cargar("P01", "lista.txt", _lista(200))
    assert "(200 requisitos)" in str(e.value) and "máximo es 0.0190735 MB por documento" in str(e.value)
    assert documentos.repo.listar_docs(COLECCION) == []


def test_sin_texto_por_pagina_si_asi_cabe(documentos, monkeypatch):
    sin_texto = len(documentos.cargar("P01", "a.txt", _lista(100)).model_copy(
        update={"texto_por_pagina": None}).model_dump_json().encode())
    monkeypatch.setattr(almacen, "MAX_BYTES_GUARDADOS", sin_texto + 300)  # la advertencia nueva cabe
    d = documentos.cargar("P01", "a.txt", _lista(100))
    assert d.texto_por_pagina is None and len(d.requisitos_propuestos) == 100
    assert d.advertencias[-1].startswith("El texto por página no se guardó: el documento pasaba de ")
    assert len(documentos.repo.listar_docs(COLECCION)) == 2


def test_lo_guardado_cabe_en_utf8_y_en_bson(documentos):
    """Un sustituto UTF-16 suelto (mapa ToUnicode dañado) hacía fallar la escritura con 500."""
    import bson

    contenido = pdf_con_tounicode("El sistema debe registrar A usuarios.", {"A": 0xD83D})
    d = documentos.cargar("P01", "emoji.pdf", contenido)
    assert d.requisitos_propuestos[0].texto == "El sistema debe registrar � usuarios."
    assert "contiene caracteres no reconocidos: revisa la extracción" in d.requisitos_propuestos[0].advertencias
    bson.encode(documentos.repo.obtener_doc(COLECCION, d.documento_id))
