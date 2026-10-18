"""Paquete para Overleaf de una prueba de modelos (ADR 0027, 0028 y 0029).

Mismo formato que el de las corridas de calibración (ADR 0026), con el mismo preámbulo, y compila
con pdfLaTeX y con XeLaTeX:

    main.tex                     ejemplo que usa todo (se puede borrar)
    estilo-dudamel.tex           preámbulo común (\\dudameldir)
    figuras/modelos.tex          exhaustividad, precisión y falsas alarmas por modelo (barras, Wilson)
    figuras/confusion.tex        matriz de confusión por modelo
    figuras/calidad.tex          los tres criterios de calidad por modelo (Wilson)
    figuras/cobertura.tex        distribución de la cobertura de lecturas esperadas por ítem
    figuras/parejas.tex          parejas discriminadas (ambiguo marcado y su control no)
    figuras/latencia.tex         mediana y p90 de la latencia por modelo
    figuras/modos.tex            modos de falla de los falsos negativos
    figuras/subenumeracion.tex   lecturas esperadas contra intenciones producidas, por ítem
    figuras/estabilidad.tex      detección por corrida en una serie idéntica (si la hay)
    tablas/*.tex                 booktabs y longtable (modelos, confusión, calidad, clases, pares,
                                 subenumeración, modos, estabilidad, aprobación v2.3, banco, respuestas)
    apendice/rubrica.tex         la rúbrica de la revisión (también como rubrica.md)
    datos/*.csv                  los números de cada figura: ninguna figura los trae incrustados
    prueba.json                  la prueba completa con sus revisiones, su uid y la huella del banco
    LEEME.md

Una figura cuya métrica no se puede calcular (sin revisión, sin controles, sin falsos negativos)
no se genera, y `main.tex` dice qué falta; en las tablas, el valor es «---».
"""
from __future__ import annotations

import io
import json
import zipfile

from .latex import ESTILO, _csv, _num, preambulo, tex
from .pruebas_modelos import banco_de, codigo_de, es_ambiguo, etiqueta_modelo
from .rubrica import CLAVES, COBERTURA, CRITERIOS, MODOS_FALLA, REGLA_AGREGADO, markdown

NOMBRE_CLASE = {"polisemia": "Polisemia", "regionalismo": "Regionalismo", "inequivoco": "Inequívoco"}
NOMBRE_CRITERIO = {c["clave"]: c["nombre"] for c in CRITERIOS}
NOMBRE_MODO = {m["clave"]: m["nombre"] for m in MODOS_FALLA}
# lo que pdfLaTeX con T1 y utf8 compila sin paquetes extra; las respuestas de los modelos pueden traer otros
_PUNTUACION = set("–—‘’“”…•«»¿¡°·")


def _seguro(texto) -> str:
    """Texto de un modelo, escapado y sin caracteres que pdfLaTeX no conoce (emojis, flechas…)."""
    limpio = "".join(c if ord(c) < 0x180 or c in _PUNTUACION else "?" for c in str(texto or ""))
    return tex(limpio)


def _ic(m: dict | None) -> str:
    """Proporción con su intervalo de Wilson, o «---» si no se puede calcular. El intervalo va
    siempre: con menos de 30 casos es lo que dice cuánto vale el número."""
    if not m or m.get("valor") is None:
        return "---"
    return f"{m['valor']:.2f} [{m['bajo']:.2f}, {m['alto']:.2f}]"


def _p(x) -> str:
    if x is None:
        return "---"
    return f"{x:.2g}" if x < 0.001 else f"{x:.3f}"


def _error(x: dict | None) -> list[str]:
    """[valor, distancia al extremo bajo, distancia al alto] para las barras de error de pgfplots."""
    if not x or x.get("valor") is None:
        return ["nan", "nan", "nan"]
    return [_num(x["valor"]), _num(x["valor"] - x["bajo"]), _num(x["alto"] - x["valor"])]


def _nombres(r: dict) -> str:
    """Las etiquetas del eje vertical, de abajo arriba (la fila 1 es el último modelo)."""
    return ",".join("{" + _seguro(m["etiqueta"]) + "}" for m in reversed(r["modelos"]))


def _alto(n: int, por_fila: float = 1.25) -> str:
    return f"{max(4.4, 1.8 + por_fila * n):.1f}cm"


def _envolver(comentario: list[str], ejes: str, cuerpo: list[str]) -> str:
    return "\n".join([*[f"% {c}" for c in comentario], "\\begin{tikzpicture}", ejes, *cuerpo,
                      "\\end{axis}", "\\end{tikzpicture}", ""])


def _barras(r: dict, series: list[tuple[str, str, str]], *, archivo: str, xlabel: str, xmax: str = "1") -> str:
    """Barras horizontales por modelo con barra de error explícita. `series`: (columna, estilo, leyenda).
    Cada serie se desplaza a mano dentro de la fila del modelo (`y expr`, `bar shift=0pt`): así la
    barra de error cae exactamente sobre su barra, cosa que el agrupado automático no garantiza."""
    n, k = len(r["modelos"]), len(series)
    paso = 0.62 / max(k, 1)
    ejes = (f"\\begin{{axis}}[dudamel/eje, xbar, bar shift=0pt, bar width={max(3.5, 11 - 2.5 * k):.1f}pt, width=0.66\\linewidth,\n"
            f"  height={_alto(n)}, xmin=0, xmax={xmax}, ymin=0.4, ymax={n + 0.6}, ytick={{1,...,{n}}},\n"
            f"  yticklabels={{{_nombres(r)}}}, ymajorgrids=false, xlabel={{{xlabel}}}, unbounded coords=discard,\n"
            "  legend columns=1, legend style={at={(0.5,1.03)}, anchor=south}]")
    cuerpo = []
    for j, (col, estilo, leyenda) in enumerate(series):
        dy = ((k - 1) / 2 - j) * paso  # la primera serie arriba, como en la leyenda
        cuerpo += [(f"  \\addplot[dudamel/{estilo}, dudamel/error] table[x={col}, y expr=\\thisrow{{fila}}{dy:+.3f},"
                    f" x error minus={col}_menos, x error plus={col}_mas, col sep=comma] {{\\dudameldir/datos/{archivo}}};"),
                   f"  \\addlegendentry{{{leyenda}}}"]
    return ejes, cuerpo


