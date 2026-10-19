"""Revisión de calidad fuera del sistema (ADR 0030): se exporta un archivo a ciegas, lo contesta una
persona o una IA, y se importan las respuestas. Funciones puras sobre documentos ya leídos: nada
aquí llama a un LLM; quien contesta el archivo lo hace por su cuenta.

**El archivo** (Markdown para pegarlo en un chat, o JSON) lleva la rúbrica con sus casos frecuentes,
cada salida revisable con su término, cita, lecturas esperadas e intenciones, los falsos negativos
por clasificar y una plantilla JSON para contestar. No trae proveedor ni modelo: cada salida tiene un
id opaco, ``S015`` = la salida 15 del orden barajado de la revisión (el mismo número que la pantalla),
y cada falso negativo, ``F07``, en un orden barajado aparte. El archivo trae la semilla y una huella
del orden: al importar, el servidor rehace el orden y rechaza el archivo si la huella no coincide
(la prueba cambió o el archivo es de otra revisión).

**Al importar**, cada marca guarda su origen (``{tipo: persona|ia, quien, importacion}``). Por
omisión no se pisa lo ya marcado en la pantalla; lo que se conserva sirve para medir el acuerdo
entre quien contestó el archivo y la revisión que ya había (kappa por criterio). Así un juicio de
IA queda validado contra la revisión humana en las salidas que las dos vieron, y el resumen avisa
cuántas marcas vienen de una IA.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import secrets

from . import calidad as cal
from .anotaciones import kappa
from .rubrica import (
    CLAVES,
    CLAVES_MODOS,
    COBERTURA,
    CRITERIOS,
    MODOS_FALLA,
    REGLA_AGREGADO,
    aclaraciones_md,
)

FORMATO = "dudamel-revision-v1"
TIPOS = ("persona", "ia")


def _huella(pares: list[tuple[str, str]]) -> str:
    return hashlib.sha256(json.dumps(pares, ensure_ascii=False).encode()).hexdigest()[:16]


def _orden(prueba: dict, doc: dict | None, semilla: int | None) -> tuple[list[dict], int]:
    """El orden de la revisión: el guardado si ya empezó; si no, el que tendría con esa semilla."""
    if doc:
        return doc["orden"], doc["semilla"]
    semilla = secrets.randbelow(2 ** 31) if semilla is None else semilla
    return cal.nueva_revision(prueba, revisor="", a_ciegas=True, semilla=semilla)["orden"], semilla


def _falsos_negativos(prueba: dict, terminos: dict[str, dict], es_ambiguo, semilla: int) -> list[dict]:
    fn = cal.falsos_negativos(prueba, None, terminos, es_ambiguo)
    lista = [{"modelo": m, "item": x["item"], "error": x["error"]} for m, v in fn.items() for x in v["items"]]
    lista.sort(key=lambda x: (x["item"], x["modelo"]))
    random.Random(f"{semilla}:fn").shuffle(lista)
    return lista


def _sid(k: int) -> str:
    return f"S{k + 1:03d}"


def _fid(k: int) -> str:
    return f"F{k + 1:02d}"


def exportar(prueba: dict, doc: dict | None, modos_doc: dict | None, terminos: dict[str, dict], es_ambiguo, *,
             codigo: str, solo_pendientes: bool = False, semilla: int | None = None) -> dict:
    """El contenido del archivo, sin nombres de modelos::

        {formato, prueba, semilla, n_salidas, huella, n_fn, huella_fn, criterio, banco,
         salidas: [{id, termino, dominio, contexto, cita, lecturas, intenciones}],
         falsos_negativos: [{id, termino, dominio, contexto, cita, lecturas, respuesta, error}],
         plantilla: {formato, prueba, huella, huella_fn, respuestas: […], modos: […]}}
    """
    orden, semilla = _orden(prueba, doc, semilla)
    marcas = (doc or {}).get("marcas", {})
    salidas = []
    for k, o in enumerate(orden):
        if solo_pendientes and o["item"] in marcas.get(o["modelo"], {}):
            continue
        t, r = terminos[o["item"]], prueba["resultados"][o["modelo"]][o["item"]]
        salidas.append({"id": _sid(k), "termino": t["termino"], "dominio": t["dominio"], "contexto": t["contexto"],
                        "cita": t["cita"], "lecturas": t["lecturas"] if es_ambiguo(t) else [],
                        "intenciones": [{"significado": x["significado"], "intencion": x["intencion"],
                                         "parafrasis": x["parafrasis"]} for x in r["intenciones"]]})
    fns = _falsos_negativos(prueba, terminos, es_ambiguo, semilla)
    ya = (modos_doc or {}).get("modos", {})
    falsos = []
    for k, f in enumerate(fns):
        if solo_pendientes and f["item"] in ya.get(f["modelo"], {}):
            continue
        t, r = terminos[f["item"]], prueba["resultados"][f["modelo"]][f["item"]]
        respuesta = ("(no dio una salida válida)" if f["error"]
                     else " | ".join(x["significado"] for x in r["intenciones"]))
        falsos.append({"id": _fid(k), "termino": t["termino"], "dominio": t["dominio"], "contexto": t["contexto"],
                       "cita": t["cita"], "lecturas": t["lecturas"], "respuesta": respuesta, "error": f["error"]})
    cabecera = {"formato": FORMATO, "prueba": codigo, "semilla": semilla,
                "n_salidas": len(orden), "huella": _huella([(o["item"], o["modelo"]) for o in orden]),
                "n_fn": len(fns), "huella_fn": _huella([(f["item"], f["modelo"]) for f in fns])}
    plantilla = dict(cabecera) | {
        "respuestas": [{"id": s["id"], "fidelidad": None, "delimitacion": None, "intencion": None,
                        **({"lecturas": []} if s["lecturas"] else {}), "nota": ""} for s in salidas],
        "modos": [{"id": f["id"], "modo": "formato" if f["error"] else None, "nota": ""} for f in falsos]}
    return cabecera | {"criterio": cal.CRITERIO, "banco": prueba.get("banco"), "salidas": salidas,
                       "falsos_negativos": falsos, "plantilla": plantilla}


def markdown(contenido: dict) -> str:
    """El archivo para pegarlo en un chat o dárselo a una persona."""
    c = contenido
    L = [
        f"# Revisión de calidad · prueba {c['prueba']}",
        "",
        ("Vas a revisar lo que escribieron varios modelos de lenguaje al explicar términos que pueden ser ambiguos "
         "en entrevistas de requisitos. No sabes qué modelo escribió cada salida y no tienes que adivinarlo."),
        "",
        "## Qué devolver",
        "",
        ("Devuelve **solo** el bloque JSON de la sección «Respuesta», completo, con cada `null` cambiado por `true` "
         "o `false`. No cambies los `id` ni los campos de arriba (`formato`, `prueba`, `semilla`, `huella`…): el "
         "sistema los usa para saber a qué salida corresponde cada respuesta."),
        "",
        "- `fidelidad`, `delimitacion`, `intencion`: `true` si la salida cumple el criterio, `false` si no.",
        ("- `lecturas` (solo en los términos ambiguos): los **números** de las lecturas esperadas que aparecen en "
         "alguna intención de la salida, por ejemplo `[1]` o `[1, 3]`; `[]` si ninguna."),
        "- `nota`: opcional, una frase si dudaste.",
        f"- `modo` (falsos negativos): una de {', '.join(f'`{k}`' for k in CLAVES_MODOS)}.",
        "",
        "## Rúbrica",
        "",
        REGLA_AGREGADO,
        "",
    ]
    for cr in CRITERIOS:
        L += [f"### {cr['nombre']} (`{cr['clave']}`)", "", cr["oracion"], "",
              f"- **Pasa:** {cr['pasa']}", f"- **No pasa:** {cr['no_pasa']}", ""]
    L += ["### Lecturas esperadas (`lecturas`)", "", COBERTURA["oracion"], "",
          f"- **Pasa:** {COBERTURA['pasa']}", f"- **No pasa:** {COBERTURA['no_pasa']}", "",
          "### Casos frecuentes", "", *aclaraciones_md(), "",
          "### Modos de falla de los falsos negativos", "",
          ("Un falso negativo es un término ambiguo que el modelo trató como si tuviera un solo sentido (o en el "
           "que falló). Elige el modo que mejor explica qué lectura se le escapó:"), ""]
    L += [f"- `{m['clave']}` — **{m['nombre']}.** {m['descripcion']}" for m in MODOS_FALLA]
    L += ["", f"## Salidas ({len(c['salidas'])})", ""]
    for s in c["salidas"]:
        L += [f"### {s['id']} · {s['termino']} ({s['dominio']})", "", f"Contexto: {s['contexto']}", "",
              f"Cita: «{s['cita']}»", ""]
        if s["lecturas"]:
            L += ["Lecturas esperadas:", *[f"{k}. {x}" for k, x in enumerate(s["lecturas"], 1)], ""]
        else:
            L += ["Término de un solo sentido: no hay lecturas que marcar.", ""]
        n = len(s["intenciones"])
        L += [f"Lo que escribió el modelo ({'una intención' if n == 1 else f'{n} intenciones'}):", ""]
        for k, x in enumerate(s["intenciones"], 1):
            L += [f"- I{k} · significado: {x['significado']}", f"  - intención: {x['intencion']}",
                  f"  - paráfrasis: «{x['parafrasis']}»"]
        L += [""]
    if c["falsos_negativos"]:
        L += [f"## Falsos negativos por clasificar ({len(c['falsos_negativos'])})", ""]
        for f in c["falsos_negativos"]:
            L += [f"### {f['id']} · {f['termino']} ({f['dominio']})", "", f"Cita: «{f['cita']}»", "",
                  "Lecturas esperadas:", *[f"{k}. {x}" for k, x in enumerate(f["lecturas"], 1)], "",
                  f"Respuesta del modelo: {f['respuesta']}", ""]
    L += ["## Respuesta", "", "```json", json.dumps(c["plantilla"], ensure_ascii=False, indent=1), "```", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- importar

def leer(texto: str) -> dict:
    """El JSON de respuestas: el archivo tal cual, o el último bloque ```json de un Markdown o de la
    respuesta de un chat. Sin bloque, lo que va de la primera { a la última }."""
    texto = texto.strip()
    bloques = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", texto, flags=re.DOTALL)
    candidatos = [texto, *reversed(bloques)]
    if "{" in texto:
        candidatos.append(texto[texto.index("{"): texto.rindex("}") + 1])
    for x in candidatos:
        try:
            d = json.loads(x)
        except ValueError:
            continue
        if isinstance(d, dict) and ("respuestas" in d or "modos" in d):
            return d
    raise ValueError("No encontré el JSON de respuestas: tiene que traer «respuestas» (y opcionalmente «modos»).")


def _booleano(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "sí", "si", "false", "no"):
        return v.strip().lower() in ("true", "sí", "si")
    return None


def importar(prueba: dict, doc: dict | None, modos_doc: dict | None, terminos: dict[str, dict], es_ambiguo,
             datos: dict, *, codigo: str, tipo: str, quien: str, sobrescribir: bool = False,
             semilla: int | None = None) -> tuple[dict | None, dict | None, dict]:
    """Aplica las respuestas. Devuelve (revisión, modos, informe); la revisión se crea si no
    existía y el archivo trae respuestas de calidad, con la semilla del archivo (``semilla`` la
    suple si el JSON no la trae).

    informe: {aplicadas, conservadas, sin_contestar, errores: [{id, motivo}], modos_aplicados,
              modos_conservados, acuerdo: {fidelidad: kappa, …, lecturas: {n, iguales}} | None}
    """
    if tipo not in TIPOS:
        raise ValueError(f"tipo debe ser {' o '.join(TIPOS)}")
    if datos.get("formato") not in (None, FORMATO):
        raise ValueError(f"El archivo es de otro formato ({datos.get('formato')}).")
    if datos.get("prueba") not in (None, codigo):
        raise ValueError(f"El archivo es de la prueba {datos.get('prueba')}, no de {codigo}.")
    semilla = datos.get("semilla", semilla)
    if doc is None and semilla is None and datos.get("respuestas"):
        raise ValueError("Sin revisión empezada, el archivo tiene que traer la semilla con que se exportó.")
    orden, semilla = _orden(prueba, doc, semilla if doc is None else None)
    if doc is not None and datos.get("semilla") not in (None, doc["semilla"]):
        raise ValueError("El archivo se exportó con otro orden: es de una revisión anterior. Expórtalo de nuevo.")
    pares_orden = [(o["item"], o["modelo"]) for o in orden]
    if datos.get("respuestas") and datos.get("huella") is not None:
        n = datos.get("n_salidas") or len(orden)
        if datos["huella"] != _huella(pares_orden[:n]):
            raise ValueError("La huella del archivo no coincide con esta prueba: la prueba cambió o el archivo es de "
                             "otra revisión. Expórtalo de nuevo.")
    fns = _falsos_negativos(prueba, terminos, es_ambiguo, semilla)
    if (datos.get("modos") and datos.get("huella_fn") is not None
            and datos["huella_fn"] != _huella([(f["item"], f["modelo"]) for f in fns])):
        raise ValueError("La huella de los falsos negativos no coincide: exporta el archivo de nuevo.")

    if doc is None and datos.get("respuestas"):
        doc = cal.nueva_revision(prueba, revisor=quien, a_ciegas=True, semilla=semilla)
        doc["revisor_tipo"] = tipo
    numero = len((doc or {}).get("importaciones", [])) + 1
    origen = {"tipo": tipo, "quien": quien, "importacion": numero}
    informe = {"aplicadas": 0, "conservadas": 0, "sin_contestar": 0, "errores": [], "modos_aplicados": 0,
               "modos_conservados": 0}
    previas: dict[str, dict] = {}   # id → marca que ya había (para el acuerdo)
    importadas: dict[str, dict] = {}
    registro = []
    for x in datos.get("respuestas") or []:
        sid = str(x.get("id", ""))
        m = re.fullmatch(r"S(\d+)", sid)
        if not m or not 1 <= int(m.group(1)) <= len(orden):
            informe["errores"].append({"id": sid or "?", "motivo": "id desconocido"})
            continue
        o = orden[int(m.group(1)) - 1]
        crit = {k: _booleano(x.get(k)) for k in CLAVES}
        if any(v is None for v in crit.values()):
            informe["sin_contestar"] += 1
            continue
        t = terminos[o["item"]]
        lecturas = x.get("lecturas") or []
        if not isinstance(lecturas, list) or not all(isinstance(v, int) and not isinstance(v, bool) for v in lecturas):
            informe["errores"].append({"id": sid, "motivo": "lecturas tiene que ser una lista de números"})
            continue
        if es_ambiguo(t) and any(not 1 <= v <= len(t["lecturas"]) for v in lecturas):
            informe["errores"].append({"id": sid, "motivo": f"lecturas fuera de 1–{len(t['lecturas'])}"})
            continue
        cobertura = sorted({v - 1 for v in lecturas}) if es_ambiguo(t) else []
        nota = (str(x.get("nota") or "").strip() or None)
        importadas[sid] = {**crit, "cobertura": cobertura}
        ya = doc["marcas"].get(o["modelo"], {}).get(o["item"])
        if ya:
            previas[sid] = ya
        aplicar = not ya or sobrescribir
        registro.append({"id": sid, "item": o["item"], "modelo": o["modelo"], **crit, "cobertura": cobertura,
                         "nota": nota, "aplicada": aplicar})
        if not aplicar:
            informe["conservadas"] += 1
            continue
        marca = cal.marcar(doc, modelo=o["modelo"], item=o["item"], criterios=crit, cobertura=cobertura,
                           n_lecturas=len(t["lecturas"]), ambiguo=es_ambiguo(t), nota=nota[:500] if nota else None)
        marca["origen"] = origen
        informe["aplicadas"] += 1

    for x in datos.get("modos") or []:
        fid = str(x.get("id", ""))
        m = re.fullmatch(r"F(\d+)", fid)
        if not m or not 1 <= int(m.group(1)) <= len(fns):
            informe["errores"].append({"id": fid or "?", "motivo": "id desconocido"})
            continue
        if x.get("modo") in (None, ""):
            continue
        if x["modo"] not in CLAVES_MODOS:
            informe["errores"].append({"id": fid, "motivo": f"modo desconocido: {x['modo']}"})
            continue
        f = fns[int(m.group(1)) - 1]
        if modos_doc is None:
            modos_doc = {"prueba_id": prueba["prueba_id"], "usuario_id": prueba["usuario_id"], "modos": {}}
        if modos_doc["modos"].get(f["modelo"], {}).get(f["item"]) and not sobrescribir:
            informe["modos_conservados"] += 1
            continue
        nota = (str(x.get("nota") or "").strip() or None)
        cal.asignar_modo(modos_doc, modelo=f["modelo"], item=f["item"], modo=x["modo"], nota=nota[:500] if nota else None)
        modos_doc["modos"][f["modelo"]][f["item"]]["origen"] = origen
        informe["modos_aplicados"] += 1

    informe["acuerdo"] = acuerdo(previas, importadas)
    if doc is None:
        return None, modos_doc, informe
    doc.setdefault("importaciones", []).append({
        "numero": numero, "fecha": cal.ahora(), "tipo": tipo, "quien": quien, "sobrescribir": sobrescribir,
        **{k: informe[k] for k in ("aplicadas", "conservadas", "sin_contestar", "modos_aplicados", "modos_conservados")},
        "errores": len(informe["errores"]), "acuerdo": informe["acuerdo"], "respuestas": registro})
    doc["actualizada"] = cal.ahora()
    return doc, modos_doc, informe


def acuerdo(previas: dict[str, dict], importadas: dict[str, dict]) -> dict | None:
    """Kappa por criterio entre la marca que ya había y la importada, en las salidas que tienen las
    dos; en las lecturas, cuántas coinciden exactamente."""
    comunes = [k for k in previas if k in importadas]
    if not comunes:
        return None
    salida = {c: kappa({k: bool(previas[k][c]) for k in comunes}, {k: importadas[k][c] for k in comunes})
              for c in CLAVES}
    con_lecturas = [k for k in comunes if previas[k].get("cobertura") or importadas[k]["cobertura"]]
    salida["lecturas"] = {"n": len(con_lecturas),
                          "iguales": sum(1 for k in con_lecturas if sorted(previas[k].get("cobertura") or [])
                                         == importadas[k]["cobertura"])}
    return salida


def composicion(doc: dict | None) -> dict:
    """Cuántas marcas vienen de cada origen: pantalla (sin origen), persona o IA por archivo."""
    cuenta = {"pantalla": 0, "persona": 0, "ia": 0}
    quienes: dict[str, set] = {"persona": set(), "ia": set()}
    for mm in (doc or {}).get("marcas", {}).values():
        for marca in mm.values():
            o = marca.get("origen")
            if not o:
                cuenta["pantalla"] += 1
            else:
                cuenta[o["tipo"]] += 1
                quienes[o["tipo"]].add(o["quien"])
    return cuenta | {"quienes_ia": sorted(quienes["ia"]), "quienes_persona": sorted(quienes["persona"])}
