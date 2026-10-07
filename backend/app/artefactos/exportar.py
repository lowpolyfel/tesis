"""Exportaciones de texto del Big Picture (ADR 0011): Mermaid y PlantUML.

Deterministas: el mismo grafo produce el mismo texto. Los ids se sanean a
`[A-Za-z0-9_]` y las etiquetas van siempre entre comillas, con las comillas,
`#`, `<`, `>` y acentos graves escapados como entidades de Mermaid; acentos,
corchetes y paréntesis van bien entre comillas. Dibujarlos queda fuera del
prototipo (CONTEXTO §7): el texto se pega en cualquier visor.
"""
from __future__ import annotations

import re
import unicodedata

from .simbolos import Simbolo
from .terminos import separar_accion

# Formas al estilo i*: actor círculo, meta redondeada, meta blanda «nube»
# (estadio), tarea hexágono, recurso rectángulo.
_FORMAS = {
    "requisito": ('[/"', '"/]'), "actor": ('(("', '"))'), "meta": ('("', '")'), "meta_blanda": ('(["', '"])'),
    "tarea": ('{{"', '"}}'), "recurso": ('["', '"]'), "simbolo": ('[["', '"]]'),
}
_ESTILOS = {
    "requisito": "fill:#ffffff,stroke:#555555,color:#1b1712",
    "actor": "fill:#eef0ff,stroke:#5b5bd6,color:#1b1712",
    "meta": "fill:#ecfbf3,stroke:#0f9a6a,color:#1b1712",
    "meta_blanda": "fill:#fff6e5,stroke:#d38b00,color:#1b1712,stroke-dasharray:4 3",
    "tarea": "fill:#e8f4ff,stroke:#2a7bd6,color:#1b1712",
    "recurso": "fill:#f3f0ea,stroke:#8a7f6a,color:#1b1712",
    "simbolo": "fill:#fdeef4,stroke:#c2417a,color:#1b1712",
}
_FLECHA = {"relacionado_con": "-.->"}
# palabras de la sintaxis de Mermaid que no pueden ser id de un nodo
_RESERVADAS = {"end", "graph", "flowchart", "subgraph", "direction", "style", "linkstyle", "class", "classdef",
               "click", "call", "href", "default", "interpolate", "acctitle", "accdescr"}
_COLORES_PLANTUML = {"actor": ("#EEF0FF", "#5B5BD6"), "sujeto": ("#EEF0FF", "#5B5BD6"),
                     "objeto": ("#ECFBF3", "#0F9A6A"), "verbo": ("#E8F4FF", "#2A7BD6"),
                     "estado": ("#FFF6E5", "#D38B00")}


def ids_saneados(ids: list[str]) -> dict[str, str]:
    """id del grafo → id válido en Mermaid y PlantUML, sin colisiones."""
    salida, usados = {}, set()
    for i in ids:
        base = re.sub(r"[^A-Za-z0-9]+", "_", i).strip("_")
        base = base if base[:1].isalpha() else f"n_{base}"
        base = f"{base}_" if base.lower() in _RESERVADAS else base
        nuevo, n = base, 2
        while nuevo in usados:
            nuevo, n = f"{base}_{n}", n + 1
        usados.add(nuevo)
        salida[i] = nuevo
    return salida


def _una_linea(texto: str) -> str:
    """Espacios colapsados y sin caracteres de control (un NUL que venga de un
    PDF no es válido en el SVG que dibuja el visor)."""
    return " ".join("".join(c for c in str(texto) if unicodedata.category(c) != "Cc" or c.isspace()).split())