# ---------------------------------------------------------------- datos

def _datos_modelos(r: dict) -> str:
    filas = []
    n = len(r["modelos"])
    for k, m in enumerate(r["modelos"]):
        c = m["calidad"]["criterios"]
        lat = m["latencia_ms"]
        filas.append([n - k, *_error(m["deteccion"]), *_error(m["precision"]), *_error(m["falsas_alarmas"]),
                      *[x for clave in CLAVES for x in _error(c[clave])],
                      *_error((m.get("parejas") or {}).get("proporcion")),
                      _num(None if lat["mediana"] is None else lat["mediana"] / 1000, 2),
                      _num(None if lat["p90"] is None else lat["p90"] / 1000, 2)])
    encabezado = ["fila"]
    for col in ("det", "pre", "fal", *CLAVES, "par"):
        encabezado += [col, f"{col}_menos", f"{col}_mas"]
    return _csv(filas, [*encabezado, "lat_mediana", "lat_p90"])


def _datos_confusion(r: dict) -> tuple[str, str]:
    """Dos tablas (aciertos y fallos) con la posición de cada casilla y su rótulo: cada modelo ocupa
    dos columnas (marcó ambiguo / unívoco) y dos filas (verdad ambigua / inequívoca)."""
    aciertos, fallos = [], []
    for k, m in enumerate(r["modelos"]):
        c, x0 = m["confusion"], 3 * k
        sin = not m["n_inequivocos"]  # sin controles no hay FP ni VN que contar
        aciertos += [[x0, 1, f"VP {c['vp']}"], [x0 + 1, 0, "VN ---" if sin else f"VN {c['vn']}"]]
        fallos += [[x0 + 1, 1, f"FN {c['fn']}"], [x0, 0, "FP ---" if sin else f"FP {c['fp']}"]]
    return _csv(aciertos, ["x", "y", "rotulo"]), _csv(fallos, ["x", "y", "rotulo"])


def _datos_cobertura(r: dict) -> tuple[str, list[str]]:
    """Cuántos ítems quedaron con cada proporción de lecturas cubiertas, por modelo."""
    valores = sorted({round(c["cubiertas"] / c["esperadas"], 4) for m in r["modelos"]
                      for c in m["calidad"]["cobertura"]["por_item"] if c["esperadas"]})
    filas = []
    for j, v in enumerate(valores):
        fila = [j, _num(v, 2)]
        for m in r["modelos"]:
            fila.append(sum(1 for c in m["calidad"]["cobertura"]["por_item"]
                            if c["esperadas"] and round(c["cubiertas"] / c["esperadas"], 4) == v))
        filas.append(fila)
    rotulos = [f"{v:.2f}" for v in valores]
    return _csv(filas, ["x", "proporcion", *[m["id"] for m in r["modelos"]]]), rotulos


def _datos_modos(r: dict) -> str:
    filas = [[j, m_["clave"], *[mm["falsos_negativos"]["por_modo"].get(m_["clave"], 0) for mm in r["modelos"]]]
             for j, m_ in enumerate(MODOS_FALLA)]
    filas.append([len(MODOS_FALLA), "sin_clasificar", *[mm["falsos_negativos"]["sin_clasificar"] for mm in r["modelos"]]])
    return _csv(filas, ["y", "modo", *[m["id"] for m in r["modelos"]]])


def _datos_subenumeracion(r: dict) -> dict[str, str]:
    """Por modelo (un archivo cada uno), un punto por ítem ambiguo respondido: lecturas esperadas
    (con un desplazamiento por modelo) contra intenciones producidas (con un desplazamiento
    determinista para que los puntos iguales no se tapen)."""
    archivos = {}
    n = len(r["modelos"])
    for k, m in enumerate(r["modelos"]):
        filas = [[p["item"], p["lecturas"], p["intenciones"],
                  f"{p['lecturas'] + (k - (n - 1) / 2) * 0.18 + ((j * 7) % 5 - 2) * 0.02:.3f}",
                  f"{p['intenciones'] + ((j * 5) % 7 - 3) * 0.035:.3f}"]
                 for j, p in enumerate(x for x in m["subenumeracion"]["por_item"] if x["ok"])]
        archivos[f"datos/subenumeracion_{m['id']}.csv"] = _csv(filas, ["item", "lecturas", "intenciones", "x", "y"])
    return archivos


def _datos_estabilidad(e: dict) -> dict[str, str]:
    """La detección por corrida (una columna por modelo) y, por modelo, su rango (mínimo a máximo)."""
    corridas = [c["corrida"] for c in e["corridas"]]
    filas = [[c, *[_num(m["detecciones"][j], 0) for m in e["modelos"]]] for j, c in enumerate(corridas)]
    archivos = {"datos/estabilidad.csv": _csv(filas, ["corrida", *[f"m{k + 1}" for k in range(len(e["modelos"]))]])}
    for k, m in enumerate(e["modelos"]):
        if m["minimo"] is not None:
            medio = (m["minimo"] + m["maximo"]) / 2
            archivos[f"datos/estabilidad_rango_m{k + 1}.csv"] = _csv(
                [[f"{max(corridas) + 0.6 + 0.25 * k:.2f}", _num(medio, 1), _num(medio - m["minimo"], 1),
                  _num(m["maximo"] - medio, 1)]], ["x", "medio", "menos", "mas"])
    return archivos


# ---------------------------------------------------------------- figuras

