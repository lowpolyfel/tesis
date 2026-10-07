"""Del archivo subido al texto por página (ADR 0009).

Solo PDF con texto extraíble y texto plano: sin OCR por alcance de la tesis
(CONTEXTO §9). Los errores de OCR se confundirían con ambigüedad real.
"""
from __future__ import annotations

import codecs
import io
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Literal

from pypdf import PdfReader
from pypdf.errors import DependencyError
from pypdf.generic import ArrayObject, DictionaryObject

log = logging.getLogger(__name__)

TipoDocumento = Literal["pdf", "txt"]

# Límites técnicos de la extracción, no calibrables: pypdf lee los operadores en
# Python (unos 3 s por MB) y la extracción corre en el hilo de la petición. Una
# página de texto ocupa unos 6 KB de operadores; más de 2 MB es un dibujo.
MAX_BYTES_OPERADORES_PAGINA = 2 * 1024 * 1024
TIEMPO_MAX_EXTRACCION = 30.0  # segundos para todo el PDF; se revisa entre operadores
_reloj = time.monotonic

_SUSTITUTO = re.compile("[\ud800-\udfff]")


class ErrorDocumento(Exception):
    """El archivo no se puede convertir en texto por página."""


class TipoNoSoportado(ErrorDocumento):
    pass


class DemasiadoGrande(ErrorDocumento):
    pass


class SinTexto(ErrorDocumento):
    pass


class Ilegible(ErrorDocumento):
    pass


@dataclass
class TextoExtraido:
    tipo: TipoDocumento
    paginas: list[str]  # texto tal como se extrajo, una entrada por página
    con_paginas: bool  # las páginas son reales (PDF, o .txt con saltos de página \f)
    advertencias: list[str] = field(default_factory=list)


def sin_sustitutos(texto: str) -> tuple[str, int]:
    """pypdf decodifica los mapas ToUnicode con `surrogatepass`: un glifo puede dar media
    pareja sustituta UTF-16 (un emoji partido, una CMap mal hecha), que no se puede
    guardar en UTF-8 ni en BSON. Une las parejas completas y cambia las mitades
    sueltas por U+FFFD. Devuelve (texto, caracteres cambiados)."""
    if not _SUSTITUTO.search(texto):
        return texto, 0
    limpio = texto.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    return limpio, limpio.count("\ufffd") - texto.count("\ufffd")


def nombre_de_archivo(nombre: str | None) -> str:
    """Solo el nombre, sin ruta («C:\\fakepath\\srs.pdf» -> «srs.pdf»)."""
    limpio = PurePosixPath((nombre or "").replace("\\", "/")).name.strip()
    return limpio[:200] or "documento"


def tipo_de(nombre: str, contenido: bytes, tipo_contenido: str | None = None) -> TipoDocumento:
    """Por la firma del contenido primero (un PDF empieza con %PDF-) y luego por la extensión."""
    extension = PurePosixPath(nombre.lower()).suffix
    if contenido.lstrip()[:5] == b"%PDF-" or extension == ".pdf":
        return "pdf"
    if extension == ".txt" or (not extension and (tipo_contenido or "").startswith("text/plain")):
        return "txt"
    raise TipoNoSoportado(f"Tipo de archivo no soportado ({extension or tipo_contenido or 'sin extensión'}): "
                          "solo PDF con texto extraíble o texto plano .txt (CONTEXTO §9).")


def decodificar(contenido: bytes) -> tuple[str, str]:
    """UTF-8 (con o sin BOM) o UTF-16 con BOM; si no, Windows-1252 y al final latin-1,
    que nunca falla. Devuelve (texto, codificación usada)."""
    if contenido.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return contenido.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            pass
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return contenido.decode(codificacion), codificacion
        except UnicodeDecodeError:
            continue
    return contenido.decode("latin-1"), "latin-1"


