"""Paquete para Overleaf de una prueba de modelos (ADR 0027).

Mismo formato que el de las corridas de calibración (ADR 0026), con el mismo preámbulo:

    main.tex                 ejemplo que usa todo (se puede borrar)
    estilo-dudamel.tex       preámbulo común
    figuras/modelos.tex      detección y aprobación por modelo, con su intervalo de Wilson
    tablas/modelos.tex       resumen por modelo
    tablas/clases.tex        detección y aprobación por clase de término
    tablas/pares.tex         prueba exacta de McNemar entre cada par de modelos (si hay revisiones)
    tablas/banco.tex         los términos de la prueba con sus lecturas esperadas (longtable)
    tablas/respuestas.tex    qué respondió cada modelo y la revisión de la persona (longtable)
    datos/modelos.csv        los números de la figura
    datos/respuestas.csv     una fila por término y modelo
    prueba.json              la prueba completa con sus revisiones
    LEEME.md
"""
from __future__ import annotations

import io
import json
import zipfile

from .latex import ESTILO, _celda, _csv, _num, tex
from .pruebas_modelos import banco, etiqueta_modelo

NOMBRE_CLASE = {"polisemia": "Polisemia", "regionalismo": "Regionalismo"}
# lo que pdfLaTeX con T1 y utf8 compila sin paquetes extra; las respuestas de los modelos pueden traer otros
_PUNTUACION = set("–—‘’“”…•«»¿¡°·")


def _seguro(texto) -> str:
    """Texto de un modelo, escapado y sin caracteres que pdfLaTeX no conoce (emojis, flechas…)."""
    limpio = "".join(c if ord(c) < 0x180 or c in _PUNTUACION else "?" for c in str(texto or ""))
    return tex(limpio)


def _ic(m: dict) -> str:
    return "---" if m["valor"] is None else f"{m['valor']:.2f} [{m['bajo']:.2f}, {m['alto']:.2f}]"


def _datos_modelos(r: dict) -> str:
    """Una fila por modelo: la fila de la figura (de arriba abajo) y cada proporción con la
    distancia a sus extremos (lo que piden las barras de error de pgfplots)."""
    filas = []
    n = len(r["modelos"])
    for k, m in enumerate(r["modelos"]):
        fila = [n - k]
        for clave in ("deteccion", "aprobacion"):
            x = m[clave]
            fila += [_num(x["valor"]), _num(None if x["valor"] is None else x["valor"] - x["bajo"]),
                     _num(None if x["valor"] is None else x["alto"] - x["valor"])]
        filas.append(fila)
    return _csv(filas, ["fila", "deteccion", "det_menos", "det_mas", "aprobacion", "apr_menos", "apr_mas"])


def _figura(r: dict) -> str:
    n = len(r["modelos"])
    nombres = ",".join("{" + tex(m["etiqueta"]) + "}" for m in reversed(r["modelos"]))
    alto = f"{max(4.0, 1.6 + 1.1 * n):.1f}cm"
    hay_aprobacion = any(m["aprobacion"]["valor"] is not None for m in r["modelos"])
    series = [
        ("  \\addplot[dudamel/deteccion] table[x=deteccion, y expr=\\thisrow{fila}+0.14, x error minus=det_menos,"
         " x error plus=det_mas, col sep=comma] {\\dudameldir/datos/modelos.csv};"),
        "  \\addlegendentry{Detección}",
    ]
    if hay_aprobacion:
        series += [
            ("  \\addplot[dudamel/aprobacion] table[x=aprobacion, y expr=\\thisrow{fila}-0.14, x error minus=apr_menos,"
             " x error plus=apr_mas, col sep=comma] {\\dudameldir/datos/modelos.csv};"),
            "  \\addlegendentry{Aprobación (revisión humana)}",
        ]
    return "\n".join([
        "% Por modelo: proporción de términos que marcó como ambiguos (detección) y proporción que la",
        "% persona revisora aprobó (aprobación), con su intervalo de Wilson al 95 %.",
        "\\begin{tikzpicture}",
        # más angosta que el texto: los nombres de los modelos van a la izquierda del eje
        f"\\begin{{axis}}[dudamel/eje, width=0.68\\linewidth, height={alto}, xmin=0, xmax=1, ymin=0.4, ymax={n + 0.6},",
        f"  ytick={{1,...,{n}}}, yticklabels={{{nombres}}}, ymajorgrids=false, xlabel={{Proporción}},",
        "  unbounded coords=discard, legend columns=2, legend style={at={(0.5,1.03)}, anchor=south}]",
        *series,
        "\\end{axis}",
        "\\end{tikzpicture}",
        "",
    ])


