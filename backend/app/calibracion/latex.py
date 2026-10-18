"""Paquete para Overleaf de una corrida de calibración (ADR 0026).

Un .zip que se sube tal cual a Overleaf (o se copia dentro de la tesis) y compila con
pdfLaTeX:

    main.tex                 ejemplo que usa todo (se puede borrar)
    estilo-dudamel.tex       preámbulo común: pgfplots, booktabs, colores y estilos
    figuras/*.tex            gráficas en pgfplots: leen sus datos de datos/*.csv
    tablas/*.tex             tablas con booktabs
    datos/*.csv              los números de cada gráfica (solo columnas numéricas)
    datos/valores.csv        cada término con su similitud y su etiqueta (para revisar)
    corrida.json             la corrida completa, con su configuración y sus huellas
    LEEME.md                 cómo usarlo

Las figuras son vectoriales y usan la tipografía del documento. Los colores son los de la
pantalla de Calibración: naranja = ambiguo / a debate, azul = no ambiguo / directo, aqua =
F1, y cada serie lleva además su propio trazo para que se lea en blanco y negro.
Sin dependencias: zipfile y texto.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile

ESTILO = r"""%% Estilo de las figuras y tablas de Dudamel (calibración, ADR 0026 y 0027).
%% Requiere pdfLaTeX con pgfplots y booktabs (incluidos en Overleaf).
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usepackage{booktabs}
\usepackage{longtable}
\usetikzlibrary{babel}
%% Carpeta del paquete respecto del documento principal: si lo copias dentro de tu tesis, define
%% antes de \input{...estilo-dudamel}: \newcommand{\dudameldir}{carpeta-del-paquete}
\providecommand{\dudameldir}{.}
\definecolor{dudamelAzul}{HTML}{2A78D6}
\definecolor{dudamelNaranja}{HTML}{EB6834}
\definecolor{dudamelAqua}{HTML}{1BAF7A}
\definecolor{dudamelGris}{HTML}{8A8984}
\definecolor{dudamelTinta}{HTML}{52514E}
\pgfplotsset{
  dudamel/eje/.style={
    width=\linewidth, height=0.62\linewidth,
    axis lines=left, axis line style={dudamelTinta!60},
    tick style={dudamelTinta!60}, tick label style={font=\small, text=dudamelTinta},
    label style={font=\small}, title style={font=\small\bfseries},
    grid=major, major grid style={dudamelGris!25, line width=0.3pt},
    legend style={font=\footnotesize, draw=none, fill=none, legend cell align=left},
    /pgf/number format/.cd, use period, 1000 sep={},
  },
  dudamel/umbral/.style={dudamelTinta, densely dashed, line width=0.8pt},
  dudamel/ambiguo/.style={dudamelNaranja, mark=*, mark size=2.2pt, mark options={fill=dudamelNaranja, draw=white, line width=0.4pt}},
  dudamel/noambiguo/.style={dudamelAzul, mark=square*, mark size=2pt, mark options={fill=dudamelAzul, draw=white, line width=0.4pt}},
  dudamel/sinetiqueta/.style={dudamelGris, mark=o, mark size=2pt},
  dudamel/precision/.style={dudamelAzul, line width=1.2pt, mark=square*, mark size=1.6pt},
  dudamel/exhaustividad/.style={dudamelNaranja, line width=1.2pt, densely dashed, mark=triangle*, mark size=2pt},
  dudamel/f1/.style={dudamelAqua, line width=1.2pt, dashdotted, mark=*, mark size=1.6pt},
  dudamel/debates/.style={dudamelNaranja, line width=1.2pt, mark=*, mark size=1.6pt},
  dudamel/directos/.style={dudamelAzul, line width=1.2pt, densely dashed, mark=square*, mark size=1.6pt},
  dudamel/roc/.style={dudamelAzul, line width=1.2pt, mark=*, mark size=1.4pt},
  dudamel/azar/.style={dudamelGris, densely dotted, line width=0.8pt},
  dudamel/deteccion/.style={dudamelNaranja, only marks, mark=*, mark size=2.4pt, mark options={fill=dudamelNaranja, draw=white, line width=0.4pt},
    error bars/x dir=both, error bars/x explicit, error bars/error bar style={dudamelNaranja, line width=0.9pt}},
  dudamel/aprobacion/.style={dudamelAqua, only marks, mark=square*, mark size=2.2pt, mark options={fill=dudamelAqua, draw=white, line width=0.4pt},
    error bars/x dir=both, error bars/x explicit, error bars/error bar style={dudamelAqua, line width=0.9pt}},
}
"""

_ESCAPES = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
            "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
            "<": r"\textless{}", ">": r"\textgreater{}"}


def tex(texto) -> str:
    """Texto de la persona o de los agentes, seguro dentro de LaTeX (los acentos van en UTF-8)."""
    return "".join(_ESCAPES.get(c, c) for c in str(texto if texto is not None else ""))


def _num(x, d: int = 3) -> str:
    return "nan" if x is None else f"{x:.{d}f}"


def _celda(x, d: int = 3) -> str:
    return "---" if x is None else f"{x:.{d}f}"


def _ic(ic: dict | None, d: int = 3) -> str:
    return "" if not ic or ic.get("bajo") is None else f" [{ic['bajo']:.{d}f}, {ic['alto']:.{d}f}]"


def _csv(filas: list[list], encabezado: list[str]) -> str:
    salida = io.StringIO()
    w = csv.writer(salida, lineterminator="\n")
    w.writerow(encabezado)
    w.writerows(filas)
    return salida.getvalue()


def _dispersion(valores: list[dict]) -> dict[str, str]:
    """Una tabla por clase con (similitud, y): y es la fila de la clase más un desplazamiento
    determinista para que los puntos iguales no se tapen."""
    filas = {"ambiguos": [], "no_ambiguos": [], "sin_etiqueta": []}
    base = {"ambiguos": 2, "no_ambiguos": 1, "sin_etiqueta": 0}
    for i, v in enumerate(sorted(valores, key=lambda v: (v["similitud"], v["entrevista_id"], v["termino"]))):
        clase = "sin_etiqueta" if v.get("ambiguo") is None else ("ambiguos" if v["ambiguo"] else "no_ambiguos")
        filas[clase].append([_num(v["similitud"], 4), f"{base[clase] + ((i * 7) % 9 - 4) * 0.045:.3f}"])
    return {k: _csv(f, ["similitud", "y"]) for k, f in filas.items()}


def _figura_distribucion(r: dict, hay: dict[str, bool]) -> str:
    u = r["umbral_configurado"]
    series = []
    for clase, estilo in (("ambiguos", "ambiguo"), ("no_ambiguos", "noambiguo"), ("sin_etiqueta", "sinetiqueta")):
        if hay[clase]:
            # sin leyenda: cada clase es una fila con su nombre en el eje
            series.append(f"  \\addplot[only marks, dudamel/{estilo}] table[x=similitud, y=y, col sep=comma]"
                          f" {{\\dudameldir/datos/similitud_{clase}.csv}};")
    return "\n".join([
        "% Similitud inicial de cada término por clase del ground truth; la línea es el umbral configurado.",
        "\\begin{tikzpicture}",
        "\\begin{axis}[dudamel/eje, height=0.42\\linewidth, xmin=0, xmax=1, ymin=-0.5, ymax=2.5,",
        "  xlabel={Similitud inicial (coseno mínimo entre paráfrasis)},",
        "  ytick={0,1,2}, yticklabels={Sin etiqueta, No ambiguo, Ambiguo}, ymajorgrids=false, clip=false]",
        *series,
        f"  \\addplot[dudamel/umbral, forget plot] coordinates {{({u},-0.5) ({u},2.5)}};",
        f"  \\node[anchor=south west, font=\\footnotesize, text=dudamelTinta] at (axis cs:{u},2.5) {{umbral {u}}};",
        "\\end{axis}",
        "\\end{tikzpicture}",
        "",
    ])


def _figura_metricas(r: dict) -> str:
    u = r["umbral_configurado"]
    return "\n".join([
        "% Precisión, exhaustividad y F1 de «a debate» contra «ambiguo» en cada umbral de la rejilla.",
        "\\begin{tikzpicture}",
        "\\begin{axis}[dudamel/eje, ymin=0, ymax=1.05, xlabel={Umbral}, ylabel={Valor},",
        "  unbounded coords=jump, legend pos=south west]",
        "  \\addplot[dudamel/precision] table[x=umbral, y=precision, col sep=comma] {\\dudameldir/datos/rejilla.csv};",
        "  \\addlegendentry{Precisión}",
        "  \\addplot[dudamel/exhaustividad] table[x=umbral, y=exhaustividad, col sep=comma] {\\dudameldir/datos/rejilla.csv};",
        "  \\addlegendentry{Exhaustividad}",
        "  \\addplot[dudamel/f1] table[x=umbral, y=f1, col sep=comma] {\\dudameldir/datos/rejilla.csv};",
        "  \\addlegendentry{F1}",
        f"  \\addplot[dudamel/umbral, forget plot] coordinates {{({u},0) ({u},1.05)}};",
        "\\end{axis}",
        "\\end{tikzpicture}",
        "",
    ])


def _figura_debates(r: dict) -> str:
    u, n = r["umbral_configurado"], r["n_valores"]
    return "\n".join([
        "% Cuántos términos irían a debate y cuántos se aceptarían directo con cada umbral.",
        "\\begin{tikzpicture}",
        f"\\begin{{axis}}[dudamel/eje, ymin=0, ymax={max(n, 1)}, xlabel={{Umbral}}, ylabel={{Términos}},",
        "  legend pos=north west]",
        "  \\addplot[dudamel/debates] table[x=umbral, y=debates, col sep=comma] {\\dudameldir/datos/rejilla.csv};",
        "  \\addlegendentry{A debate}",
        "  \\addplot[dudamel/directos] table[x=umbral, y=directos, col sep=comma] {\\dudameldir/datos/rejilla.csv};",
        "  \\addlegendentry{Aceptados directo}",
        f"  \\addplot[dudamel/umbral, forget plot] coordinates {{({u},0) ({u},{max(n, 1)})}};",
        "\\end{axis}",
        "\\end{tikzpicture}",
        "",
    ])


def _figura_roc(gt: dict) -> str:
    a = gt.get("auc")
    ic = (gt.get("confianza") or {}).get("medidas", {}).get("auc")
    leyenda = f"AUC = {a:.3f}{_ic(ic)}" if a is not None else "AUC no disponible"
    return "\n".join([
        "% Curva ROC: tasa de ambiguos a debate contra tasa de no ambiguos a debate, al mover el umbral.",
        "\\begin{tikzpicture}",
        "\\begin{axis}[dudamel/eje, width=0.62\\linewidth, height=0.62\\linewidth, xmin=0, xmax=1, ymin=0, ymax=1,",
        "  xlabel={Tasa de falsos positivos}, ylabel={Tasa de verdaderos positivos}, legend pos=south east]",
        "  \\addplot[dudamel/roc] table[x=fpr, y=tpr, col sep=comma] {\\dudameldir/datos/roc.csv};",
        f"  \\addlegendentry{{{leyenda}}}",
        "  \\addplot[dudamel/azar] coordinates {(0,0) (1,1)};",
        "  \\addlegendentry{Azar}",
        "\\end{axis}",
        "\\end{tikzpicture}",
        "",
    ])


def _tabla_metricas(r: dict, gt: dict) -> str:
    c, m = gt["configurado"], (gt.get("confianza") or {}).get("medidas", {})
    conf = gt.get("confianza") or {}
    filas = [
        ("Términos etiquetados con similitud", f"{gt['n_emparejados']} ({gt['n_ambiguos']} ambiguos, {gt['n_no_ambiguos']} no ambiguos)"),
        ("AUC", f"{_celda(gt.get('auc'))}{_ic(m.get('auc'))}"),
        ("Precisión", f"{_celda(c['precision'])}{_ic(m.get('precision'))}"),
        ("Exhaustividad", f"{_celda(c['exhaustividad'])}{_ic(m.get('exhaustividad'))}"),
        ("F1", f"{_celda(c['f1'])}{_ic(m.get('f1'))}"),
        ("¿Algún umbral separa los casos?", {True: "sí", False: "no", None: "---"}[gt["separacion"]["separa"]]),
    ]
    cuerpo = "\n".join(f"{tex(a)} & {tex(b)} \\\\" for a, b in filas)
    return "\n".join([
        f"% Métricas con el umbral configurado ({r['umbral_configurado']}). Entre corchetes, intervalo bootstrap "
        f"percentil al {int(conf.get('nivel', 0.95) * 100)} % ({conf.get('remuestreos')} remuestreos, semilla {conf.get('semilla')}).",
        "\\begin{tabular}{@{}ll@{}}",
        "\\toprule",
        "Medida & Valor \\\\",
        "\\midrule",
        cuerpo,
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ])


def _tabla_confusion(gt: dict) -> str:
    c = gt["configurado"]
    return "\n".join([
        "% Matriz de confusión con el umbral configurado (positivo = a debate).",
        "\\begin{tabular}{@{}lrr@{}}",
        "\\toprule",
        " & A debate & Aceptado directo \\\\",
        "\\midrule",
        f"Ambiguo & {c['vp']} & {c['fn']} \\\\",
        f"No ambiguo & {c['fp']} & {c['vn']} \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ])


def _tabla_rejilla(r: dict, gt: dict | None) -> str:
    met = {f["umbral"]: f for f in (gt or {}).get("por_umbral", [])}
    filas = []
    for f in r["rejilla"]:
        g = met.get(f["umbral"], {})
        celdas = [f"{f['umbral']:.3f}", str(f["directos"]), str(f["debates"]),
                  _celda(g.get("precision")), _celda(g.get("exhaustividad")), _celda(g.get("f1"))]
        if f["configurado"]:
            celdas = [f"\\textbf{{{x}}}" for x in celdas]
        filas.append(" & ".join(celdas) + " \\\\")
    return "\n".join([
        "% Qué habría decidido la regla «similitud >= umbral» con cada umbral (en negritas, el configurado).",
        "\\begin{tabular}{@{}rrrrrr@{}}",
        "\\toprule",
        "Umbral & Directos & A debate & Precisión & Exhaustividad & F1 \\\\",
        "\\midrule",
        *filas,
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ])


def _tabla_por_tipo(gt: dict) -> str:
    nombres = {"lexica": "Léxica", "alcance": "Alcance", "anaforica": "Anafórica", "sintactica": "Sintáctica",
               "regional": "Regional", "vaguedad": "Vaguedad", "no_ambiguo": "No ambiguo"}
    filas = [f"{tex(nombres.get(t['tipo'], t['tipo']))} & {t['n']} & {t['a_debate']} & {t['proporcion']:.3f} \\\\"
             for t in gt.get("por_tipo", [])]
    return "\n".join([
        "% Por tipo de ambigüedad: cuántos términos van a debate con el umbral configurado (en los no",
        "% ambiguos, esa proporción son falsos positivos).",
        "\\begin{tabular}{@{}lrrr@{}}",
        "\\toprule",
        "Tipo & Términos & A debate & Proporción \\\\",
        "\\midrule",
        *filas,
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ])


def _tabla_valores(r: dict) -> str:
    gt_txt = {True: "ambiguo", False: "no ambiguo", None: "---"}
    dec = {"aceptado_directo": "directo", "en_debate": "debate"}
    via = {"aceptado_directo": "directo", "consenso": "consenso", "arbitraje": "arbitraje"}
    filas = [f"{tex(v['entrevista_id'])} & {tex(v['termino'])} & {v['similitud']:.3f} & {gt_txt[v.get('ambiguo')]} & "
             f"{dec.get(v['decision_real'], '---')} & {via.get(v.get('via'), '---')} \\\\"
             for v in sorted(r["valores"], key=lambda v: (v["entrevista_id"], v["similitud"]))]
    return "\n".join([
        "% Cada término que llegó al mecanismo de divergencia (usa longtable: puede ocupar varias páginas).",
        "\\begin{longtable}{@{}llrlll@{}}",
        "\\toprule",
        "Entrevista & Término & Similitud & Ground truth & Decisión & Vía final \\\\",
        "\\midrule",
        "\\endhead",
        *filas,
        "\\bottomrule",
        "\\end{longtable}",
        "",
    ])


def _main(c: dict, gt: dict | None, hay_figura: set[str]) -> str:
    r = c["resultado"]
    figuras = [(n, pie) for n, pie in (
        ("distribucion", "Similitud inicial de cada término por clase del ground truth." if gt
         else "Similitud inicial de cada término (sin ground truth)."),
        ("metricas", "Precisión, exhaustividad y F1 con cada umbral."),
        ("roc", "Curva ROC de la similitud inicial."),
        ("debates", "Términos a debate y aceptados directo con cada umbral."),
    ) if n in hay_figura]
    tablas = [("rejilla", "Sensibilidad del umbral.")]
    if gt:
        tablas = [("metricas", "Métricas con el umbral configurado."), ("confusion", "Matriz de confusión."),
                  ("por_tipo", "Por tipo de ambigüedad."), *tablas]
    partes = [
        "\\documentclass[11pt]{article}",
        "\\usepackage[utf8]{inputenc}",
        "\\usepackage[T1]{fontenc}",
        "\\usepackage[spanish,es-noshorthands,es-tabla]{babel}",
        "\\usepackage[margin=2.5cm]{geometry}",
        "\\input{estilo-dudamel}",
        "\\begin{document}",
        f"\\section*{{Calibración del umbral --- corrida {tex(c['calibracion_id'])}}}",
        f"Fecha: {tex(c['fecha'])}. Versión de Dudamel: {tex(c.get('version_app'))}. "
        f"Umbral configurado: {r['umbral_configurado']}. Entrevistas: {len(r['entrevistas'])}. "
        f"Términos con similitud: {r['n_valores']}. "
        f"Embeddings: {tex(', '.join(r['modelos_embeddings']) or '---')}.",
        "",
    ]
    for nombre, pie in figuras:
        partes += ["\\begin{figure}[htbp]", "\\centering", f"\\input{{\\dudameldir/figuras/{nombre}}}",
                   f"\\caption{{{pie}}}", f"\\label{{fig:dudamel-{nombre}}}", "\\end{figure}", ""]
    for nombre, pie in tablas:
        partes += ["\\begin{table}[htbp]", "\\centering", f"\\caption{{{pie}}}", f"\\label{{tab:dudamel-{nombre}}}",
                   f"\\input{{\\dudameldir/tablas/{nombre}}}", "\\end{table}", ""]
    partes += ["\\input{\\dudameldir/tablas/valores}", "\\end{document}", ""]
    return "\n".join(partes)


LEEME = """# Paquete de la corrida {id} para Overleaf