def extraer_txt(contenido: bytes) -> TextoExtraido:
    texto, codificacion = decodificar(contenido)
    if "\x00" in texto:
        raise TipoNoSoportado("El archivo no parece texto plano (tiene bytes nulos).")
    if not any(c.isalnum() for c in texto):
        raise SinTexto("El archivo de texto está vacío.")
    paginas = texto.split("\f")
    advertencias = []
    if codificacion not in ("utf-8-sig", "utf-16"):
        advertencias.append(f"El archivo no estaba en UTF-8; se leyó como {codificacion}: revisa acentos y eñes.")
    return TextoExtraido("txt", paginas, con_paginas=len(paginas) > 1, advertencias=advertencias)


class _TiempoAgotado(Exception):
    """La extracción pasó de TIEMPO_MAX_EXTRACCION (se lanza desde el visitante de pypdf)."""


def _falta_dependencia(e: DependencyError) -> Ilegible:
    if "AES" in str(e):  # pypdf: «cryptography>=3.1 is required for AES algorithm»
        return Ilegible("El PDF está cifrado con AES (así lo guardan Word y Acrobat al restringir edición, copia "
                        "o impresión) y al servidor le falta el paquete cryptography, que pypdf necesita para "
                        "descifrarlo: instala backend/requirements.txt.")
    return Ilegible(f"Al servidor le falta una dependencia para leer este PDF ({e}).")


_DIBUJA = re.compile(rb"/([^\s/\[\]<>(){}%]+)\s*Do\b")  # «/Fm1 Do»: la página dibuja ese XObject


def _nombre_pdf(crudo: bytes) -> str:
    """Nombre de un operando tal como lo guarda pypdf (los «#xx» ya decodificados)."""
    return "/" + re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), crudo).decode("latin-1")


def _bytes_de_operadores(pagina: DictionaryObject) -> int:
    """Lo que pypdf leería para extraer el texto de la página: su contenido
    descomprimido y el de los formularios (XObject /Form) que DIBUJA con «Do», cada
    uno una vez y también los anidados. Solo cuentan los que se dibujan: LibreOffice o
    matplotlib declaran todos los formularios del documento en un único diccionario de
    recursos que heredan todas las páginas, y contarlos todos dejaba sin extraer
    páginas que solo tienen texto. Se mide antes de extraer porque la lectura de un
    flujo no se puede interrumpir."""
    vistos: set[int] = set()

    def datos(obj) -> bytes:
        obj = obj.get_object()
        if isinstance(obj, ArrayObject):
            return b"\n".join(datos(x) for x in obj)  # los flujos se parten entre tokens
        return obj.get_data() if hasattr(obj, "get_data") else b""

    def medir(contenido: bytes, recursos) -> int:
        total = len(contenido)
        recursos = recursos.get_object() if recursos is not None else None
        xobjetos = recursos.get("/XObject") if isinstance(recursos, DictionaryObject) else None
        xobjetos = xobjetos.get_object() if xobjetos is not None else None
        if not isinstance(xobjetos, DictionaryObject):
            return total
        for nombre in dict.fromkeys(_nombre_pdf(m) for m in _DIBUJA.findall(contenido)):
            x = xobjetos.get(nombre)
            x = x.get_object() if x is not None else None
            if id(x) in vistos or not isinstance(x, DictionaryObject) or x.get("/Subtype") != "/Form":
                continue
            vistos.add(id(x))
            # un formulario sin /Resources propios usa los de quien lo dibuja
            total += medir(datos(x), x.get("/Resources") or recursos)
        return total

    contenido = pagina.get("/Contents")
    return medir(datos(contenido) if contenido is not None else b"", pagina.get_inherited("/Resources"))


def _lista(paginas: list[int]) -> str:
    return ", ".join(map(str, paginas))


