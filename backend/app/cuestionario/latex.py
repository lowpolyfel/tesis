"""Paquete para Overleaf con los resultados del cuestionario de evaluación (ADR 0033).

Mismo formato que los de calibración (ADR 0026): compila con pdfLaTeX y con XeLaTeX.

    main.tex                  ejemplo que usa todo (se puede borrar)
    estilo-dudamel.tex        el preámbulo común (\\dudameldir)
    figuras/sus.tex           distribución del puntaje SUS, con la media y la referencia de 68
    figuras/comparacion.tex   P9–P20: a mano contra DUDAMEL (barras apiladas al 100 %)
    figuras/sus_items.tex     P25–P34, los diez ítems del SUS
    figuras/etapas.tex        P35–P39, las etapas intermedias
    figuras/ambiguedad.tex    P42–P47, la detección de ambigüedad
    figuras/problemas.tex     P50, los problemas de infraestructura
    figuras/entrega.tex       P21, qué versión le entregarían al cliente
    figuras/uso_real.tex      P59, si lo usarían en un proyecto real
    tablas/resumen.tex        participantes, SUS (media, mediana, DE) y fallas
    tablas/escalas.tex        cada escala: n, mediana, RIC y % arriba del punto medio
    tablas/conteos.tex        P7, P8 y P48: media, mediana y rango
    tablas/frecuencias.tex    cada pregunta de opción o casillas (longtable)
    tablas/abiertas.tex       las respuestas abiertas, para codificarlas (longtable)
    datos/*.csv               los números de cada figura; respuestas.csv, una fila por persona
    resultados.json           el resumen completo
    LEEME.md

Todo es anónimo: ni la cuenta ni el correo; cada persona es R01, R02… por orden de envío.
Sin enviados, el paquete trae solo el `main.tex` que lo dice.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile

from app.calibracion.latex import ESTILO, _csv, preambulo, tex

from . import GRUPOS_ESCALA, ORDEN, PREGUNTAS, VERSION, filas_csv, resultados

# lo que pdfLaTeX con T1 y utf8 compila sin paquetes extra; una respuesta abierta puede traer emojis
_PUNTUACION = set("–—‘’“”…•«»¿¡°·")
# Los cinco niveles, del extremo «a mano / en desacuerdo» al «DUDAMEL / de acuerdo»: naranja y azul con
# el gris en medio, y cada uno con su trama para leerse en blanco y negro
ESTILO_CUESTIONARIO = r"""%% Niveles de las escalas del cuestionario (ADR 0033)
\pgfplotsset{
  dudamel/nivel1/.style={fill=dudamelNaranja, draw=white},
  dudamel/nivel2/.style={fill=dudamelNaranja!45, draw=white, pattern=north east lines, pattern color=dudamelNaranja},
  dudamel/nivel3/.style={fill=dudamelGris!35, draw=white},
  dudamel/nivel4/.style={fill=dudamelAzul!45, draw=white, pattern=north west lines, pattern color=dudamelAzul},
  dudamel/nivel5/.style={fill=dudamelAzul, draw=white},
}
"""


def _seguro(texto) -> str:
    limpio = "".join(c if ord(c) < 0x180 or c in _PUNTUACION else "?" for c in str(texto or ""))
    return tex(limpio)


def _n(x, d: int = 1) -> str:
    if x is None:
        return "---"
    return str(int(x)) if float(x).is_integer() else f"{x:.{d}f}"


def _alto(n: int, por_fila: float = 1.05) -> str:
    return f"{max(4.0, 1.6 + por_fila * n):.1f}cm"


def _envolver(comentario: list[str], ejes: str, cuerpo: list[str]) -> str:
    return "\n".join([*[f"% {c}" for c in comentario], "\\begin{tikzpicture}", ejes, *cuerpo,
                      "\\end{axis}", "\\end{tikzpicture}", ""])


# ---------------------------------------------------------------- datos y figuras

def _datos_grupo(g: dict, r: dict) -> str:
    """Una fila por pregunta (la primera arriba): porcentaje de cada nivel sobre quienes la contestaron."""
    filas, k = [], len(g["preguntas"])
    for i, qid in enumerate(g["preguntas"]):
        x = r["preguntas"][qid]
        n = x["n"] or 0
        fr = x.get("frecuencias") or {}
        filas.append([k - i, PREGUNTAS[qid]["n"], n,
                      *[f"{(100 * fr.get(str(v), 0) / n) if n else 0:.2f}" for v in range(1, 6)]])
    return _csv(filas, ["fila", "pregunta", "n", "nivel1", "nivel2", "nivel3", "nivel4", "nivel5"])


def _figura_grupo(g: dict, archivo: str) -> str:
    k = len(g["preguntas"])
    rotulos = ",".join("{" + f"P{PREGUNTAS[q]['n']}. {_seguro(PREGUNTAS[q]['texto'])}" + "}"
                       for q in reversed(g["preguntas"]))
    ejes = (f"\\begin{{axis}}[dudamel/eje, xbar stacked, bar width=10pt, width=0.55\\linewidth, height={_alto(k)},\n"
            f"  xmin=0, xmax=100, ymin=0.4, ymax={k + 0.6}, ytick={{1,...,{k}}}, yticklabels={{{rotulos}}},\n"
            "  yticklabel style={text width=5.6cm, align=right, font=\\scriptsize}, ymajorgrids=false,\n"
            "  xlabel={\\% de quienes la contestaron}, legend columns=1,\n"
            "  legend style={at={(0.5,1.03)}, anchor=south, font=\\scriptsize}, reverse legend=false]")
    cuerpo = []
    for v, nivel in enumerate(g["niveles"], 1):
        cuerpo += [(f"  \\addplot[dudamel/nivel{v}] table[x=nivel{v}, y=fila, col sep=comma] "
                    f"{{\\dudameldir/datos/{archivo}.csv}};"),
                   f"  \\addlegendentry{{{v} {_seguro(nivel)}}}"]
    return _envolver([f"{g['titulo']}: datos/{archivo}.csv"], ejes, cuerpo)


def _datos_sus(r: dict) -> str:
    """Cuántos puntajes caen en cada decena (0–10, …, 90–100; el 100 va en la última)."""
    cuentas = [0] * 10
    for v in r["sus"]["valores"]:
        cuentas[min(int(v // 10), 9)] += 1
    return _csv([[10 * i + 5, c] for i, c in enumerate(cuentas)], ["centro", "personas"])


def _figura_sus(r: dict) -> str:
    media = r["sus"]["media"]
    cuentas = [0] * 10
    for v in r["sus"]["valores"]:
        cuentas[min(int(v // 10), 9)] += 1
    tope = max(2, max(cuentas) + 1)
    ejes = ("\\begin{axis}[dudamel/eje, height=0.5\\linewidth, xmin=0, xmax=100,\n"
            f"  ymin=0, ymax={tope}, xtick={{0,10,...,100}}, ytick distance=1, xlabel={{Puntaje SUS (0--100)}},\n"
            "  ylabel={Personas}, xmajorgrids=false, legend style={at={(0.02,0.98)}, anchor=north west}]")
    cuerpo = [("  \\addplot[ybar, bar width=8, dudamel/barra2, forget plot] table[x=centro, y=personas, col sep=comma] "
               "{\\dudameldir/datos/sus.csv};"),
              f"  \\addplot[dudamel/umbral] coordinates {{({media:.2f},0) ({media:.2f},{tope})}};",
              f"  \\addlegendentry{{Media ({media:.1f})}}",
              f"  \\addplot[dudamel/azar] coordinates {{(68,0) (68,{tope})}};",
              "  \\addlegendentry{Referencia (68)}"]
    return _envolver(["Puntaje SUS por persona, agrupado por decenas: datos/sus.csv"], ejes, cuerpo)


def _datos_opciones(qid: str, r: dict) -> str:
    p, fr = PREGUNTAS[qid], r["preguntas"][qid].get("frecuencias") or {}
    k = len(p["opciones"])
    return _csv([[k - i, fr.get(o, 0)] for i, o in enumerate(p["opciones"])], ["fila", "personas"])


def _figura_opciones(qid: str, archivo: str, r: dict) -> str:
    p = PREGUNTAS[qid]
    k = len(p["opciones"])
    rotulos = ",".join("{" + _seguro(o) + "}" for o in reversed(p["opciones"]))
    tope = max(2, *(r["preguntas"][qid].get("frecuencias") or {}).values(), 0) + 1
    ejes = (f"\\begin{{axis}}[dudamel/eje, xbar, bar width=9pt, width=0.5\\linewidth, height={_alto(k, 0.8)},\n"
            f"  xmin=0, xmax={tope}, xtick distance=1, ymin=0.4, ymax={k + 0.6}, ytick={{1,...,{k}}},\n"
            f"  yticklabels={{{rotulos}}}, yticklabel style={{text width=5.6cm, align=right, font=\\scriptsize}},\n"
            "  ymajorgrids=false, xlabel={Personas}, nodes near coords, nodes near coords style={font=\\scriptsize}]")
    cuerpo = [f"  \\addplot[dudamel/barra1] table[x=personas, y=fila, col sep=comma] {{\\dudameldir/datos/{archivo}.csv}};"]
    return _envolver([f"P{p['n']}. {p['texto']}: datos/{archivo}.csv"], ejes, cuerpo)


FIGURAS_OPCIONES = [("q21", "entrega"), ("q50", "problemas"), ("q59", "uso_real")]


# ---------------------------------------------------------------- tablas

def _tabla(comentario: list[str], columnas: str, encabezado: str, filas: list[str], larga: bool = False) -> str:
    entorno = "longtable" if larga else "tabular"
    return "\n".join([*[f"% {c}" for c in comentario], f"\\begin{{{entorno}}}{{{columnas}}}", "\\toprule",
                      encabezado + " \\\\", "\\midrule", *(["\\endhead"] if larga else []),
                      *filas, "\\bottomrule", f"\\end{{{entorno}}}", ""])


def _tabla_resumen(r: dict) -> str:
    s = r["sus"]
    filas = [f"Cuestionarios enviados & {r['enviados']} \\\\",
             f"A medias (no cuentan) & {r['borradores']} \\\\",
             f"SUS, media & {_n(s['media'])} \\\\",
             f"SUS, mediana & {_n(s['mediana'])} \\\\",
             f"SUS, desviación estándar & {_n(s['de'])} \\\\",
             (f"SUS, mínimo y máximo & {_n(min(s['valores']) if s['valores'] else None)} -- "
              f"{_n(max(s['valores']) if s['valores'] else None)} \\\\"),
             f"Tuvieron fallas de infraestructura (P50) & {r['con_fallas_de_infraestructura']} \\\\"]
    return "\n".join(["% Resumen del cuestionario", "\\begin{tabular}{lr}", "\\toprule", *filas, "\\bottomrule",
                      "\\end{tabular}", ""])


def _tabla_escalas(r: dict) -> str:
    filas = []
    for qid in ORDEN:
        p, x = PREGUNTAS[qid], r["preguntas"][qid]
        if p["tipo"] != "escala":
            continue
        arriba = f"{100 * x['arriba_del_medio']:.0f}~\\%" if x.get("arriba_del_medio") is not None else "---"
        ric = f"{_n(x.get('q1'))}--{_n(x.get('q3'))}" if x["n"] else "---"
        filas.append(f"P{p['n']} & {_seguro(p['texto'])} & {x['n']} & {_n(x.get('mediana'))} & {ric} & {arriba} \\\\")
    return _tabla(["Escalas del 1 al 5: mediana y rango intercuartílico; en P9--P20, % arriba del 3 (mejor con DUDAMEL)"],
                  "rp{7.2cm}rrrr", "P & Pregunta & $n$ & Mediana & RIC & $>3$", filas, larga=True)


def _tabla_conteos(r: dict) -> str:
    filas = []
    for qid in ORDEN:
        p, x = PREGUNTAS[qid], r["preguntas"][qid]
        if p["tipo"] != "numero":
            continue
        rango = f"{x['minimo']}--{x['maximo']}" if x["n"] else "---"
        filas.append(f"P{p['n']} & {_seguro(p['texto'])} & {x['n']} & {_n(x.get('media'))} & "
                     f"{_n(x.get('mediana'))} & {rango} \\\\")
    return _tabla(["Conteos: media, mediana y rango"], "rp{6.8cm}rrrr", "P & Pregunta & $n$ & Media & Mediana & Rango", filas)


def _tabla_frecuencias(r: dict) -> str:
    filas = []
    for qid in ORDEN:
        p, x = PREGUNTAS[qid], r["preguntas"][qid]
        if p["tipo"] not in ("opcion", "casillas"):
            continue
        nota = " (varias)" if p["tipo"] == "casillas" else ""
        filas.append(f"\\multicolumn{{3}}{{l}}{{\\textbf{{P{p['n']}.}} {_seguro(p['texto'])}{nota}}} \\\\")
        total = x["n"] or 0
        for o in p["opciones"]:
            k = (x.get("frecuencias") or {}).get(o, 0)
            pct = f"{100 * k / total:.0f}~\\%" if total else "---"
            filas.append(f"\\quad {_seguro(o)} & {k} & {pct} \\\\")
        filas.append("\\addlinespace")
    return _tabla(["Preguntas de opción y de casillas: personas y % de quienes la contestaron"],
                  "p{10.4cm}rr", "Opción & Personas & \\%", filas, larga=True)


def _tabla_abiertas(r: dict) -> str:
    filas = []
    for qid in ORDEN:
        p, x = PREGUNTAS[qid], r["preguntas"][qid]
        if p["tipo"] != "texto":
            continue
        filas.append(f"\\multicolumn{{1}}{{l}}{{\\textbf{{P{p['n']}.}} {_seguro(p['texto'])}}} \\\\")
        filas += [f"\\quad {_seguro(t)} \\\\" for t in x.get("respuestas", [])] or ["\\quad \\emph{Sin respuestas.} \\\\"]
        filas.append("\\addlinespace")
    return _tabla(["Respuestas abiertas, sin la cuenta (para codificación temática)"], "p{14.6cm}", "Respuesta",
                  filas, larga=True)


# ---------------------------------------------------------------- main y paquete

def _main(r: dict, figuras: list[tuple[str, str]], fecha: str) -> str:
    partes = [*preambulo(), "\\input{estilo-cuestionario}", "\\begin{document}",
              "\\section*{Cuestionario de evaluación de DUDAMEL}",
              (f"Resultados al {tex(fecha)}. Versión del cuestionario: {tex(VERSION)}. {r['enviados']} cuestionario(s) "
               "enviado(s); los que quedaron a medias no cuentan. Anónimo: cada persona es R01, R02\\ldots{} por orden de "
               "envío. El SUS va de 0 a 100 y no es un porcentaje."), ""]
    if not r["enviados"]:
        return "\n".join([*partes, "Todavía no hay cuestionarios enviados.", "\\end{document}", ""])
    if r["con_fallas_de_infraestructura"]:
        partes += [(f"\\paragraph{{Ojo.}} {r['con_fallas_de_infraestructura']} de {r['enviados']} persona(s) dijeron haber "
                    "tenido fallas de infraestructura (P50); conviene declararlo antes de concluir sobre la usabilidad."), ""]
    partes += ["\\begin{table}[htbp]", "\\centering", "\\small", "\\caption{Resumen.}", "\\label{tab:dudamel-cuest-resumen}",
               "\\input{\\dudameldir/tablas/resumen}", "\\end{table}", ""]
    for nombre, pie in figuras:
        partes += ["\\begin{figure}[htbp]", "\\centering", f"\\input{{\\dudameldir/figuras/{nombre}}}",
                   f"\\caption{{{pie}}}", f"\\label{{fig:dudamel-cuest-{nombre}}}", "\\end{figure}", ""]
    partes += ["\\begin{table}[htbp]", "\\centering", "\\small", "\\caption{Conteos.}", "\\label{tab:dudamel-cuest-conteos}",
               "\\input{\\dudameldir/tablas/conteos}", "\\end{table}", "",
               "\\clearpage", "\\subsection*{Escalas}", "{\\small\\input{\\dudameldir/tablas/escalas}}",
               "\\subsection*{Opciones}", "{\\small\\input{\\dudameldir/tablas/frecuencias}}",
               "\\subsection*{Respuestas abiertas}", "{\\small\\input{\\dudameldir/tablas/abiertas}}",
               "\\end{document}", ""]
    return "\n".join(partes)


LEEME = """# Resultados del cuestionario de evaluación para Overleaf