def _figura_modelos(r: dict) -> str:
    con_controles = any(m["falsas_alarmas"] for m in r["modelos"])
    series = [("det", "barra1", "Exhaustividad (ambiguos detectados)")]
    if con_controles:
        series += [("pre", "barra3", "Precisión"), ("fal", "barra2", "Falsas alarmas (inequívocos marcados)")]
    ejes, cuerpo = _barras(r, series, archivo="modelos.csv", xlabel="Proporción")
    return _envolver([
        "Por modelo: exhaustividad = ambiguos que marcó como ambiguos (2 o más intenciones) sobre todos los ambiguos",
        "(un error cuenta como no detectado); precisión = ambiguos sobre todo lo marcado; falsas alarmas =",
        "inequívocos marcados como ambiguos sobre los inequívocos que respondieron. Barras de error: intervalo de",
        "Wilson al 95 %. Datos: datos/modelos.csv.",
    ], ejes, cuerpo)


def _figura_confusion(r: dict) -> str:
    n = len(r["modelos"])
    ticks = ",".join(f"{3 * k},{3 * k + 1}" for k in range(n))
    etiquetas = ",".join("{Ambiguo},{Unívoco}" for _ in range(n))
    nombres = "\n".join(f"  \\node[font=\\scriptsize, anchor=south, text width=3cm, align=center] at (axis cs:{3 * k + 0.5},1.5) {{{_seguro(m['etiqueta'])}}};"
                        for k, m in enumerate(r["modelos"]))
    ejes = (f"\\begin{{axis}}[width={min(15.5, max(7, 5.2 * n)):.1f}cm, height=5.6cm, xmin=-0.7, xmax={3 * n - 1.3}, ymin=-0.8, ymax=1.8,\n"
            f"  axis lines=none, xtick={{{ticks}}}, xticklabels={{{etiquetas}}}, ytick={{0,1}},\n"
            "  yticklabels={{Inequívoco},{Ambiguo}}, tick label style={font=\\footnotesize}, clip=false,\n"
            "  point meta=explicit symbolic, nodes near coords, nodes near coords align={center},\n"
            "  every node near coord/.append style={font=\\footnotesize, anchor=center}]")
    cuerpo = [
        "  \\addplot[dudamel/acierto] table[x=x, y=y, meta=rotulo, col sep=comma] {\\dudameldir/datos/confusion_aciertos.csv};",
        "  \\addplot[dudamel/fallo] table[x=x, y=y, meta=rotulo, col sep=comma] {\\dudameldir/datos/confusion_fallos.csv};",
        nombres,
        "  \\node[font=\\footnotesize, anchor=east] at (axis cs:-0.6,1) {Verdad: ambiguo};",
        "  \\node[font=\\footnotesize, anchor=east] at (axis cs:-0.6,0) {Verdad: inequívoco};",
        *[line for k in range(n) for line in (
            f"  \\node[font=\\scriptsize, text=dudamelTinta] at (axis cs:{3 * k},-0.62) {{marcó ambiguo}};",
            f"  \\node[font=\\scriptsize, text=dudamelTinta] at (axis cs:{3 * k + 1},-0.62) {{unívoco}};")],
    ]
    return _envolver([
        "Matriz de confusión por modelo (positivo = marcó el término como ambiguo). Casillas sólidas: aciertos (VP,",
        "VN); punteadas: fallos (FN, FP). Un error del modelo cuenta como FN en un ambiguo y no entra en un inequívoco.",
        "Datos: datos/confusion_aciertos.csv y datos/confusion_fallos.csv.",
    ], ejes, cuerpo)


def _figura_calidad(r: dict) -> str:
    estilos = {"fidelidad": "barra1", "delimitacion": "barra2", "intencion": "barra4"}
    ejes, cuerpo = _barras(r, [(c, estilos[c], NOMBRE_CRITERIO[c]) for c in CLAVES], archivo="modelos.csv",
                           xlabel="Proporción de salidas revisadas que cumplen")
    return _envolver([
        "Calidad por modelo: proporción de salidas revisadas que cumplen cada criterio (fidelidad, delimitación,",
        "intención; ver el apéndice de la rúbrica). Un criterio se cumple si lo cumplen todas las intenciones de la",
        "salida. Barras de error: intervalo de Wilson al 95 %. Datos: datos/modelos.csv.",
    ], ejes, cuerpo)


def _figura_cobertura(r: dict, rotulos: list[str]) -> str:
    estilos = ("barra1", "barra2", "barra4", "barra3")
    ejes = (f"\\begin{{axis}}[dudamel/eje, ybar=1pt, bar width=7pt, width=0.8\\linewidth, height=0.45\\linewidth,\n"
            f"  ymin=0, xtick={{0,...,{len(rotulos) - 1}}}, xticklabels={{{','.join(rotulos)}}},\n"
            "  xlabel={Lecturas esperadas cubiertas / esperadas}, ylabel={Ítems ambiguos revisados},\n"
            "  enlarge x limits=0.15, legend style={at={(0.5,1.03)}, anchor=south}, legend columns=2]")
    cuerpo = []
    for k, m in enumerate(r["modelos"]):
        cuerpo += [f"  \\addplot[dudamel/{estilos[k % 4]}] table[x=x, y={m['id']}, col sep=comma] {{\\dudameldir/datos/cobertura.csv}};",
                   f"  \\addlegendentry{{{_seguro(m['etiqueta'])}}}"]
    return _envolver([
        "Cobertura de lecturas esperadas: por ítem ambiguo revisado, la proporción de las lecturas del banco que la",
        "persona revisora marcó como presentes en la salida (cotejo a mano contra la referencia escrita, sin",
        "similitud de embeddings). Datos: datos/cobertura.csv.",
    ], ejes, cuerpo)


def _figura_parejas(r: dict) -> str:
    ejes, cuerpo = _barras(r, [("par", "barra4", "Parejas discriminadas")], archivo="modelos.csv",
                           xlabel="Proporción de parejas")
    return _envolver([
        "Parejas del mismo dominio (un ambiguo y su control inequívoco, por ejemplo «caja» / «caja registradora»):",
        "proporción en la que el modelo marcó el ambiguo y no el control, sobre las parejas con las dos respuestas.",
        "Barras de error: intervalo de Wilson al 95 %. Datos: datos/modelos.csv.",
    ], ejes, cuerpo)