def _tabla_modelos(r: dict) -> str:
    filas = []
    for m in r["modelos"]:
        lat = m["latencia_ms"]["mediana"]
        filas.append(" & ".join([
            tex(m["etiqueta"]), _ic(m["deteccion"]), _ic(m["aprobacion"]), f"{m['revisados']}/{m['n']}",
            str(m["errores"]), str(m["reintentos"]), _celda(m["intenciones_media"], 1),
            "---" if lat is None else f"{lat / 1000:.1f}"]) + " \\\\")
    return "\n".join([
        "% Detección: términos marcados como ambiguos sobre los de la prueba (un error cuenta como no detectado).",
        "% Aprobación: ✓ de la persona revisora sobre los revisados. Entre corchetes, intervalo de Wilson al 95 %.",
        "\\begin{tabular}{@{}lllrrrrr@{}}",
        "\\toprule",
        "Modelo & Detección & Aprobación & Revisados & Errores & Reintentos & Intenciones & Latencia (s) \\\\",
        "\\midrule",
        *filas,
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ])


def _tabla_clases(r: dict) -> str:
    filas = []
    for m in r["modelos"]:
        for clase, c in m["por_clase"].items():
            filas.append(f"{tex(m['etiqueta'])} & {NOMBRE_CLASE.get(clase, tex(clase))} & {c['n']} & "
                         f"{_ic(c['deteccion'])} & {_ic(c['aprobacion'])} \\\\")
    return "\n".join([
        "% Detección y aprobación por clase de término del banco.",
        "\\begin{tabular}{@{}llrll@{}}",
        "\\toprule",
        "Modelo & Clase & Términos & Detección & Aprobación \\\\",
        "\\midrule",
        *filas,
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ])


def _tabla_pares(r: dict) -> str:
    nombre = {m["id"]: m["etiqueta"] for m in r["modelos"]}
    filas = [f"{tex(nombre[p['a']])} & {tex(nombre[p['b']])} & {p['comunes']} & {p['solo_a']} & {p['solo_b']} & "
             f"{_celda(p['p'])} \\\\" for p in r["pares"]]
    return "\n".join([
        "% Prueba exacta de McNemar sobre los términos revisados en ambos modelos: «solo A» es ✓ en A y ✗ en B.",
        "% p < 0.05 sugiere que la diferencia de aprobación no es azar.",
        "\\begin{tabular}{@{}llrrrr@{}}",
        "\\toprule",
        "Modelo A & Modelo B & Comunes & Solo A & Solo B & $p$ \\\\",
        "\\midrule",
        *filas,
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ])


def _tabla_banco(prueba: dict) -> str:
    terminos = {t["id"]: t for t in banco()["terminos"]}
    filas = []
    for i in prueba["items"]:
        t = terminos[i]
        filas.append(f"{i} & {tex(t['termino'])} & {NOMBRE_CLASE.get(t['clase'], tex(t['clase']))} & "
                     f"{tex(t['dominio'])} & {tex('; '.join(t['lecturas']))} \\\\")
    return "\n".join([
        "% Los términos del banco que usó la prueba, con las lecturas esperadas (la referencia de la revisión).",
        "\\begin{longtable}{@{}lllp{0.22\\linewidth}p{0.4\\linewidth}@{}}",
        "\\toprule",
        "ID & Término & Clase & Dominio & Lecturas esperadas \\\\",
        "\\midrule",
        "\\endhead",
        *filas,
        "\\bottomrule",
        "\\end{longtable}",
        "",
    ])


def _respuesta(r: dict | None) -> tuple[str, str]:
    """(¿ambiguo?, significados) de un resultado, en texto."""
    if r is None:
        return "---", "sin correr"
    if not r["ok"]:
        return "error", (r.get("error") or "")[:120]
    return ("sí" if r["ambiguo"] else "no"), " / ".join(i["significado"] for i in r["intenciones"])


def _tabla_respuestas(prueba: dict, marcas: dict) -> str:
    terminos = {t["id"]: t for t in banco()["terminos"]}
    rev = {True: "bien", False: "mal", None: "---"}
    filas = []
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        for i in prueba["items"]:
            amb, texto = _respuesta(res.get(i))
            bueno = marcas.get(m["id"], {}).get(i, {}).get("bueno")
            filas.append(f"{i} & {tex(terminos[i]['termino'])} & {tex(etiqueta_modelo(m))} & {amb} & {_seguro(texto)} & {rev[bueno]} \\\\")
    return "\n".join([
        "% Qué respondió cada modelo (los significados de sus intenciones) y la revisión de la persona.",
        "\\begin{longtable}{@{}llp{0.17\\linewidth}lp{0.38\\linewidth}l@{}}",
        "\\toprule",
        "ID & Término & Modelo & ¿Ambiguo? & Significados & Revisión \\\\",
        "\\midrule",
        "\\endhead",
        *filas,
        "\\bottomrule",
        "\\end{longtable}",
        "",
    ])


def _datos_respuestas(prueba: dict, marcas: dict) -> str:
    terminos = {t["id"]: t for t in banco()["terminos"]}
    filas = []
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        for i in prueba["items"]:
            r = res.get(i)
            marca = marcas.get(m["id"], {}).get(i, {})
            filas.append([i, terminos[i]["termino"], terminos[i]["clase"], m["proveedor"], m["modelo"],
                          "" if r is None else int(r["ok"]), "" if not r or not r["ok"] else int(r["ambiguo"]),
                          "" if not r or not r["ok"] else len(r["intenciones"]), "" if not r else r.get("ms") or "",
                          "" if not r else r.get("intentos", ""),
                          {True: 1, False: 0, None: ""}[marca.get("bueno")], marca.get("nota") or ""])
    return _csv(filas, ["id", "termino", "clase", "proveedor", "modelo", "respondio", "ambiguo", "intenciones", "ms",
                        "intentos", "bueno", "nota"])


