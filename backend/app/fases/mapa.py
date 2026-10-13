"""Fase 2: el mapa conceptual con propósito, desde el LEL validado (ADR 0024).

El Modelador propone la pregunta de enfoque (el propósito), los conceptos —cada uno con
el símbolo del LEL que representa— y las proposiciones «concepto — enlace → concepto».
El código verifica las referencias (se reintenta una vez si un id no existe), liga cada
concepto a su símbolo del LEL, quita repetidos, lazos y conceptos sueltos, y numera las
relaciones. La persona experta lo edita en una interfaz interactiva (mover, renombrar,
unir, quitar, agregar) y valida cada componente; cada cambio queda en el historial.
"""
from __future__ import annotations

from app.models import MapaEditable, SalidaMapaProposito

from .claves import clave as clave_de
from .documento import DocumentosDeFase, ahora
from .memoria import acuerdos_en_texto
from .progreso import Avisar, paso
from .textos import Simbolos, hechos, hechos_en_texto, lel_en_texto, validadas


def verificar_mapa(s: SalidaMapaProposito) -> None:
    ids = [c.id for c in s.conceptos]
    if len(ids) != len(set(ids)):
        raise ValueError(f"ids de concepto repetidos: {ids}")
    if s.central not in ids:
        raise ValueError(f"«central» debe ser el id de un concepto de la lista {ids}")
    malas = [f"{r.origen}→{r.destino}" for r in s.relaciones if r.origen not in ids or r.destino not in ids]
    if malas:
        raise ValueError(f"relaciones con conceptos que no existen: {malas}; usa solo los ids {ids}")


def armar_mapa(s: SalidaMapaProposito, simbolos: Simbolos) -> tuple[dict, list[str]]:
    """Del mapa del Modelador al mapa editable: símbolos del LEL, sin repetidos, lazos ni sueltos."""
    avisos = []
    conceptos = []
    for c in s.conceptos:
        simbolo = simbolos(c.simbolo) or simbolos(c.etiqueta)
        if simbolo is None:
            avisos.append(f"«{c.etiqueta}» no corresponde a ningún término validado del LEL.")
        conceptos.append({"id": c.id, "etiqueta": c.etiqueta, "simbolo": simbolo, "x": None, "y": None,
                          "validado": False, "origen": "agentes"})
    relaciones, vistas = [], set()
    for r in s.relaciones:
        llave = (r.origen, " ".join(r.enlace.lower().split()), r.destino)
        if r.origen == r.destino or llave in vistas:
            continue
        vistas.add(llave)
        relaciones.append({"id": f"R{len(relaciones) + 1}", "origen": r.origen, "enlace": r.enlace,
                           "destino": r.destino, "validado": False, "autor": "agentes"})
    usados = {r["origen"] for r in relaciones} | {r["destino"] for r in relaciones} | {s.central}
    sueltos = [c["etiqueta"] for c in conceptos if c["id"] not in usados]
    if sueltos:
        avisos.append(f"Se quitaron conceptos sin relaciones: {', '.join(sueltos)}.")
    conceptos = [c for c in conceptos if c["id"] in usados]
    contenido = MapaEditable.model_validate({"proposito": s.proposito, "central": s.central, "conceptos": conceptos,
                                             "relaciones": relaciones}).model_dump(mode="json")
    return contenido, avisos


def generar(deps, proyecto, entradas: list[dict], acuerdos: list[dict], entrevistas: list[dict],
            huella_origen: str, avisar: Avisar) -> dict:
    s = deps.settings
    lel = validadas(entradas)
    if not lel:
        raise ValueError("El mapa se arma con el LEL validado y todavía no hay términos validados.")
    avisar(paso("lel", "Leyendo el léxico validado", "ok", f"{len(lel)} términos · {len(acuerdos)} acuerdos"))
    avisar(paso("modelador", "El Modelador arma el mapa y su propósito"))
    r = deps.modelador.mapa_con_proposito(
        verificar=verificar_mapa, proyecto=proyecto.nombre, contexto=(proyecto.contexto or "").strip()
        or "(el proyecto no tiene contexto general)", acuerdos=acuerdos_en_texto(acuerdos), lel=lel_en_texto(entradas),
        necesidades=hechos_en_texto(hechos(entrevistas), campos=("objetivos", "necesidades"), limite=25),
        max_conceptos=s.mapa_max_conceptos, max_relaciones=s.mapa_max_relaciones)
    avisar(paso("modelador", "El Modelador armó el mapa", "ok",
                f"{len(r.valor.conceptos)} conceptos · {len(r.valor.relaciones)} proposiciones"
                + (" (con un reintento)" if r.hubo_reintento else "")))
    avisar(paso("revision", "Revisando que cada concepto venga del LEL"))
    contenido, avisos = armar_mapa(r.valor, Simbolos(entradas))
    avisar(paso("revision", "Revisión en código", "aviso" if avisos else "ok",
                f"{len(avisos)} aviso(s)" if avisos else "todo se rastrea al LEL"))
    fecha = ahora()
    doc = {"proyecto_id": proyecto.proyecto_id, "fase": "mapa", "contenido": contenido, "huella_origen": huella_origen,
           "avisos": avisos, "modelo": r.modelo, "prompt_version": r.prompt_version, "intentos": len(r.intentos),
           "generado": fecha, "actualizado": fecha,
           "historial": [{"fecha": fecha, "accion": "generar", "autor": "agentes",
                          "detalle": f"{len(contenido['conceptos'])} conceptos, {len(contenido['relaciones'])} relaciones"}]}
    return DocumentosDeFase(deps.repo).guardar("mapa", doc)


