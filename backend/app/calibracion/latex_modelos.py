"""Paquete para Overleaf de una prueba de modelos (ADR 0027).

Mismo formato que el de las corridas de calibración (ADR 0026), con el mismo preámbulo:

    main.tex                 ejemplo que usa todo (se puede borrar)
    estilo-dudamel.tex       preámbulo común
    figuras/modelos.tex      exhaustividad, falsas alarmas y aprobación por modelo, con su intervalo de Wilson
    tablas/modelos.tex       resumen por modelo
    tablas/confusion.tex     VP, FN, FP, VN por modelo y las parejas del mismo dominio (con controles)
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
from .pruebas_modelos import banco_de, es_ambiguo, etiqueta_modelo

NOMBRE_CLASE = {"polisemia": "Polisemia", "regionalismo": "Regionalismo", "inequivoco": "Inequívoco"}
# lo que pdfLaTeX con T1 y utf8 compila sin paquetes extra; las respuestas de los modelos pueden traer otros
_PUNTUACION = set("–—‘’“”…•«»¿¡°·")


def _seguro(texto) -> str:
    """Texto de un modelo, escapado y sin caracteres que pdfLaTeX no conoce (emojis, flechas…)."""
    limpio = "".join(c if ord(c) < 0x180 or c in _PUNTUACION else "?" for c in str(texto or ""))
    return tex(limpio)


def _ic(m: dict) -> str:
    return "---" if m["valor"] is None else f"{m['valor']:.2f} [{m['bajo']:.2f}, {m['alto']:.2f}]"


# (clave del resumen, columna del CSV, estilo pgfplots, leyenda, desplazamiento vertical en la fila)
SERIES = (("deteccion", "det", "deteccion", "Exhaustividad (ambiguos detectados)", 0.2),
          ("falsas_alarmas", "fal", "falsasalarmas", "Falsas alarmas (inequívocos marcados)", 0.0),
          ("aprobacion", "apr", "aprobacion", "Aprobación (revisión humana)", -0.2))


def _datos_modelos(r: dict) -> str:
    """Una fila por modelo: la fila de la figura (de arriba abajo) y cada proporción con la
    distancia a sus extremos (lo que piden las barras de error de pgfplots)."""
    filas, encabezado = [], ["fila"]
    for _, col, *_ in SERIES:
        encabezado += [col, f"{col}_menos", f"{col}_mas"]
    n = len(r["modelos"])
    for k, m in enumerate(r["modelos"]):
        fila = [n - k]
        for clave, *_ in SERIES:
            x = m.get(clave) or {"valor": None}
            fila += [_num(x["valor"]), _num(None if x["valor"] is None else x["valor"] - x["bajo"]),
                     _num(None if x["valor"] is None else x["alto"] - x["valor"])]
        filas.append(fila)
    return _csv(filas, encabezado)


def _figura(r: dict) -> str:
    n = len(r["modelos"])
    nombres = ",".join("{" + tex(m["etiqueta"]) + "}" for m in reversed(r["modelos"]))
    alto = f"{max(4.4, 1.8 + 1.3 * n):.1f}cm"
    series = []
    for clave, col, estilo, leyenda, dy in SERIES:
        if not any((m.get(clave) or {}).get("valor") is not None for m in r["modelos"]):
            continue
        series += [(f"  \\addplot[dudamel/{estilo}] table[x={col}, y expr=\\thisrow{{fila}}{dy:+.2f}, x error minus={col}_menos,"
                    f" x error plus={col}_mas, col sep=comma] {{\\dudameldir/datos/modelos.csv}};"),
                   f"  \\addlegendentry{{{leyenda}}}"]
    return "\n".join([
        "% Por modelo: exhaustividad (ambiguos que marcó como ambiguos), falsas alarmas (inequívocos que",
        "% marcó como ambiguos) y aprobación de la persona revisora, con su intervalo de Wilson al 95 %.",
        "\\begin{tikzpicture}",
        # más angosta que el texto: los nombres de los modelos van a la izquierda del eje
        f"\\begin{{axis}}[dudamel/eje, width=0.68\\linewidth, height={alto}, xmin=0, xmax=1, ymin=0.4, ymax={n + 0.6},",
        f"  ytick={{1,...,{n}}}, yticklabels={{{nombres}}}, ymajorgrids=false, xlabel={{Proporción}},",
        "  unbounded coords=discard, legend columns=1, legend style={at={(0.5,1.03)}, anchor=south}]",
        *series,
        "\\end{axis}",
        "\\end{tikzpicture}",
        "",
    ])


def _tabla_modelos(r: dict) -> str:
    controles = any(m.get("falsas_alarmas") for m in r["modelos"])
    filas = []
    for m in r["modelos"]:
        lat = m["latencia_ms"]["mediana"]
        celdas = [tex(m["etiqueta"]), _ic(m["deteccion"])]
        if controles:
            celdas += [_ic(m["falsas_alarmas"]), _ic(m["precision"])]
        celdas += [_ic(m["aprobacion"]), f"{m['revisados']}/{m['n']}", str(m["errores"]), str(m["reintentos"]),
                   "---" if lat is None else f"{lat / 1000:.1f}"]
        filas.append(" & ".join(celdas) + " \\\\")
    columnas = "Modelo & Exhaustividad" + (" & Falsas alarmas & Precisión" if controles else "") + \
        " & Aprobación & Revisados & Errores & Reintentos & Latencia (s) \\\\"
    return "\n".join([
        "% Exhaustividad: ambiguos marcados como ambiguos sobre todos los ambiguos (un error cuenta como no detectado).",
        *(["% Falsas alarmas: inequívocos marcados como ambiguos sobre los inequívocos que respondieron.",
           "% Precisión: ambiguos sobre todo lo marcado como ambiguo."] if controles else
          ["% Sin controles inequívocos en el banco: no hay precisión ni falsas alarmas."]),
        "% Aprobación: ✓ de la persona revisora sobre los revisados. Entre corchetes, intervalo de Wilson al 95 %.",
        "\\begin{tabular}{@{}l" + "l" * (4 if controles else 2) + "rrrr@{}}",
        "\\toprule",
        columnas,
        "\\midrule",
        *filas,
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ])


def _tabla_confusion(r: dict) -> str:
    """Matriz de confusión por modelo (positivo = marcó ambiguo) y las parejas del mismo dominio."""
    filas = []
    for m in r["modelos"]:
        c, par = m["confusion"], m.get("parejas")
        parejas = "---" if not par else f"{par['discrimina']}/{par['n']}"
        filas.append(f"{tex(m['etiqueta'])} & {c['vp']} & {c['fn']} & {c['fp']} & {c['vn']} & "
                     f"{m['errores_inequivocos']} & {parejas} \\\\")
    return "\n".join([
        "% Positivo = el modelo marcó el término como ambiguo. VP/FN sobre los ambiguos (un error es FN); FP/VN sobre",
        "% los inequívocos que respondieron. Parejas: en cuántas parejas del mismo dominio marcó el ambiguo y no su control.",
        "\\begin{tabular}{@{}lrrrrrr@{}}",
        "\\toprule",
        "Modelo & VP & FN & FP & VN & Errores en inequívocos & Parejas \\\\",
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
        "% Por clase de término: proporción que el modelo marcó como ambiguos (en las clases ambiguas es la",
        "% exhaustividad; en la inequívoca, las falsas alarmas) y aprobación. Con pocos casos por clase los",
        "% intervalos se traslapan: una diferencia entre clases es una tendencia, no un resultado.",
        "\\begin{tabular}{@{}llrll@{}}",
        "\\toprule",
        "Modelo & Clase & Términos & Marcó ambiguo & Aprobación \\\\",
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
    terminos = {t["id"]: t for t in banco_de(prueba)["terminos"]}
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
    terminos = {t["id"]: t for t in banco_de(prueba)["terminos"]}
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
    terminos = {t["id"]: t for t in banco_de(prueba)["terminos"]}
    filas = []
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        for i in prueba["items"]:
            r = res.get(i)
            marca = marcas.get(m["id"], {}).get(i, {})
            filas.append([i, terminos[i]["termino"], terminos[i]["clase"], int(es_ambiguo(terminos[i])), m["proveedor"], m["modelo"],
                          "" if r is None else int(r["ok"]), "" if not r or not r["ok"] else int(r["ambiguo"]),
                          "" if not r or not r["ok"] else len(r["intenciones"]), "" if not r else r.get("ms") or "",
                          "" if not r else r.get("intentos", ""),
                          {True: 1, False: 0, None: ""}[marca.get("bueno")], marca.get("nota") or ""])
    return _csv(filas, ["id", "termino", "clase", "ambiguo_esperado", "proveedor", "modelo", "respondio", "ambiguo", "intenciones", "ms",
                        "intentos", "bueno", "nota"])


def _main(prueba: dict, r: dict, revisiones: dict | None) -> str:
    b = prueba["banco"]
    revisor = (revisiones or {}).get("revisor")
    tablas = [("modelos", "Resultados por modelo.")]
    if any(m.get("falsas_alarmas") for m in r["modelos"]):
        tablas.append(("confusion", "Matriz de confusión por modelo (positivo = marcó ambiguo)."))
    tablas.append(("clases", "Por clase de término."))
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
        "\\caption{Exhaustividad, falsas alarmas y aprobación por modelo (intervalos de Wilson al 95~\\%).}",
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

Exhaustividad = ambiguos que el modelo marcó como ambiguos / ambiguos de la prueba (un error
cuenta como no detectado). Con controles inequívocos (banco v2 o posterior): falsas alarmas =
inequívocos marcados como ambiguos / inequívocos que respondieron, y precisión = ambiguos / todo
lo marcado. Aprobación = ✓ de la persona revisora / términos revisados. Los intervalos son de
Wilson al 95 %.
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
    if any(m.get("falsas_alarmas") for m in r["modelos"]):  # sin controles no hay FP ni VN que mostrar
        archivos["tablas/confusion.tex"] = _tabla_confusion(r)
    if any(p["comunes"] for p in r["pares"]):
        archivos["tablas/pares.tex"] = _tabla_pares(r)
    archivos["main.tex"] = _main(prueba, r, revisiones)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return salida.getvalue()