def _figura_latencia(r: dict) -> str:
    n = len(r["modelos"])
    ejes = (f"\\begin{{axis}}[dudamel/eje, xbar, bar shift=0pt, bar width=7pt, width=0.66\\linewidth, height={_alto(n, 0.9)},\n"
            f"  xmin=0, ymin=0.4, ymax={n + 0.6}, ytick={{1,...,{n}}}, yticklabels={{{_nombres(r)}}}, ymajorgrids=false,\n"
            "  xlabel={Segundos por término}, unbounded coords=discard, enlarge x limits={rel=0.08, upper},\n"
            "  legend style={at={(0.5,1.03)}, anchor=south}, legend columns=2]")
    cuerpo = ["  \\addplot[dudamel/barra3] table[x=lat_mediana, y expr=\\thisrow{fila}+0.15, col sep=comma] {\\dudameldir/datos/modelos.csv};",
              "  \\addlegendentry{Mediana}",
              "  \\addplot[dudamel/barra2] table[x=lat_p90, y expr=\\thisrow{fila}-0.15, col sep=comma] {\\dudameldir/datos/modelos.csv};",
              "  \\addlegendentry{Percentil 90}"]
    return _envolver([
        "Latencia por modelo: mediana y percentil 90 del tiempo de una llamada al Clasificador (un término), sobre",
        "las respuestas válidas. Incluye el reintento cuando lo hubo. Datos: datos/modelos.csv.",
    ], ejes, cuerpo)


def _figura_modos(r: dict) -> str:
    filas = len(MODOS_FALLA) + 1
    nombres = ",".join("{" + tex(m["nombre"]) + "}" for m in MODOS_FALLA) + ",{Sin clasificar}"
    ejes = (f"\\begin{{axis}}[dudamel/eje, xbar, bar shift=0pt, bar width=4pt, width=0.5\\linewidth, height={0.9 * filas + 1.6:.1f}cm,\n"
            "  enlarge x limits={rel=0.08, upper},\n"
            f"  xmin=0, ymin=-0.6, ymax={filas - 0.4}, ytick={{0,...,{filas - 1}}}, yticklabels={{{nombres}}}, y dir=reverse,\n"
            "  ymajorgrids=false, xlabel={Falsos negativos}, legend style={at={(0.5,1.03)}, anchor=south}, legend columns=2]")
    estilos = ("barra1", "barra2", "barra4", "barra3")
    cuerpo = []
    paso = 0.6 / len(r["modelos"])
    for k, m in enumerate(r["modelos"]):
        dy = (k - (len(r["modelos"]) - 1) / 2) * paso  # el eje va de arriba abajo: la primera serie arriba
        cuerpo += [f"  \\addplot[dudamel/{estilos[k % 4]}] table[x={m['id']}, y expr=\\thisrow{{y}}{dy:+.3f}, col sep=comma] {{\\dudameldir/datos/modos.csv}};",
                   f"  \\addlegendentry{{{_seguro(m['etiqueta'])}}}"]
    return _envolver([
        "Modos de falla de los falsos negativos (ambiguos que el modelo marcó como unívocos o en los que falló),",
        "clasificados a mano con el catálogo del apéndice. Datos: datos/modos.csv.",
    ], ejes, cuerpo)


def _figura_subenumeracion(r: dict) -> str:
    marcas = ("*", "square*", "triangle*", "diamond*")
    colores = ("dudamelNaranja", "dudamelAzul", "dudamelAqua", "dudamelTinta")
    cuerpo = ["  \\addplot[dudamel/azar, forget plot, domain=1.5:3.5] {x};"]
    for k, m in enumerate(r["modelos"]):
        cuerpo += [(f"  \\addplot[only marks, mark={marcas[k % 4]}, mark size=1.8pt, {colores[k % 4]}, fill opacity=0.8]"
                   f" table[x=x, y=y, col sep=comma] {{\\dudameldir/datos/subenumeracion_{m['id']}.csv}};"),
                   f"  \\addlegendentry{{{_seguro(m['etiqueta'])}}}"]
    ejes = ("\\begin{axis}[dudamel/eje, width=0.62\\linewidth, height=0.5\\linewidth, xmin=1.4, xmax=3.6, ymin=0.4, ymax=4.6,\n"
            "  xtick={2,3}, ytick={1,2,3,4}, xlabel={Lecturas esperadas en el banco}, ylabel={Intenciones producidas},\n"
            "  legend style={at={(0.5,1.03)}, anchor=south}, legend columns=2]")
    return _envolver([
        "Subenumeración: por ítem ambiguo respondido, las lecturas esperadas del banco contra las intenciones que",
        "produjo el modelo (con un pequeño desplazamiento para que los puntos no se tapen). Bajo la diagonal punteada",
        "faltan lecturas: si la más alejada nunca se genera, el coseno mínimo entre paráfrasis sube y un término",
        "ambiguo puede quedar por encima del umbral. Datos: datos/subenumeracion_M*.csv.",
    ], ejes, cuerpo)


def _figura_estabilidad(e: dict) -> str:
    marcas = ("*", "square*", "triangle*", "diamond*")
    colores = ("dudamelNaranja", "dudamelAzul", "dudamelAqua", "dudamelTinta")
    corridas = [c["corrida"] for c in e["corridas"]]
    cuerpo = []
    for k, m in enumerate(e["modelos"]):
        cuerpo += [(f"  \\addplot[{colores[k % 4]}, mark={marcas[k % 4]}, line width=0.9pt] table[x=corrida, y=m{k + 1}, col sep=comma]"
                   " {\\dudameldir/datos/estabilidad.csv};"),
                   f"  \\addlegendentry{{{_seguro(m['etiqueta'])}}}",
                   *([(f"  \\addplot[{colores[k % 4]}, only marks, mark=-, forget plot, error bars/.cd, y dir=both, y explicit]"
                      f" table[x=x, y=medio, y error minus=menos, y error plus=mas, col sep=comma]"
                      f" {{\\dudameldir/datos/estabilidad_rango_m{k + 1}.csv}};")] if m["minimo"] is not None else [])]
    ejes = (f"\\begin{{axis}}[dudamel/eje, width=0.7\\linewidth, height=0.45\\linewidth, xmin={min(corridas) - 0.4},"
            f" xmax={max(corridas) + 0.6 + 0.25 * len(e['modelos'])},\n"
            f"  xtick={{{','.join(map(str, corridas))}}}, xlabel={{Corrida}}, ylabel={{Ambiguos detectados}}, enlarge y limits=0.15,\n"
            "  legend style={at={(0.5,1.03)}, anchor=south}, legend columns=2]")
    return _envolver([
        "Estabilidad: ambiguos detectados por cada modelo en N corridas idénticas (mismos modelos, términos, banco,",
        "prompt, temperatura y semilla). A la derecha, el rango (mínimo a máximo) de cada modelo.",
        "Datos: datos/estabilidad.csv y datos/estabilidad_rango_m*.csv.",
    ], ejes, cuerpo)


