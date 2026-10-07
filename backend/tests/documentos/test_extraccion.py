"""Del archivo al texto por página: PDF generados en la prueba y texto plano."""
import codecs

import pytest

from app.documentos.extraccion import (
    DemasiadoGrande,
    Ilegible,
    SinTexto,
    TipoNoSoportado,
    decodificar,
    leer,
    nombre_de_archivo,
    tipo_de,
)
from tests.documentos.muestras import ENCABEZADO, pdf_srs
from tests.documentos.pdf_prueba import pdf, pdf_mixto, pdf_sin_texto

MAX = 10 * 1024 * 1024
ACENTOS = "Programación: año, señal, ¿qué?, ¡sí!, pingüino, ÁÉÍÓÚ Ñ Ü «comillas» “curvas” – raya"


def test_pypdf_extrae_acentos_y_enie_de_winansi():
    extraido = leer("acentos.pdf", pdf([[ACENTOS, "El módulo de compañía debe validar el año."]]), MAX)
    assert extraido.tipo == "pdf" and extraido.con_paginas
    assert extraido.paginas[0].splitlines() == [ACENTOS, "El módulo de compañía debe validar el año."]
    assert extraido.advertencias == []


def test_pdf_de_varias_paginas_conserva_cada_pagina():
    extraido = leer("srs.pdf", pdf_srs(), MAX)
    assert len(extraido.paginas) == 3
    assert all(p.splitlines()[0] == ENCABEZADO for p in extraido.paginas)
    assert extraido.paginas[2].splitlines()[-1] == "Página 3 de 3"


def test_pdf_sin_texto_extraible_no_se_procesa_sin_ocr():
    with pytest.raises(SinTexto) as e:
        leer("escaneo.pdf", pdf_sin_texto(2), MAX)
    assert "OCR" in str(e.value) and "CONTEXTO §9" in str(e.value)


def test_pagina_sin_texto_entre_otras_se_advierte():
    extraido = leer("mixto.pdf", pdf_mixto([["El sistema debe guardar."], None, ["El sistema debe salir."]]), MAX)
    assert extraido.paginas[1] == ""
    assert extraido.advertencias == ["Páginas sin texto extraíble (¿escaneadas? sin OCR): 2."]


@pytest.mark.parametrize("contenido", [b"%PDF-1.4\nbasura sin objetos", b"no es un pdf"])
def test_pdf_ilegible(contenido):
    with pytest.raises(Ilegible):
        leer("roto.pdf", contenido, MAX)


def test_tamano_maximo():
    with pytest.raises(DemasiadoGrande) as e:
        leer("grande.txt", b"x" * 2049, 2048)
    assert "DOCUMENTO_MAX_MB" in str(e.value)
    assert leer("justo.txt", b"x" * 2048, 2048).paginas == ["x" * 2048]


@pytest.mark.parametrize("nombre, contenido, tipo_contenido", [
    ("requisitos.docx", b"PK\x03\x04", None),
    ("diagrama.png", b"\x89PNG\r\n", "image/png"),
    ("sin_extension", b"hola", "application/octet-stream"),
])
def test_tipo_no_soportado(nombre, contenido, tipo_contenido):
    with pytest.raises(TipoNoSoportado):
        leer(nombre, contenido, MAX, tipo_contenido)


def test_tipo_por_firma_y_por_extension():
    assert tipo_de("sin_extension", pdf_srs()) == "pdf"
    assert tipo_de("SRS.PDF", b"lo que sea") == "pdf"
    assert tipo_de("notas.TXT", b"hola") == "txt"
    assert tipo_de("pegado", b"hola", "text/plain; charset=utf-8") == "txt"
    assert tipo_de("notas.txt", b"Un PDF empieza con %PDF-1.4 en su cabecera.") == "txt"


def test_txt_latin1_se_lee_con_respaldo():
    texto = "El módulo de nómina debe calcular el aguinaldo del año."
    extraido = leer("latin1.txt", texto.encode("latin-1"), MAX)
    assert extraido.tipo == "txt" and extraido.paginas == [texto] and not extraido.con_paginas
    assert "no estaba en UTF-8" in extraido.advertencias[0]


def test_txt_windows_1252_conserva_comillas_curvas():
    texto = "El sistema debe mostrar “Saldo insuficiente” – sin código."
    assert decodificar(texto.encode("cp1252")) == (texto, "cp1252")


@pytest.mark.parametrize("contenido", [
    "El sistema debe validar la señal.".encode(),
    codecs.BOM_UTF8 + "El sistema debe validar la señal.".encode(),
    "El sistema debe validar la señal.".encode("utf-16"),
])
def test_txt_unicode_sin_advertencia(contenido):
    extraido = leer("a.txt", contenido, MAX)
    assert extraido.paginas == ["El sistema debe validar la señal."] and extraido.advertencias == []


def test_txt_con_saltos_de_pagina():
    extraido = leer("paginas.txt", b"Uno debe.\fDos debe.", MAX)
    assert extraido.paginas == ["Uno debe.", "Dos debe."] and extraido.con_paginas


@pytest.mark.parametrize("contenido, error", [(b"", SinTexto), (b" \n\t ", SinTexto), (b"ab\x00\x00cd", TipoNoSoportado)])
def test_txt_vacio_o_binario(contenido, error):
    with pytest.raises(error):
        leer("x.txt", contenido, MAX)


def test_nombre_de_archivo_sin_ruta():
    assert nombre_de_archivo("C:\\fakepath\\srs final.pdf") == "srs final.pdf"
    assert nombre_de_archivo("../../etc/passwd") == "passwd"
    assert nombre_de_archivo(None) == "documento"


def test_txt_que_no_es_cp1252_cae_en_latin1():
    contenido = "Año ".encode("latin-1") + b"\x81" + " el sistema debe validar.".encode("latin-1")
    extraido = leer("raro.txt", contenido, MAX)
    assert extraido.paginas == ["Año \x81 el sistema debe validar."]
    assert extraido.advertencias == ["El archivo no estaba en UTF-8; se leyó como latin-1: revisa acentos y eñes."]


def test_archivo_vacio_de_tipo_no_soportado_es_415():
    with pytest.raises(TipoNoSoportado):
        leer("vacio.docx", b"", MAX)
    with pytest.raises(SinTexto):
        leer("vacio.pdf", b"", MAX)


def test_pdf_con_guion_suave_de_winansi():
    """pypdf devuelve el byte 0xAD de WinAnsi como U+00AD; la palabra se une en la separación."""
    from app.documentos import separar_paginas
    extraido = leer("corte.pdf", pdf([["El sistema deberá autenti­", "car al usuario."]]), MAX)
    assert extraido.paginas[0].splitlines() == ["El sistema deberá autenti­", "car al usuario."]
    s = separar_paginas(extraido.paginas, extraido.con_paginas, maquetado=True)
    assert [r.texto for r in s.requisitos_propuestos] == ["El sistema deberá autenticar al usuario."]
    assert s.requisitos_propuestos[0].texto_original == "El sistema deberá autenti-\ncar al usuario."
