"""Del archivo al texto por página: PDF generados en la prueba y texto plano."""
import codecs

import pytest
from pypdf import PageObject
from pypdf.errors import DependencyError

from app.documentos import extraccion
from app.documentos.extraccion import (
    DemasiadoGrande,
    Ilegible,
    SinTexto,
    TipoNoSoportado,
    decodificar,
    leer,
    nombre_de_archivo,
    sin_sustitutos,
    tipo_de,
)
from tests.documentos.muestras import ENCABEZADO, pdf_srs
from tests.documentos.pdf_cifrados import AES128, AES256, TEXTO_CIFRADO
from tests.documentos.pdf_prueba import (
    operadores_de_texto,
    pdf,
    pdf_con_operadores,
    pdf_con_tounicode,
    pdf_mixto,
    pdf_sin_texto,
)

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


# --- PDF cifrados con AES (revisión final) -------------------------------------------------

def _hay_cryptography() -> bool:
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.parametrize("cifrado", [AES128, AES256], ids=["aes128", "aes256"])
def test_pdf_cifrado_con_aes_sin_contrasena_de_apertura(cifrado):
    """Con cryptography se lee; sin ella el error lo dice, en vez de «¿es un escaneo?»."""
    if _hay_cryptography():
        assert leer("protegido.pdf", cifrado, MAX).paginas[0].strip() == TEXTO_CIFRADO
    else:
        with pytest.raises(Ilegible, match="falta el paquete cryptography"):
            leer("protegido.pdf", cifrado, MAX)


def test_dependencia_faltante_no_es_pagina_sin_texto(monkeypatch):
    def sin_aes(self, **_):
        raise DependencyError("cryptography>=3.1 is required for AES algorithm")

    monkeypatch.setattr(PageObject, "extract_text", sin_aes)
    with pytest.raises(Ilegible, match="cifrado con AES.*falta el paquete cryptography"):
        leer("protegido.pdf", pdf([["El sistema debe guardar."]]), MAX)


# --- Sustitutos UTF-16 sueltos de un mapa ToUnicode ------------------------------------------

def test_sin_sustitutos_une_parejas_y_cambia_las_mitades_sueltas():
    assert sin_sustitutos("a😀b") == ("a😀b", 0)
    assert sin_sustitutos("a\ud83db\ude00") == ("a�b�", 2)
    assert sin_sustitutos("ya tenía �") == ("ya tenía �", 0)


def test_pdf_con_media_pareja_sustituta_se_puede_guardar():
    contenido = pdf_con_tounicode("El sistema debe registrar A usuarios con B.", {"A": 0xD83D, "B": 0xDE00})
    extraido = leer("emoji.pdf", contenido, MAX)
    assert extraido.paginas[0].strip() == "El sistema debe registrar � usuarios con �."
    extraido.paginas[0].encode("utf-8")
    assert extraido.advertencias == ["Caracteres no reconocidos (el mapa ToUnicode del PDF da medio carácter) "
                                     "cambiados por «�» en las páginas: 1."]
    entera = leer("emoji.pdf", pdf_con_tounicode("Debe mostrar AB.", {"A": 0xD83D, "B": 0xDE00}), MAX)
    assert entera.paginas[0].strip() == "Debe mostrar 😀." and entera.advertencias == []


# --- Costo de la extracción ---------------------------------------------------------------

DIBUJO = b"0 0 m\n"  # un operador por renglón: lo que más le cuesta leer a pypdf por byte