# ---------------------------------------------------------------- tablas

def _tabla(comentario: list[str], columnas: str, encabezado: str, filas: list[str], larga: bool = False) -> str:
    entorno = "longtable" if larga else "tabular"
    return "\n".join([*[f"% {c}" for c in comentario], f"\\begin{{{entorno}}}{{{columnas}}}", "\\toprule",
                      encabezado + " \\\\", "\\midrule", *(["\\endhead"] if larga else []),
                      *filas, "\\bottomrule", f"\\end{{{entorno}}}", ""])


def _tabla_modelos(r: dict) -> str:
    filas = []
    for m in r["modelos"]:
        lat = m["latencia_ms"]["mediana"]
        filas.append(" & ".join([_seguro(m["etiqueta"]), _ic(m["deteccion"]), _ic(m["falsas_alarmas"]),
                                 _ic(m["precision"]), str(m["errores"]), str(m["reintentos"]),
                                 "---" if lat is None else f"{lat / 1000:.1f}"]) + " \\\\")
    return _tabla([
        "Exhaustividad: ambiguos marcados como ambiguos sobre todos los ambiguos (un error cuenta como no detectado).",
        "Falsas alarmas: inequívocos marcados como ambiguos sobre los inequívocos que respondieron. Precisión: ambiguos",
        "sobre todo lo marcado. «---»: no se puede calcular (por ejemplo, un banco sin controles inequívocos).",
        "Entre corchetes, intervalo de Wilson al 95 %. Casos: exhaustividad sobre los ambiguos; falsas alarmas sobre",
        "los inequívocos que respondieron; precisión sobre lo marcado (VP + FP, ver la matriz de confusión).",
    ], "@{}llllrrr@{}", "Modelo & Exhaustividad & Falsas alarmas & Precisión & Errores & Reintentos & Latencia (s)", filas)


def _tabla_confusion(r: dict) -> str:
    filas = []
    for m in r["modelos"]:
        c, par = m["confusion"], m.get("parejas")
        parejas = "---" if not par else f"{par['discrimina']}/{par['n']}"
        fp, vn, err = (c["fp"], c["vn"], m["errores_inequivocos"]) if m["n_inequivocos"] else ("---", "---", "---")
        filas.append(f"{_seguro(m['etiqueta'])} & {c['vp']} & {c['fn']} & {fp} & {vn} & {err} & {parejas} \\\\")
    return _tabla([
        "Positivo = el modelo marcó el término como ambiguo. VP/FN sobre los ambiguos (un error es FN); FP/VN sobre",
        "los inequívocos que respondieron. Parejas: en cuántas parejas del mismo dominio marcó el ambiguo y no su control.",
    ], "@{}lrrrrrr@{}", "Modelo & VP & FN & FP & VN & Errores en inequívocos & Parejas", filas)


def _tabla_calidad(r: dict) -> str:
    filas = []
    for m in r["modelos"]:
        q, cob = m["calidad"], m["calidad"]["cobertura"]
        cobertura = "---" if cob["proporcion"] is None else f"{cob['cubiertas']}/{cob['esperadas']} = {cob['proporcion']:.2f}"
        filas.append(" & ".join([_seguro(m["etiqueta"]), f"{q['revisadas']}/{q['revisables']}",
                                 *[_ic(q["criterios"][c]) for c in CLAVES], cobertura]) + " \\\\")
    return _tabla([
        "Calidad de las salidas revisadas: proporción que cumple cada criterio de la rúbrica (una marca por salida;",
        "un criterio se cumple si lo cumplen todas sus intenciones), con su intervalo de Wilson al 95 %. Cobertura:",
        "lecturas esperadas cubiertas sobre esperadas, en los ítems ambiguos revisados. «---»: falta la revisión.",
    ], "@{}lrllll@{}", "Modelo & Revisadas & Fidelidad & Delimitación & Intención & Cobertura", filas)


def _tabla_clases(r: dict) -> str:
    filas = []
    for m in r["modelos"]:
        for clase, c in m["por_clase"].items():
            nota = "" if c["ambiguo"] else " (falsas alarmas)"
            filas.append(f"{_seguro(m['etiqueta'])} & {NOMBRE_CLASE.get(clase, tex(clase))} & {c['n']} & "
                         f"{_ic(c['deteccion'])}{nota} \\\\")
    return _tabla([
        "Por clase de término: proporción que el modelo marcó como ambiguos (en las clases ambiguas es la",
        "exhaustividad; en la inequívoca, las falsas alarmas). Con 20 a 30 casos por clase los intervalos se",
        "traslapan: una diferencia entre clases es una tendencia por confirmar, no un resultado.",
    ], "@{}llrl@{}", "Modelo & Clase & Términos & Marcó ambiguo", filas)