def extraer_pdf(contenido: bytes) -> TextoExtraido:
    try:
        lector = PdfReader(io.BytesIO(contenido))
        if lector.is_encrypted and not lector.decrypt(""):
            raise Ilegible("El PDF está protegido con contraseña.")
        paginas_pdf = list(lector.pages)
    except ErrorDocumento:
        raise
    except DependencyError as e:
        raise _falta_dependencia(e) from e
    except Exception as e:  # pypdf lanza varias clases según el daño del archivo
        raise Ilegible(f"No se pudo leer el PDF ({type(e).__name__}: {e}).") from e
    if not paginas_pdf:
        raise Ilegible("El PDF no tiene páginas.")

    # El tiempo se revisa antes de cada operador (también dentro de los formularios,
    # que pypdf vuelve a leer en cada uso); al agotarse, las páginas que faltan no se extraen.
    limite = _reloj() + TIEMPO_MAX_EXTRACCION
    agotado = False

    def vigilar(*_) -> None:
        nonlocal agotado
        if agotado or _reloj() > limite:
            agotado = True
            raise _TiempoAgotado

    paginas, fallidas, pesadas, sin_tiempo, con_sustitutos = [], [], [], [], []
    for n, pagina in enumerate(paginas_pdf, 1):
        texto = ""
        try:
            if agotado or _reloj() > limite:
                agotado = True
            elif _bytes_de_operadores(pagina) > MAX_BYTES_OPERADORES_PAGINA:
                pesadas.append(n)
            else:
                texto = pagina.extract_text(visitor_operand_before=vigilar) or ""
        except _TiempoAgotado:
            pass
        except DependencyError as e:  # no es una página sin texto: falta cryptography (AES)
            raise _falta_dependencia(e) from e
        except Exception:  # una página dañada no debe tirar el documento entero
            log.warning("No se pudo extraer el texto de la página %d", n, exc_info=True)
            fallidas.append(n)
        if agotado:  # también si pypdf siguió tras la interrupción dentro de un formulario
            texto = ""
            sin_tiempo.append(n)
        texto, cambiados = sin_sustitutos(texto)
        if cambiados:
            con_sustitutos.append(n)
        paginas.append(texto)

    advertencias = []
    if fallidas:
        advertencias.append(f"No se pudo extraer el texto de las páginas: {_lista(fallidas)}.")
    if pesadas:
        advertencias.append(f"Páginas sin extraer por tener más de {MAX_BYTES_OPERADORES_PAGINA / 2**20:g} MB de "
                            f"operadores de dibujo (límite técnico; ¿diagramas vectoriales?): {_lista(pesadas)}.")
    if sin_tiempo:
        tramo = f"{sin_tiempo[0]} a {sin_tiempo[-1]}" if len(sin_tiempo) > 1 else str(sin_tiempo[0])
        advertencias.append(f"Páginas sin extraer porque la extracción pasó de {TIEMPO_MAX_EXTRACCION:g} s "
                            f"(límite técnico): {tramo}.")
    if not any(c.isalnum() for p in paginas for c in p):
        if advertencias:
            raise Ilegible("No se pudo extraer texto del PDF. " + " ".join(advertencias))
        raise SinTexto("El PDF no tiene texto extraíble (¿es un escaneo?). No se hace OCR: "
                       "queda fuera por alcance de la tesis (CONTEXTO §9).")
    if con_sustitutos:
        advertencias.append(f"Caracteres no reconocidos (el mapa ToUnicode del PDF da medio carácter) cambiados "
                            f"por «\ufffd» en las páginas: {_lista(con_sustitutos)}.")
    omitidas = set(fallidas) | set(pesadas) | set(sin_tiempo)
    vacias = [n for n, p in enumerate(paginas, 1) if not any(c.isalnum() for c in p) and n not in omitidas]
    if vacias:
        advertencias.append(f"Páginas sin texto extraíble (¿escaneadas? sin OCR): {_lista(vacias)}.")
    return TextoExtraido("pdf", paginas, con_paginas=True, advertencias=advertencias)


def leer(nombre: str, contenido: bytes, max_bytes: int, tipo_contenido: str | None = None) -> TextoExtraido:
    """Valida tamaño y tipo, y extrae el texto por página."""
    if len(contenido) > max_bytes:
        raise DemasiadoGrande(f"El archivo excede el máximo de {max_bytes / (1024 * 1024):g} MB (DOCUMENTO_MAX_MB).")
    tipo = tipo_de(nombre, contenido, tipo_contenido)  # primero el tipo: un .docx vacío es 415, no 422
    if not contenido:
        raise SinTexto("El archivo está vacío.")
    return extraer_pdf(contenido) if tipo == "pdf" else extraer_txt(contenido)
