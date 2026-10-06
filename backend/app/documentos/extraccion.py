"""Del archivo subido al texto por página (ADR 0009).

Solo PDF con texto extraíble y texto plano: sin OCR por alcance de la tesis
(CONTEXTO §9). Los errores de OCR se confundirían con ambigüedad real.
"""
from __future__ import annotations

import codecs
import io
import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Literal

from pypdf import PdfReader

log = logging.getLogger(__name__)

TipoDocumento = Literal["pdf", "txt"]


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


def extraer_pdf(contenido: bytes) -> TextoExtraido:
    try:
        lector = PdfReader(io.BytesIO(contenido))
        if lector.is_encrypted and not lector.decrypt(""):
            raise Ilegible("El PDF está protegido con contraseña.")
        paginas_pdf = list(lector.pages)
    except ErrorDocumento:
        raise
    except Exception as e:  # pypdf lanza varias clases según el daño del archivo
        raise Ilegible(f"No se pudo leer el PDF ({type(e).__name__}: {e}).") from e
    if not paginas_pdf:
        raise Ilegible("El PDF no tiene páginas.")

    paginas, fallidas = [], []
    for n, pagina in enumerate(paginas_pdf, 1):
        try:
            paginas.append(pagina.extract_text() or "")
        except Exception:  # una página dañada no debe tirar el documento entero
            log.warning("No se pudo extraer el texto de la página %d", n, exc_info=True)
            paginas.append("")
            fallidas.append(n)
    if not any(c.isalnum() for p in paginas for c in p):
        raise SinTexto("El PDF no tiene texto extraíble (¿es un escaneo?). No se hace OCR: "
                       "queda fuera por alcance de la tesis (CONTEXTO §9).")

    advertencias = []
    if fallidas:
        advertencias.append(f"No se pudo extraer el texto de las páginas: {', '.join(map(str, fallidas))}.")
    vacias = [n for n, p in enumerate(paginas, 1) if not any(c.isalnum() for c in p) and n not in fallidas]
    if vacias:
        advertencias.append(f"Páginas sin texto extraíble (¿escaneadas? sin OCR): {', '.join(map(str, vacias))}.")
    return TextoExtraido("pdf", paginas, con_paginas=True, advertencias=advertencias)


def leer(nombre: str, contenido: bytes, max_bytes: int, tipo_contenido: str | None = None) -> TextoExtraido:
    """Valida tamaño y tipo, y extrae el texto por página."""
    if len(contenido) > max_bytes:
        raise DemasiadoGrande(f"El archivo excede el máximo de {max_bytes / (1024 * 1024):g} MB (DOCUMENTO_MAX_MB).")
    if not contenido:
        raise SinTexto("El archivo está vacío.")
    if tipo_de(nombre, contenido, tipo_contenido) == "pdf":
        return extraer_pdf(contenido)
    return extraer_txt(contenido)