def _tabla_pares(r: dict) -> str:
    nombre = {m["id"]: _seguro(m["etiqueta"]) for m in r["modelos"]}
    filas = []
    for p in r["pares"]:
        d = p["deteccion"]
        filas.append(f"{nombre[p['a']]} & {nombre[p['b']]} & Detección (ambiguos) & {d['n']} & {d['solo_a']} & "
                     f"{d['solo_b']} & {_p(d['p'])} \\\\")
        for c in CLAVES:
            q = p["calidad"][c]
            filas.append(f" & & {NOMBRE_CRITERIO[c]} & {q['n']} & {q['solo_a']} & {q['solo_b']} & {_p(q['p'])} \\\\")
        filas.append(f" & & \\multicolumn{{5}}{{l}}{{\\footnotesize Excluidos de la calidad por distinto número de "
                     f"intenciones: {p['excluidos_por_intenciones']}}} \\\\")
    return _tabla([
        "Prueba exacta de McNemar entre cada par de modelos. Detección: sobre los ítems ambiguos («solo A» = A lo",
        "detectó y B no). Cada criterio de calidad: solo sobre los ítems revisados en los dos modelos y con el mismo",
        "número de intenciones (juzgar una lectura contra dos no es la misma cantidad); los excluidos se cuentan.",
        "«---»: sin pares discordantes no hay prueba.",
    ], "@{}lllrrrr@{}", "Modelo A & Modelo B & Medida & $n$ & Solo A & Solo B & $p$", filas)


def _tabla_subenumeracion(r: dict) -> str:
    filas = []
    for m in r["modelos"]:
        t = m["subenumeracion"]["con_tres"]
        filas.append(f"{_seguro(m['etiqueta'])} & {t['n']} & {t['marcados']} & {t['tres_o_mas']} \\\\")
    return _tabla([
        "Subenumeración en los ítems ambiguos con tres lecturas esperadas: cuántos marcó como ambiguos el modelo",
        "y en cuántos produjo tres intenciones o más.",
    ], "@{}lrrr@{}", "Modelo & Ítems con 3 lecturas & Marcados ambiguos & Con 3 intenciones o más", filas)


def _tabla_modos(r: dict) -> str:
    filas = []
    for m in r["modelos"]:
        fn = m["falsos_negativos"]
        for clave, cuantos in fn["por_modo"].items():
            if cuantos:
                filas.append(f"{_seguro(m['etiqueta'])} & {tex(NOMBRE_MODO[clave])} & {cuantos} \\\\")
        if fn["sin_clasificar"]:
            filas.append(f"{_seguro(m['etiqueta'])} & Sin clasificar & {fn['sin_clasificar']} \\\\")
    if not filas:
        filas = ["\\multicolumn{3}{@{}l}{--- (no hay falsos negativos)} \\\\"]
    return _tabla(["Modos de falla de los falsos negativos, clasificados a mano con el catálogo del apéndice."],
                  "@{}llr@{}", "Modelo & Modo & Falsos negativos", filas)


def _tabla_estabilidad(e: dict) -> str:
    filas = []
    for m in e["modelos"]:
        corridas = ", ".join("---" if d is None else str(d) for d in m["detecciones"])
        rango = "---" if m["rango"] is None else f"{m['minimo']}--{m['maximo']} ({m['rango']})"
        filas.append(f"{_seguro(m['etiqueta'])} & {m['n_ambiguos']} & {corridas} & {rango} \\\\")
    return _tabla([
        f"Estabilidad en {len(e['corridas'])} corridas idénticas: ambiguos detectados en cada corrida y su rango.",
        "«---»: la corrida no terminó, o hay menos de dos corridas terminadas.",
    ], "@{}lrll@{}", "Modelo & Ambiguos & Detectados por corrida & Rango", filas)


def _tabla_legado(r: dict) -> str:
    leg = r["aprobacion_legado"]
    nombre = {m["id"]: _seguro(m["etiqueta"]) for m in r["modelos"]}
    filas = [f"{nombre[k]} & {_ic(v)} \\\\" for k, v in leg["por_modelo"].items()]
    return _tabla([
        "Aprobación con el criterio viejo (v2.3): un solo ✓/✗ por salida que mezclaba si detectó la ambigüedad con",
        "si lo escrito estaba bien. Se conserva tal como se guardó y NO se traduce a los criterios nuevos.",
    ], "@{}ll@{}", "Modelo & Aprobación (criterio v2.3)", filas)


def _tabla_banco(prueba: dict) -> str:
    terminos = {t["id"]: t for t in banco_de(prueba)["terminos"]}
    filas = [f"{i} & {tex(terminos[i]['termino'])} & {NOMBRE_CLASE.get(terminos[i]['clase'], tex(terminos[i]['clase']))} & "
             f"{tex(terminos[i]['dominio'])} & {tex('; '.join(terminos[i]['lecturas']))} \\\\" for i in prueba["items"]]
    return _tabla(["Los términos del banco que usó la prueba, con las lecturas esperadas (la referencia de la revisión)."],
                  "@{}lllp{0.22\\linewidth}p{0.4\\linewidth}@{}", "ID & Término & Clase & Dominio & Lecturas esperadas",
                  filas, larga=True)


def _respuesta(r: dict | None) -> tuple[str, str]:
    if r is None:
        return "---", "sin correr"
    if not r["ok"]:
        return "error", (r.get("error") or "")[:120]
    return ("sí" if r["ambiguo"] else "no"), " / ".join(i["significado"] for i in r["intenciones"])


def _tabla_respuestas(prueba: dict, revision: dict | None) -> str:
    terminos = {t["id"]: t for t in banco_de(prueba)["terminos"]}
    marcas = (revision or {}).get("marcas", {})
    si_no = {True: "sí", False: "no"}
    filas = []
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        for i in prueba["items"]:
            amb, texto = _respuesta(res.get(i))
            mk = marcas.get(m["id"], {}).get(i)
            calidad = "/".join(si_no[mk[c]] for c in CLAVES) if mk else "---"
            cob = (f"{len(mk['cobertura'])}/{len(terminos[i]['lecturas'])}" if mk and es_ambiguo(terminos[i]) else "---")
            filas.append(f"{i} & {tex(terminos[i]['termino'])} & {_seguro(etiqueta_modelo(m))} & {amb} & {_seguro(texto)} & "
                         f"{calidad} & {cob} \\\\")
    return _tabla(["Qué respondió cada modelo (los significados de sus intenciones) y la revisión de calidad",
                   "(fidelidad/delimitación/intención) con la cobertura de lecturas esperadas."],
                  "@{}llp{0.15\\linewidth}lp{0.34\\linewidth}ll@{}",
                  "ID & Término & Modelo & ¿Ambiguo? & Significados & F/D/I & Cob.", filas, larga=True)


