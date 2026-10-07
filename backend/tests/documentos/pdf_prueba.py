"""PDF reales y mínimos para las pruebas, escritos byte por byte.

Fuente Helvetica con /Encoding /WinAnsiEncoding: cada carácter fuera de ASCII va
como escape octal de su byte en Windows-1252 (é = \\351, ñ = \\361), que es como
lo escribe un procesador de textos. Un renglón por operador Tj.
"""
from __future__ import annotations

import io


def _cadena(texto: str) -> str:
    salida = []
    for byte in texto.encode("cp1252"):
        c = chr(byte)
        if c in "()\\":
            salida.append("\\" + c)
        elif 32 <= byte < 127:
            salida.append(c)
        else:
            salida.append(f"\\{byte:03o}")
    return "(" + "".join(salida) + ")"


def _flujo_de_texto(renglones: list[str]) -> bytes:
    ops = ["BT", "/F1 11 Tf", "14 TL", "72 760 Td"]
    ops += [f"{_cadena(r)} Tj T*" for r in renglones]
    ops.append("ET")
    return "\n".join(ops).encode("latin-1")


def _flujo(datos: bytes, diccionario: bytes = b"") -> bytes:
    return b"<< /Length %d %s>>\nstream\n" % (len(datos), diccionario) + datos + b"\nendstream"


def _armar(flujos: list[bytes], xobjetos: dict[str, bytes] | None = None) -> bytes:
    """Una página por flujo de contenido. `xobjetos`: formularios (nombre -> sus operadores)
    disponibles en todas las páginas."""
    objetos: list[bytes] = [b"", b""]  # 1 catálogo, 2 árbol de páginas (se llenan al final)
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    nombres = []
    for nombre, operadores in (xobjetos or {}).items():
        objetos.append(_flujo(operadores, b"/Type /XObject /Subtype /Form /BBox [0 0 612 792] "
                                          b"/Resources << /Font << /F1 3 0 R >> >> "))
        nombres.append(b"/%s %d 0 R" % (nombre.encode(), len(objetos)))
    recursos = b"<< /Font << /F1 3 0 R >> %s>>" % (b"/XObject << %s >> " % b" ".join(nombres) if nombres else b"")
    hojas = []
    for flujo in flujos:
        objetos.append(_flujo(flujo))
        contenido = len(objetos)
        objetos.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       b"/Resources %s /Contents %d 0 R >>" % (recursos, contenido))
        hojas.append(len(objetos))
    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % h for h in hojas), len(hojas))
    return _escribir(objetos)


def _escribir(objetos: list[bytes]) -> bytes:
    salida = io.BytesIO()
    salida.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    posiciones = []
    for n, cuerpo in enumerate(objetos, 1):
        posiciones.append(salida.tell())
        salida.write(b"%d 0 obj\n" % n + cuerpo + b"\nendobj\n")
    xref = salida.tell()
    salida.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1))
    salida.writelines(b"%010d 00000 n \n" % p for p in posiciones)
    salida.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, xref))
    return salida.getvalue()


def pdf(paginas: list[list[str]]) -> bytes:
    """Un PDF con una página por lista de renglones."""
    return _armar([_flujo_de_texto(renglones) for renglones in paginas])


def pdf_sin_texto(paginas: int = 1) -> bytes:
    """Páginas con un rectángulo dibujado y ningún texto: lo que deja un escaneo sin OCR."""
    return _armar([b"0.5 g 72 72 468 648 re f" for _ in range(paginas)])


def pdf_mixto(paginas: list[list[str] | None]) -> bytes:
    """None = página sin texto entre páginas con texto."""
    return _armar([_flujo_de_texto(p) if p is not None else b"0.5 g 72 72 468 648 re f" for p in paginas])


def pdf_con_operadores(paginas: list[bytes], xobjetos: dict[str, bytes] | None = None) -> bytes:
    """Páginas con sus operadores tal cual (para medir el costo de la extracción)."""
    return _armar(paginas, xobjetos=xobjetos)


def operadores_de_texto(renglones: list[str]) -> bytes:
    return _flujo_de_texto(renglones)


def pdf_con_tounicode(renglon: str, mapa: dict[str, int]) -> bytes:
    """Un renglón ASCII con una fuente cuyo mapa ToUnicode asigna a ciertos bytes un
    valor UTF-16 cualquiera (p. ej. media pareja sustituta, como un emoji partido)."""
    pares = " ".join(f"<{ord(c):02X}> <{v:04X}>" for c, v in mapa.items())
    cmap = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Prueba def "
            "1 begincodespacerange <00> <FF> endcodespacerange "
            f"{len(mapa)} beginbfchar {pares} endbfchar endcmap CMapName currentdict /CMap defineresource pop "
            "end end").encode()
    # la fuente es el objeto 3 y su ToUnicode, el 4 (antes que las páginas)
    objetos = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 4 0 R >>", _flujo(cmap),
               _flujo(_flujo_de_texto([renglon])),
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
               b"/Contents 5 0 R >>"]
    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = b"<< /Type /Pages /Kids [6 0 R] /Count 1 >>"
    return _escribir(objetos)