def texto_mermaid(texto: str) -> str:
    """Una línea, sin caracteres que rompan una etiqueta entre comillas."""
    t = _una_linea(texto)
    t = t.replace("#", "#35;").replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;").replace("`", "#96;")
    return t or " "


def _etiqueta(n: dict) -> str:
    if n["tipo"] == "requisito":
        return f"{n['etiqueta']}: {n['detalle']}" if n["detalle"] else n["etiqueta"]
    if n["tipo"] == "simbolo":
        return f"{n['etiqueta']} ({n['subtipo']})" if n["subtipo"] else n["etiqueta"]
    if n["tipo"] == "actor":
        return n["etiqueta"]
    return f"{n['id']}: {n['etiqueta']}"


def a_mermaid(nodos: list[dict], aristas: list[dict]) -> str:
    ids = ids_saneados([n["id"] for n in nodos])
    lineas = ["flowchart LR"]
    for n in nodos:
        abre, cierra = _FORMAS[n["tipo"]]
        lineas.append(f"    {ids[n['id']]}{abre}{texto_mermaid(_etiqueta(n))}{cierra}")
    for a in aristas:
        lineas.append(f"    {ids[a['origen']]} {_FLECHA.get(a['relacion'], '-->')}|{a['relacion']}| {ids[a['destino']]}")
    for tipo, estilo in _ESTILOS.items():
        lineas.append(f"    classDef {tipo} {estilo}")
    for tipo in _ESTILOS:
        del_tipo = [ids[n["id"]] for n in nodos if n["tipo"] == tipo]
        if del_tipo:
            lineas.append(f"    class {','.join(del_tipo)} {tipo}")
    return "\n".join(lineas) + "\n"


# ---------------------------------------------------------------- PlantUML

def texto_plantuml(texto: str) -> str:
    """Una línea sin lo que PlantUML interpreta: comillas, llaves, `<`, `>`, la
    barra invertida (al final de una línea la une con la siguiente; `\\n` es un salto)
    y `/'`, que abre un comentario y borra el texto hasta un `'/` de la misma línea."""
    t = _una_linea(texto)
    return (t.replace('"', "'").replace("{", "(").replace("}", ")").replace("<", "‹").replace(">", "›")
            .replace("\\", "∖").replace("/'", "/’") or " ")


def a_plantuml(nodos: list[dict], aristas: list[dict], simbolos: list[Simbolo]) -> str:
    """Diagrama de clases: una clase por símbolo del LEL (noción e impacto como
    atributos), una por actor que no es ya un sujeto del LEL, las relaciones
    entre símbolos y lo que cada actor hace con cada símbolo a través de sus metas."""
    ids = ids_saneados([n["id"] for n in nodos])
    por_id = {n["id"]: n for n in nodos}
    # un actor que coincide con un sujeto del LEL se dibuja como esa clase
    alias = {a["origen"]: a["destino"] for a in aristas
             if a["relacion"] == "relacionado_con" and por_id[a["origen"]]["tipo"] == "actor"}

    lineas = ["@startuml", "title Big Picture: símbolos del LEL y actores", "left to right direction",
              "hide empty members", "skinparam shadowing false", "skinparam class {"]
    for estereotipo, (fondo, borde) in _COLORES_PLANTUML.items():
        lineas += [f"  BackgroundColor<<{estereotipo}>> {fondo}", f"  BorderColor<<{estereotipo}>> {borde}"]
    lineas += ["}", ""]

    for s in simbolos:
        atributos = [f"{{field}} noción: {texto_plantuml(x)}" for e in s.entradas for x in e.nocion]
        atributos += [f"{{field}} impacto: {texto_plantuml(x)}" for e in s.entradas for x in e.impacto]
        lineas.append(f'class "{texto_plantuml(s.simbolo)}" as {ids[s.id]} <<{s.subtipo}>> {{')
        lineas += [f"  {a}" for a in dict.fromkeys(atributos)]
        lineas.append("}")
    for n in nodos:
        if n["tipo"] == "actor" and n["id"] not in alias:
            lineas.append(f'class "{texto_plantuml(n["etiqueta"])}" as {ids[n["id"]]} <<actor>>')
    if not simbolos and not any(n["tipo"] == "actor" for n in nodos):
        lineas.append('note "Sin símbolos del LEL ni actores todavía" as N1')
    lineas.append("")

    for a in aristas:
        if a["relacion"] == "relacionado_con" and a["origen"] not in alias:
            lineas.append(f"{ids[a['origen']]} --> {ids[a['destino']]} : relacionado con")

    # actor → símbolo: actor persigue una meta que usa el símbolo; etiqueta = verbo de la meta
    usa: dict[str, list[str]] = {}
    for a in aristas:
        if a["relacion"] == "usa":
            usa.setdefault(a["origen"], []).append(a["destino"])
    relaciones: dict[tuple[str, str, str], list[str]] = {}
    for a in aristas:
        if a["relacion"] != "persigue":
            continue
        meta = por_id[a["destino"]]
        verbo = separar_accion(meta["etiqueta"])[0] or meta["tipo"]
        de = alias.get(a["origen"], a["origen"])
        for simbolo in usa.get(meta["id"], []):
            if simbolo != de:
                relaciones.setdefault((de, simbolo, verbo), []).append(meta["id"])
    for (de, hacia, verbo), metas in relaciones.items():
        lineas.append(f"{ids[de]} --> {ids[hacia]} : {texto_plantuml(verbo)} ({', '.join(metas)})")
    lineas.append("@enduml")
    return "\n".join(lineas) + "\n"
