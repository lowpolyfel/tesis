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


def _armar(flujos: list[bytes]) -> bytes:
    objetos: list[bytes] = [b"", b""]  # 1 catálogo, 2 árbol de páginas (se llenan al final)
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    hojas = []
    for flujo in flujos:
        objetos.append(b"<< /Length %d >>\nstream\n" % len(flujo) + flujo + b"\nendstream")
        contenido = len(objetos)
        objetos.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % contenido)
        hojas.append(len(objetos))
    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % h for h in hojas), len(hojas))

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