def _main(prueba: dict, r: dict, revisiones: dict | None) -> str:
    b = prueba["banco"]
    revisor = (revisiones or {}).get("revisor")
    tablas = [("modelos", "Resultados por modelo."), ("clases", "Por clase de término.")]
    if any(p["comunes"] for p in r["pares"]):
        tablas.append(("pares", "Comparación por pares (McNemar exacta)."))
    partes = [
        "\\documentclass[11pt]{article}",
        "\\usepackage[utf8]{inputenc}",
        "\\usepackage[T1]{fontenc}",
        "\\usepackage[spanish,es-noshorthands,es-tabla]{babel}",
        "\\usepackage[margin=2.5cm]{geometry}",
        "\\input{estilo-dudamel}",
        "\\begin{document}",
        f"\\section*{{Prueba de modelos --- {tex(prueba['prueba_id'])}}}",
        (f"Fecha: {tex(prueba['creado'])}. Versión de Dudamel: {tex(prueba.get('version_app'))}. "
         f"Banco: {tex(b['nombre'])} {tex(b['version'])} (huella {tex(b['huella'][:12])}), {len(prueba['items'])} términos. "
         f"Prompt: {tex(prueba['configuracion']['prompt'])}; temperatura {prueba['configuracion']['temperatura']}. "
         f"Revisión: {tex(revisor or '---')}."),
        "",
        "\\begin{figure}[htbp]", "\\centering", "\\input{\\dudameldir/figuras/modelos}",
        "\\caption{Detección y aprobación por modelo (intervalos de Wilson al 95~\\%).}",
        "\\label{fig:dudamel-modelos}", "\\end{figure}", "",
    ]
    for nombre, pie in tablas:
        partes += ["\\begin{table}[htbp]", "\\centering", "\\small", f"\\caption{{{pie}}}",
                   f"\\label{{tab:dudamel-{nombre}}}", f"\\input{{\\dudameldir/tablas/{nombre}}}", "\\end{table}", ""]
    partes += ["\\subsection*{Banco de términos}", "{\\small\\input{\\dudameldir/tablas/banco}}",
               "\\subsection*{Respuestas}", "{\\small\\input{\\dudameldir/tablas/respuestas}}", "\\end{document}", ""]
    return "\n".join(partes)


LEEME = """# Paquete de la prueba de modelos {id} para Overleaf

1. En Overleaf: **New Project → Upload Project** y sube este .zip. `main.tex` compila tal
   cual con pdfLaTeX.
2. Para usarlo dentro de tu tesis, sube la carpeta (por ejemplo como `dudamel-{id}/`) y en el
   preámbulo pon:

       \\newcommand{{\\dudameldir}}{{dudamel-{id}}}
       \\input{{dudamel-{id}/estilo-dudamel}}

   y donde quieras cada pieza: `\\input{{dudamel-{id}/figuras/modelos}}`,
   `\\input{{dudamel-{id}/tablas/modelos}}`, etc. `tablas/banco.tex` y `tablas/respuestas.tex`
   usan `longtable` y van fuera de un `table`.
3. `prueba.json` es la prueba completa: modelos, configuración, banco (con su huella), cada
   respuesta y las revisiones. Cítala por su id ({id}) y fecha.

Detección = términos que el modelo marcó como ambiguos / términos de la prueba. Aprobación =
✓ de la persona revisora / términos revisados. Los intervalos son de Wilson al 95 %.
"""


def paquete_overleaf(prueba: dict, r: dict, revisiones: dict | None) -> bytes:
    """El .zip de una prueba: `r` es su `resumen` y `revisiones` el documento de revisiones."""
    marcas = (revisiones or {}).get("marcas", {})
    archivos = {
        "LEEME.md": LEEME.format(id=prueba["prueba_id"]),
        "estilo-dudamel.tex": ESTILO,
        "prueba.json": json.dumps({**prueba, "revisiones": revisiones, "resumen": r}, ensure_ascii=False, indent=1),
        "datos/modelos.csv": _datos_modelos(r),
        "datos/respuestas.csv": _datos_respuestas(prueba, marcas),
        "figuras/modelos.tex": _figura(r),
        "tablas/modelos.tex": _tabla_modelos(r),
        "tablas/clases.tex": _tabla_clases(r),
        "tablas/banco.tex": _tabla_banco(prueba),
        "tablas/respuestas.tex": _tabla_respuestas(prueba, marcas),
    }
    if any(p["comunes"] for p in r["pares"]):
        archivos["tablas/pares.tex"] = _tabla_pares(r)
    archivos["main.tex"] = _main(prueba, r, revisiones)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return salida.getvalue()