def _datos_respuestas(prueba: dict, revision: dict | None) -> str:
    terminos = {t["id"]: t for t in banco_de(prueba)["terminos"]}
    marcas = (revision or {}).get("marcas", {})
    filas = []
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        for i in prueba["items"]:
            r = res.get(i)
            mk = marcas.get(m["id"], {}).get(i) or {}
            filas.append([i, terminos[i]["termino"], terminos[i]["clase"], int(es_ambiguo(terminos[i])),
                          len(terminos[i]["lecturas"]), m["proveedor"], m["modelo"],
                          "" if r is None else int(r["ok"]), "" if not r or not r["ok"] else int(r["ambiguo"]),
                          "" if not r or not r["ok"] else len(r["intenciones"]), "" if not r else r.get("ms") or "",
                          "" if not r else r.get("intentos", ""),
                          *["" if not mk else int(mk[c]) for c in CLAVES],
                          "" if not mk else len(mk["cobertura"]), mk.get("nota") or ""])
    return _csv(filas, ["id", "termino", "clase", "ambiguo_esperado", "lecturas_esperadas", "proveedor", "modelo",
                        "respondio", "ambiguo", "intenciones", "ms", "intentos", *CLAVES, "lecturas_cubiertas", "nota"])


def _apendice_rubrica() -> str:
    partes = ["% Rúbrica de la revisión humana (generada desde backend/app/calibracion/rubrica.py).",
              "\\subsection*{Rúbrica de la revisión de calidad}", tex(REGLA_AGREGADO), "", "\\begin{description}"]
    for c in CRITERIOS:
        partes += [f"  \\item[{tex(c['nombre'])}] {tex(c['oracion'])}",
                   f"    \\emph{{Pasa:}} {tex(c['pasa'])} \\emph{{No pasa:}} {tex(c['no_pasa'])}"]
    partes += [f"  \\item[{tex(COBERTURA['nombre'])}] {tex(COBERTURA['oracion'])}",
               f"    \\emph{{Pasa:}} {tex(COBERTURA['pasa'])} \\emph{{No pasa:}} {tex(COBERTURA['no_pasa'])}",
               "\\end{description}", "\\subsection*{Modos de falla de los falsos negativos}", "\\begin{description}"]
    partes += [f"  \\item[{tex(m['nombre'])}] {tex(m['descripcion'])}" for m in MODOS_FALLA]
    partes += ["\\end{description}", ""]
    return "\n".join(partes)


# ---------------------------------------------------------------- paquete

def _main(prueba: dict, r: dict, revision: dict | None, figuras: list[tuple[str, str]], tablas: list[tuple[str, str]],
          omitidas: list[str]) -> str:
    b = prueba["banco"]
    partes = [
        *preambulo(),
        "\\begin{document}",
        f"\\section*{{Prueba de modelos --- {tex(codigo_de(prueba))}}}",
        (f"Fecha: {tex(prueba['creado'])}. Versión de Dudamel: {tex(prueba.get('version_app'))}. "
         f"Banco: {tex(b['nombre'])} {tex(b['version'])} (huella {tex(b['huella'][:12])}), {len(prueba['items'])} términos. "
         f"Prompt: {tex(prueba['configuracion']['prompt'])}; temperatura {prueba['configuracion']['temperatura']}; "
         f"semilla {prueba['configuracion'].get('semilla')}. uid: \\texttt{{{tex(prueba.get('uid') or '---')}}}. "
         f"Revisión de calidad: {tex((revision or {}).get('revisor') or '---')}"
         f"{' (a ciegas)' if (revision or {}).get('a_ciegas') else ''}."),
        "",
    ]
    if r["avisos"] or omitidas:
        partes += ["\\paragraph{Avisos.}", "\\begin{itemize}", *[f"  \\item {tex(a)}" for a in r["avisos"]],
                   *[f"  \\item Figura omitida: {tex(o)}" for o in omitidas], "\\end{itemize}", ""]
    for nombre, pie in figuras:
        partes += ["\\begin{figure}[htbp]", "\\centering", f"\\input{{\\dudameldir/figuras/{nombre}}}",
                   f"\\caption{{{pie}}}", f"\\label{{fig:dudamel-{nombre}}}", "\\end{figure}", ""]
    for nombre, pie in tablas:
        partes += ["\\begin{table}[htbp]", "\\centering", "\\small", f"\\caption{{{pie}}}",
                   f"\\label{{tab:dudamel-{nombre}}}", f"\\input{{\\dudameldir/tablas/{nombre}}}", "\\end{table}", ""]
    partes += ["\\clearpage", "\\subsection*{Banco de términos}", "{\\small\\input{\\dudameldir/tablas/banco}}",
               "\\subsection*{Respuestas}", "{\\small\\input{\\dudameldir/tablas/respuestas}}",
               "\\appendix", "\\input{\\dudameldir/apendice/rubrica}", "\\end{document}", ""]
    return "\n".join(partes)


LEEME = """# Paquete de la prueba de modelos {codigo} para Overleaf

1. En Overleaf: **New Project → Upload Project** y sube este .zip. `main.tex` compila tal cual con
   pdfLaTeX o con XeLaTeX.
2. Para usarlo dentro de tu tesis, sube la carpeta (por ejemplo como `dudamel-{id}/`) y en el
   preámbulo pon:

       \\newcommand{{\\dudameldir}}{{dudamel-{id}}}
       \\input{{dudamel-{id}/estilo-dudamel}}

   y donde quieras cada pieza: `\\input{{dudamel-{id}/figuras/modelos}}`,
   `\\input{{dudamel-{id}/tablas/calidad}}`, etc. `tablas/banco.tex` y `tablas/respuestas.tex`
   usan `longtable` y van fuera de un `table`. `apendice/rubrica.tex` (y `rubrica.md`) es la rúbrica
   que se le entrega a un segundo anotador.
3. `prueba.json` es la prueba completa: modelos, configuración, banco (con su huella), cada respuesta,
   las revisiones y el resumen. Cítala por su código ({codigo}) y su uid ({uid}).

Cada figura lee sus números de `datos/*.csv`. Exhaustividad = ambiguos marcados / ambiguos (un error
cuenta como no detectado). Falsas alarmas = inequívocos marcados / inequívocos que respondieron.
Precisión = ambiguos / todo lo marcado. Calidad = salidas revisadas que cumplen cada criterio. Los
intervalos son de Wilson al 95 %; las comparaciones entre modelos, McNemar exacta.
"""