1. En Overleaf: **New Project → Upload Project** y sube este .zip. `main.tex` compila tal
   cual con pdfLaTeX y muestra todas las figuras y tablas.
2. Para usarlo dentro de tu tesis, sube la carpeta (por ejemplo como `dudamel-{id}/`) y en
   el preámbulo pon:

       \\newcommand{{\\dudameldir}}{{dudamel-{id}}}
       \\input{{dudamel-{id}/estilo-dudamel}}

   y donde quieras cada pieza: `\\input{{dudamel-{id}/figuras/roc}}`,
   `\\input{{dudamel-{id}/tablas/metricas}}`, etc. (dentro de un `figure` o `table`).
3. `corrida.json` es la corrida completa: configuración, versión, entrevistas con la huella
   de sus similitudes y etiquetas, y todos los resultados. Cítala por su id ({id}) y fecha.

Las figuras leen sus números de `datos/*.csv`; `datos/valores.csv` lista cada término con su
similitud, su etiqueta y la decisión del sistema.

Si usas `babel` en español, deja la opción `es-noshorthands` (o carga `\\usetikzlibrary{{babel}}`,
como hace `estilo-dudamel.tex`) para que TikZ no choque con los atajos del idioma.
"""


def paquete_overleaf(corrida: dict) -> bytes:
    """El .zip de una corrida guardada."""
    r = corrida["resultado"]
    gt = r.get("con_ground_truth")
    disp = _dispersion(r["valores"])
    hay = {k: v.count("\n") > 1 for k, v in disp.items()}
    rejilla = {f["umbral"]: f for f in (gt or {}).get("por_umbral", [])}
    archivos = {
        "LEEME.md": LEEME.format(id=corrida["calibracion_id"]),
        "estilo-dudamel.tex": ESTILO,
        "corrida.json": json.dumps(corrida, ensure_ascii=False, indent=1),
        "datos/rejilla.csv": _csv([[_num(f["umbral"]), f["directos"], f["debates"],
                                    _num(rejilla.get(f["umbral"], {}).get("precision")),
                                    _num(rejilla.get(f["umbral"], {}).get("exhaustividad")),
                                    _num(rejilla.get(f["umbral"], {}).get("f1"))] for f in r["rejilla"]],
                                  ["umbral", "directos", "debates", "precision", "exhaustividad", "f1"]),
        "datos/valores.csv": _csv([[v["entrevista_id"], v["termino"], _num(v["similitud"], 4),
                                    {True: 1, False: 0, None: ""}[v.get("ambiguo")], v["decision_real"], v.get("via") or "",
                                    v["tipo_ambiguedad"], v.get("modelo_embeddings") or ""] for v in r["valores"]],
                                  ["entrevista", "termino", "similitud", "ambiguo", "decision", "via", "tipo_sistema",
                                   "modelo_embeddings"]),
        "figuras/distribucion.tex": _figura_distribucion(r, hay),
        "figuras/debates.tex": _figura_debates(r),
        "tablas/rejilla.tex": _tabla_rejilla(r, gt),
        "tablas/valores.tex": _tabla_valores(r),
    }
    for clase, contenido in disp.items():
        archivos[f"datos/similitud_{clase}.csv"] = contenido
    if gt:
        archivos.update({
            "tablas/metricas.tex": _tabla_metricas(r, gt),
            "tablas/confusion.tex": _tabla_confusion(gt),
            "tablas/por_tipo.tex": _tabla_por_tipo(gt),
        })
        # sin las dos clases no hay curva ROC, y sin ningún valor definido no hay qué trazar
        if gt["roc"]:
            archivos["datos/roc.csv"] = _csv([[_num(p["fpr"], 4), _num(p["tpr"], 4)] for p in gt["roc"]], ["fpr", "tpr"])
            archivos["figuras/roc.tex"] = _figura_roc(gt)
        if any(f.get(k) is not None for f in gt["por_umbral"] for k in ("precision", "exhaustividad", "f1")):
            archivos["figuras/metricas.tex"] = _figura_metricas(r)
    archivos["main.tex"] = _main(corrida, gt, {n[len("figuras/"):-4] for n in archivos if n.startswith("figuras/")})
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return salida.getvalue()