class _Reloj:
    """Avanza un segundo cada vez que se consulta: el tiempo se mide en consultas."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 1
        return self.t


@pytest.fixture
def lecturas(monkeypatch):
    """Cuenta las páginas que pypdf llega a leer."""
    llamadas = []
    original = PageObject.extract_text

    def contar(self, *args, **kwargs):
        llamadas.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PageObject, "extract_text", contar)
    return llamadas


def test_pagina_con_demasiados_operadores_no_se_lee(monkeypatch, lecturas):
    monkeypatch.setattr(extraccion, "MAX_BYTES_OPERADORES_PAGINA", 2**19)
    contenido = pdf_con_operadores([operadores_de_texto(["El sistema debe guardar."]),
                                    operadores_de_texto(["El sistema debe salir."]) + DIBUJO * 100_000])
    extraido = leer("diagrama.pdf", contenido, MAX)
    assert extraido.paginas[0].strip() == "El sistema debe guardar." and extraido.paginas[1] == ""
    assert len(lecturas) == 1  # la pesada ni se lee
    assert extraido.advertencias == ["Páginas sin extraer por tener más de 0.5 MB de operadores de dibujo "
                                     "(límite técnico; ¿diagramas vectoriales?): 2."]


def test_el_costo_cuenta_los_formularios_de_la_pagina(monkeypatch, lecturas):
    monkeypatch.setattr(extraccion, "MAX_BYTES_OPERADORES_PAGINA", 2**19)
    contenido = pdf_con_operadores([operadores_de_texto(["El sistema debe guardar."]) + b"\n/Fm1 Do"],
                                   xobjetos={"Fm1": DIBUJO * 100_000})
    with pytest.raises(Ilegible) as e:
        leer("formulario.pdf", contenido, MAX)
    assert "más de 0.5 MB de operadores" in str(e.value) and "escaneo" not in str(e.value)
    assert lecturas == []


def test_formularios_que_la_pagina_no_dibuja_no_cuentan(monkeypatch, lecturas):
    """LibreOffice y matplotlib declaran todos los formularios en un diccionario de recursos
    que heredan todas las páginas: si se contaban todos, las páginas de solo texto se
    saltaban y el documento entero respondía 422."""
    monkeypatch.setattr(extraccion, "MAX_BYTES_OPERADORES_PAGINA", 2**19)
    contenido = pdf_con_operadores([operadores_de_texto(["El sistema debe guardar."]),
                                    operadores_de_texto(["El sistema debe salir."]) + b"\n/Fm1 Do"],
                                   xobjetos={"Fm1": DIBUJO * 100_000, "Fm2": DIBUJO * 100_000})
    extraido = leer("libreoffice.pdf", contenido, MAX)
    assert extraido.paginas[0].strip() == "El sistema debe guardar." and extraido.paginas[1] == ""
    assert len(lecturas) == 1  # solo la página que dibuja el formulario pesado se salta
    assert extraido.advertencias == ["Páginas sin extraer por tener más de 0.5 MB de operadores de dibujo "
                                     "(límite técnico; ¿diagramas vectoriales?): 2."]


def test_tiempo_agotado_interrumpe_la_pagina_y_omite_las_siguientes(monkeypatch):
    monkeypatch.setattr(extraccion, "_reloj", _Reloj())
    monkeypatch.setattr(extraccion, "TIEMPO_MAX_EXTRACCION", 50)  # consultas: una por página y una por operador
    contenido = pdf_con_operadores([operadores_de_texto(["El sistema debe guardar."]),
                                    operadores_de_texto(["El sistema debe salir."]) + DIBUJO * 200,
                                    operadores_de_texto(["El sistema debe avisar."])])
    extraido = leer("lento.pdf", contenido, MAX)
    assert [p.strip() for p in extraido.paginas] == ["El sistema debe guardar.", "", ""]
    assert extraido.advertencias == ["Páginas sin extraer porque la extracción pasó de 50 s (límite técnico): 2 a 3."]
    assert extraccion._reloj.t < 60  # se detuvo en la página 2, no al terminarla


def test_tiempo_agotado_dentro_de_un_formulario_repetido(monkeypatch):
    """pypdf vuelve a leer el formulario en cada uso y se traga las excepciones de adentro:
    la extracción igual se detiene en el siguiente operador de la página."""
    monkeypatch.setattr(extraccion, "_reloj", _Reloj())
    monkeypatch.setattr(extraccion, "TIEMPO_MAX_EXTRACCION", 50)
    contenido = pdf_con_operadores([operadores_de_texto(["El sistema debe guardar."]) + b"\n/Fm1 Do" * 100],
                                   xobjetos={"Fm1": DIBUJO * 30})
    with pytest.raises(Ilegible, match="pasó de 50 s"):
        leer("repetido.pdf", contenido, MAX)
    assert extraccion._reloj.t < 100  # 100 usos × 30 operadores sin el límite


def test_pdf_normal_no_toca_los_limites():
    renglon = "El sistema deberá registrar la sesión del usuario en la bitácora con fecha, hora y número."
    extraido = leer("srs.pdf", pdf([[renglon] * 50 for _ in range(30)]), MAX)
    assert len(extraido.paginas) == 30 and extraido.advertencias == []