def paquete_overleaf(prueba: dict, r: dict, legado: dict | None = None, revision: dict | None = None,
                     estab: dict | None = None) -> bytes:
    """El .zip de una prueba: `r` es su `resumen`; `legado` y `revision`, sus revisiones (v2.3 y de
    calidad); `estab`, la estabilidad de su serie si tiene más de una corrida."""
    modelos = r["modelos"]
    aciertos, fallos = _datos_confusion(r)
    archivos = {
        "LEEME.md": LEEME.format(id=prueba["prueba_id"], codigo=codigo_de(prueba), uid=prueba.get("uid") or "sin uid"),
        "estilo-dudamel.tex": ESTILO,
        "rubrica.md": markdown(),
        "apendice/rubrica.tex": _apendice_rubrica(),
        "prueba.json": json.dumps({**prueba, "codigo": codigo_de(prueba), "revisiones": legado, "revision_calidad": revision,
                                   "estabilidad": estab, "resumen": r}, ensure_ascii=False, indent=1),
        "datos/modelos.csv": _datos_modelos(r),
        "datos/confusion_aciertos.csv": aciertos,
        "datos/confusion_fallos.csv": fallos,
        "datos/respuestas.csv": _datos_respuestas(prueba, revision),
        "datos/modos.csv": _datos_modos(r),
        **_datos_subenumeracion(r),
        "figuras/modelos.tex": _figura_modelos(r),
        "figuras/latencia.tex": _figura_latencia(r),
        "tablas/modelos.tex": _tabla_modelos(r),
        "tablas/confusion.tex": _tabla_confusion(r),
        "tablas/calidad.tex": _tabla_calidad(r),
        "tablas/clases.tex": _tabla_clases(r),
        "tablas/subenumeracion.tex": _tabla_subenumeracion(r),
        "tablas/modos.tex": _tabla_modos(r),
        "tablas/banco.tex": _tabla_banco(prueba),
        "tablas/respuestas.tex": _tabla_respuestas(prueba, revision),
    }
    figuras = [("modelos", "Exhaustividad, precisión y falsas alarmas por modelo (Wilson al 95~\\%)."),
               ("confusion", "Matriz de confusión por modelo.")]
    archivos["figuras/confusion.tex"] = _figura_confusion(r)
    omitidas = []
    if any(m["calidad"]["revisadas"] for m in modelos):
        archivos["figuras/calidad.tex"] = _figura_calidad(r)
        figuras.append(("calidad", "Calidad por criterio y modelo (Wilson al 95~\\%)."))
    else:
        omitidas.append("calidad por criterio (falta la revisión de calidad)")
    datos_cob, rotulos = _datos_cobertura(r)
    if rotulos:
        archivos["datos/cobertura.csv"] = datos_cob
        archivos["figuras/cobertura.tex"] = _figura_cobertura(r, rotulos)
        figuras.append(("cobertura", "Cobertura de lecturas esperadas por ítem ambiguo revisado."))
    else:
        omitidas.append("cobertura de lecturas esperadas (falta revisar ítems ambiguos)")
    if any(m.get("parejas") and m["parejas"]["n"] for m in modelos):
        archivos["figuras/parejas.tex"] = _figura_parejas(r)
        figuras.append(("parejas", "Parejas discriminadas: ambiguo marcado y su control no (Wilson al 95~\\%)."))
    else:
        omitidas.append("parejas discriminadas (el banco no tiene controles en pareja o no hay respuestas de los dos)")
    figuras.append(("latencia", "Latencia por modelo."))
    if any(sum(m["falsos_negativos"]["por_modo"].values()) + m["falsos_negativos"]["sin_clasificar"] for m in modelos):
        archivos["figuras/modos.tex"] = _figura_modos(r)
        figuras.append(("modos", "Modos de falla de los falsos negativos."))
    else:
        omitidas.append("modos de falla (no hay falsos negativos)")
    if any(p["ok"] for m in modelos for p in m["subenumeracion"]["por_item"]):
        archivos["figuras/subenumeracion.tex"] = _figura_subenumeracion(r)
        figuras.append(("subenumeracion", "Lecturas esperadas contra intenciones producidas."))
    tablas = [("modelos", "Detección por modelo."), ("confusion", "Matriz de confusión por modelo."),
              ("calidad", "Calidad y cobertura por modelo."), ("clases", "Por clase de término."),
              ("subenumeracion", "Subenumeración."), ("modos", "Modos de falla de los falsos negativos.")]
    if r["pares"]:
        archivos["tablas/pares.tex"] = _tabla_pares(r)
        tablas.append(("pares", "Comparación por pares (McNemar exacta)."))
    if r.get("aprobacion_legado"):
        archivos["tablas/aprobacion_legado.tex"] = _tabla_legado(r)
        tablas.append(("aprobacion_legado", "Aprobación con el criterio viejo (v2.3), sin traducir."))
    if estab and any(m["rango"] is not None for m in estab["modelos"]):
        archivos.update({**_datos_estabilidad(estab), "figuras/estabilidad.tex": _figura_estabilidad(estab),
                         "tablas/estabilidad.tex": _tabla_estabilidad(estab)})
        figuras.append(("estabilidad", "Detección por corrida en corridas idénticas, con su rango."))
        tablas.append(("estabilidad", "Estabilidad entre corridas idénticas."))
    archivos["main.tex"] = _main(prueba, r, revision, figuras, tablas, omitidas)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return salida.getvalue()