1. En Overleaf: **New Project → Upload Project** y sube este .zip. `main.tex` compila tal cual con
   pdfLaTeX o con XeLaTeX.
2. Para usarlo dentro de tu tesis, sube la carpeta (por ejemplo como `cuestionario/`) y en el
   preámbulo pon:

       \\newcommand{\\dudameldir}{cuestionario}
       \\input{cuestionario/estilo-dudamel}
       \\input{cuestionario/estilo-cuestionario}

   y donde quieras cada pieza: `\\input{cuestionario/figuras/sus}`, `\\input{cuestionario/tablas/resumen}`…
   `tablas/escalas.tex`, `frecuencias.tex` y `abiertas.tex` usan `longtable` y van fuera de un `table`.
3. `datos/respuestas.csv` trae una fila por persona (R01, R02…) sin cuenta ni correo, para SPSS, R o
   Excel. `resultados.json` es el resumen completo.

SUS (Brooke, 1996): ítems impares valor−1, pares 5−valor, suma × 2.5; va de 0 a 100 y no es un
porcentaje. La línea punteada en 68 es el promedio de referencia que se suele citar (Sauro, 2011).
En el SUS los ítems pares están redactados en negativo: ahí, «de acuerdo» es malo. Las escalas se
reportan con mediana y rango intercuartílico; los conteos con media, mediana y rango.
"""


def paquete_overleaf(docs: list[dict], fecha: str) -> bytes:
    """El .zip con los resultados de los cuestionarios `docs` (solo cuentan los enviados)."""
    r = resultados(docs)
    archivos = {"LEEME.md": LEEME, "estilo-dudamel.tex": ESTILO, "estilo-cuestionario.tex": ESTILO_CUESTIONARIO,
                "resultados.json": json.dumps(r, ensure_ascii=False, indent=1)}
    figuras: list[tuple[str, str]] = []
    if r["enviados"]:
        salida = io.StringIO()
        csv.writer(salida, lineterminator="\n").writerows(filas_csv(docs))
        archivos.update({"datos/respuestas.csv": salida.getvalue(), "datos/sus.csv": _datos_sus(r),
                         "figuras/sus.tex": _figura_sus(r), "tablas/resumen.tex": _tabla_resumen(r),
                         "tablas/escalas.tex": _tabla_escalas(r), "tablas/conteos.tex": _tabla_conteos(r),
                         "tablas/frecuencias.tex": _tabla_frecuencias(r), "tablas/abiertas.tex": _tabla_abiertas(r)})
        figuras.append(("sus", "Puntaje SUS por persona (0--100), con la media y la referencia de 68."))
        for g in GRUPOS_ESCALA:
            nombre = "sus_items" if g["id"] == "sus" else g["id"]
            archivos[f"datos/{nombre}.csv"] = _datos_grupo(g, r)
            archivos[f"figuras/{nombre}.tex"] = _figura_grupo(g, nombre)
            extra = " Los ítems pares están redactados en negativo." if g["id"] == "sus" else ""
            figuras.append((nombre, f"{tex(g['titulo'])}: respuestas por nivel (\\% de quienes contestaron).{extra}"))
        for qid, nombre in FIGURAS_OPCIONES:
            archivos[f"datos/{nombre}.csv"] = _datos_opciones(qid, r)
            archivos[f"figuras/{nombre}.tex"] = _figura_opciones(qid, nombre, r)
            figuras.append((nombre, f"P{PREGUNTAS[qid]['n']}. {_seguro(PREGUNTAS[qid]['texto'])}"))
    archivos["main.tex"] = _main(r, figuras, fecha)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for ruta, contenido in archivos.items():
            z.writestr(ruta, contenido)
    return buf.getvalue()