def cambios_del_mapa(antes: dict, despues: dict) -> list[str]:
    """Lo que cambió la persona, en palabras (para el historial)."""
    cambios = []
    if antes["proposito"] != despues["proposito"]:
        cambios.append("cambió el propósito")
    a = {c["id"]: c for c in antes["conceptos"]}
    d = {c["id"]: c for c in despues["conceptos"]}
    cambios += [f"agregó «{d[i]['etiqueta']}»" for i in d.keys() - a.keys()]
    cambios += [f"quitó «{a[i]['etiqueta']}»" for i in a.keys() - d.keys()]
    cambios += [f"renombró «{a[i]['etiqueta']}» como «{d[i]['etiqueta']}»" for i in a.keys() & d.keys()
                if a[i]["etiqueta"] != d[i]["etiqueta"]]
    ra = {r["id"]: r for r in antes["relaciones"]}
    rd = {r["id"]: r for r in despues["relaciones"]}
    et = {**{i: c["etiqueta"] for i, c in a.items()}, **{i: c["etiqueta"] for i, c in d.items()}}

    def prop(r: dict) -> str:
        return f"«{et.get(r['origen'], '?')} — {r['enlace']} → {et.get(r['destino'], '?')}»"

    cambios += [f"unió {prop(rd[i])}" for i in rd.keys() - ra.keys()]
    cambios += [f"quitó {prop(ra[i])}" for i in ra.keys() - rd.keys()]
    cambios += [f"cambió {prop(ra[i])} por {prop(rd[i])}" for i in ra.keys() & rd.keys()
                if (ra[i]["origen"], ra[i]["enlace"], ra[i]["destino"]) != (rd[i]["origen"], rd[i]["enlace"], rd[i]["destino"])]
    validados = sum(1 for i in a.keys() & d.keys() if d[i]["validado"] and not a[i]["validado"]) \
        + sum(1 for i in ra.keys() & rd.keys() if rd[i]["validado"] and not ra[i]["validado"]) \
        + (1 if despues.get("proposito_validado") and not antes.get("proposito_validado") else 0)
    if validados:
        cambios.append(f"validó {validados} componente(s)")
    if a.keys() & d.keys() and any((a[i]["x"], a[i]["y"]) != (d[i]["x"], d[i]["y"]) for i in a.keys() & d.keys()) \
            and not cambios:
        cambios.append("acomodó el mapa")
    return cambios


def editar(repo, previo: dict, nuevo: MapaEditable, entradas: list[dict]) -> dict:
    """Guarda el mapa que editó la persona. Los conceptos nuevos se ligan a su símbolo del LEL si lo tienen."""
    simbolos = Simbolos(entradas)
    contenido = nuevo.model_dump(mode="json")
    for c in contenido["conceptos"]:
        if c["simbolo"] is not None and simbolos(c["simbolo"]) is None:
            c["simbolo"] = None
        if c["simbolo"] is None:
            c["simbolo"] = simbolos(c["etiqueta"])
    cambios = cambios_del_mapa(previo["contenido"], contenido)
    fecha = ahora()
    previo["contenido"] = contenido
    previo["actualizado"] = fecha
    if cambios:
        previo["historial"].append({"fecha": fecha, "accion": "editar", "autor": "persona", "cambios": cambios})
    return DocumentosDeFase(repo).guardar("mapa", previo)


def a_mermaid(contenido: dict) -> str:
    """El mapa como Mermaid (para exportarlo y para la tesis)."""
    def seguro(t: str) -> str:
        return t.replace('"', "'")

    lineas = ["flowchart TD", f"  %% {seguro(contenido['proposito'])}"]
    for c in contenido["conceptos"]:
        forma = f'(["{seguro(c["etiqueta"])}"])' if c["id"] == contenido["central"] else f'["{seguro(c["etiqueta"])}"]'
        lineas.append(f"  {c['id']}{forma}")
    for r in contenido["relaciones"]:
        lineas.append(f'  {r["origen"]} -- "{seguro(r["enlace"])}" --> {r["destino"]}')
    return "\n".join(lineas) + "\n"


def clave_concepto(c: dict) -> str:
    return clave_de(c.get("simbolo") or c["etiqueta"])
