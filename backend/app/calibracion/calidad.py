"""Revisión humana de la calidad de las salidas del Clasificador y métricas que dependen de ella
(ADR 0029). Funciones puras sobre documentos ya leídos: nada aquí llama a un LLM.

**Qué se revisa.** Solo la factura de lo que el modelo escribió, con tres criterios booleanos
independientes (`rubrica.CRITERIOS`): fidelidad, delimitación e intención. La detección (si marcó
«ambiguo») no se revisa: se mide sola contra el banco. En los términos ambiguos, además, la
persona marca qué lecturas esperadas del banco aparecen en la salida (cobertura).

**Granularidad: una marca por salida** (un término de un modelo). Un criterio se cumple si lo
cumplen todas las intenciones de esa salida. Así cada salida es una observación pareable entre
modelos (McNemar por ítem) y la revisión cuesta una tecla por criterio, no una por intención.

**Documento** (`revisiones_calidad`, uno por prueba, con el mismo id)::

    {prueba_id, usuario_id, esquema: 2, criterio: "calidad-v1", revisor, a_ciegas, semilla,
     orden: [{item, modelo}], letras: {M1: "A", …}, creada, actualizada,
     marcas: {M1: {B01: {fidelidad, delimitacion, intencion, cobertura: [índices], nota, fecha}}}}

Los modos de falla de los falsos negativos van aparte (`modos_falla`, uno por prueba), porque se
clasifican sin necesidad de empezar la revisión a ciegas::

    {prueba_id, usuario_id, modos: {M1: {B30: {modo, nota, fecha}}}, actualizada}

`orden` se guarda ya barajado (con `semilla`), para que la revisión sea reconstruible tal cual se
hizo. La revisión vieja de la v2.3 (`revisiones_modelos`, un ✓/✗ por salida) no se toca ni se
traduce: un ✓ no dice cuál de los tres criterios se cumplió.
"""
from __future__ import annotations

import math
import random
import secrets
from datetime import UTC, datetime

from .rubrica import CLAVES, CLAVES_MODOS

COLECCION_CALIDAD = "revisiones_calidad"
COLECCION_MODOS = "modos_falla"
ESQUEMA = 2
CRITERIO = "calidad-v1"
LETRAS = "ABCDEFGH"


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------- estadística mínima (sin dependencias)

Z = 1.959963984540054


def wilson(exitos: int, n: int) -> dict:
    """Proporción con su intervalo de Wilson al 95 %."""
    if not n:
        return {"valor": None, "bajo": None, "alto": None, "exitos": exitos, "n": 0}
    p = exitos / n
    den = 1 + Z * Z / n
    centro = (p + Z * Z / (2 * n)) / den
    medio = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return {"valor": p, "bajo": max(0.0, centro - medio), "alto": min(1.0, centro + medio), "exitos": exitos, "n": n}


def mcnemar(b: int, c: int) -> float | None:
    """p bilateral de la prueba exacta de McNemar con b y c pares discordantes."""
    n = b + c
    if not n:
        return None
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


# ---------------------------------------------------------------- sesión de revisión

def revisables(prueba: dict) -> dict[str, list[str]]:
    """{item: [modelos con salida válida]}: lo que se puede revisar (un error no tiene factura)."""
    salida: dict[str, list[str]] = {}
    for i in prueba["items"]:
        ms = [m["id"] for m in prueba["modelos"] if (prueba["resultados"].get(m["id"], {}).get(i) or {}).get("ok")]
        if ms:
            salida[i] = ms
    return salida


def _barajar(pares: dict[str, list[str]], rng: random.Random) -> list[dict]:
    items = list(pares)
    rng.shuffle(items)
    orden = []
    for i in items:
        ms = list(pares[i])
        rng.shuffle(ms)
        orden += [{"item": i, "modelo": m} for m in ms]
    return orden


def nueva_revision(prueba: dict, *, revisor: str, a_ciegas: bool, semilla: int | None = None) -> dict:
    """Una revisión vacía con el orden barajado: los ítems y, dentro de cada ítem, los modelos.
    Las letras de los modelos (A, B, C…) también salen de la semilla."""
    semilla = secrets.randbelow(2 ** 31) if semilla is None else semilla
    rng = random.Random(semilla)
    ids = [m["id"] for m in prueba["modelos"]]
    barajados = ids[:]
    rng.shuffle(barajados)
    return {
        "prueba_id": prueba["prueba_id"], "usuario_id": prueba["usuario_id"], "esquema": ESQUEMA, "criterio": CRITERIO,
        "revisor": revisor, "a_ciegas": a_ciegas, "semilla": semilla,
        "letras": {m: LETRAS[k] for k, m in enumerate(barajados)},
        "orden": _barajar(revisables(prueba), rng),
        "creada": ahora(), "actualizada": ahora(), "marcas": {},
    }


def completar_orden(doc: dict, prueba: dict) -> bool:
    """Si la prueba ganó salidas después de empezar la revisión (se reintentaron errores), se
    agregan al final, barajadas con una semilla derivada: lo ya revisado no cambia de lugar.
    Devuelve si cambió algo."""
    vistos = {(o["item"], o["modelo"]) for o in doc["orden"]}
    nuevos: dict[str, list[str]] = {}
    for i, ms in revisables(prueba).items():
        resto = [m for m in ms if (i, m) not in vistos]
        if resto:
            nuevos[i] = resto
    if not nuevos:
        return False
    doc["orden"] += _barajar(nuevos, random.Random(f"{doc['semilla']}:{len(doc['orden'])}"))
    return True


def marcar(doc: dict, *, modelo: str, item: str, criterios: dict[str, bool], cobertura: list[int],
           n_lecturas: int, ambiguo: bool, nota: str | None) -> dict:
    """Guarda la marca de una salida. La cobertura solo vale en los ítems ambiguos y con índices
    de lecturas que existen."""
    if set(criterios) != set(CLAVES):
        raise ValueError(f"faltan criterios: se esperan {', '.join(CLAVES)}")
    cob = sorted({c for c in cobertura if 0 <= c < n_lecturas}) if ambiguo else []
    marca = {**{k: bool(criterios[k]) for k in CLAVES}, "cobertura": cob, "nota": nota or None, "fecha": ahora()}
    doc["marcas"].setdefault(modelo, {})[item] = marca
    doc["actualizada"] = ahora()
    return marca


def asignar_modo(doc: dict, *, modelo: str, item: str, modo: str | None, nota: str | None) -> None:
    if modo is not None and modo not in CLAVES_MODOS:
        raise ValueError(f"modo desconocido: {modo}")
    modos = doc.setdefault("modos", {}).setdefault(modelo, {})
    if modo is None:
        modos.pop(item, None)
    else:
        modos[item] = {"modo": modo, "nota": nota or None, "fecha": ahora()}
    doc["actualizada"] = ahora()


# ---------------------------------------------------------------- métricas

def _detectado(r: dict | None) -> bool:
    return bool(r and r.get("ok") and r.get("ambiguo"))


def calidad_de(prueba: dict, doc: dict | None, terminos: dict[str, dict], es_ambiguo) -> dict[str, dict]:
    """Por modelo: los tres criterios (Wilson sobre las salidas revisadas) y la cobertura::

        {M1: {revisadas, revisables, criterios: {fidelidad: wilson, …},
              cobertura: {items, cubiertas, esperadas, proporcion, por_item: [{item, cubiertas, esperadas}]}}}
    """
    marcas = (doc or {}).get("marcas", {})
    pares = revisables(prueba)
    salida = {}
    for m in prueba["modelos"]:
        mm = marcas.get(m["id"], {})
        revisadas = [i for i in prueba["items"] if i in mm]
        cob = [{"item": i, "cubiertas": len(mm[i]["cobertura"]), "esperadas": len(terminos[i]["lecturas"])}
               for i in revisadas if es_ambiguo(terminos[i])]
        cubiertas, esperadas = sum(c["cubiertas"] for c in cob), sum(c["esperadas"] for c in cob)
        salida[m["id"]] = {
            "revisadas": len(revisadas), "revisables": sum(1 for ms in pares.values() if m["id"] in ms),
            "criterios": {k: wilson(sum(1 for i in revisadas if mm[i][k]), len(revisadas)) for k in CLAVES},
            "cobertura": {"items": len(cob), "cubiertas": cubiertas, "esperadas": esperadas,
                          "proporcion": cubiertas / esperadas if esperadas else None, "por_item": cob},
        }
    return salida


def subenumeracion(prueba: dict, terminos: dict[str, dict], es_ambiguo) -> dict[str, dict]:
    """Por modelo, en los ítems ambiguos: lecturas esperadas contra intenciones producidas. La
    divergencia es el coseno mínimo entre paráfrasis: si la lectura más alejada nunca se genera,
    el mínimo sube y un término ambiguo puede pasar el umbral como unívoco::

        {M1: {con_tres: {n, marcados, tres_o_mas}, por_item: [{item, lecturas, intenciones, ok}]}}
    """
    salida = {}
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        por_item = []
        for i in prueba["items"]:
            if not es_ambiguo(terminos[i]):
                continue
            r = res.get(i)
            ok = bool(r and r.get("ok"))
            por_item.append({"item": i, "lecturas": len(terminos[i]["lecturas"]),
                             "intenciones": len(r["intenciones"]) if ok else None, "ok": ok})
        tres = [p for p in por_item if p["lecturas"] >= 3]
        salida[m["id"]] = {"con_tres": {"n": len(tres),
                                        "marcados": sum(1 for p in tres if p["ok"] and p["intenciones"] >= 2),
                                        "tres_o_mas": sum(1 for p in tres if p["ok"] and p["intenciones"] >= 3)},
                           "por_item": por_item}
    return salida


def falsos_negativos(prueba: dict, doc: dict | None, terminos: dict[str, dict], es_ambiguo) -> dict[str, dict]:
    """Por modelo, los ambiguos que no detectó (unívoco o error) con su modo de falla, si ya se
    clasificó, y una sugerencia: «formato» cuando la salida no fue válida::

        {M1: {items: [{item, termino, error, modo, nota, sugerido}], por_modo: {modo: n}, sin_clasificar}}
    """
    modos = (doc or {}).get("modos", {})
    salida = {}
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        mm = modos.get(m["id"], {})
        items = []
        for i in prueba["items"]:
            if not es_ambiguo(terminos[i]) or i not in res or _detectado(res[i]):
                continue
            asignado = mm.get(i) or {}
            items.append({"item": i, "termino": terminos[i]["termino"], "error": not res[i].get("ok"),
                          "modo": asignado.get("modo"), "nota": asignado.get("nota"),
                          "sugerido": "formato" if not res[i].get("ok") else None})
        por_modo = {k: sum(1 for x in items if x["modo"] == k) for k in CLAVES_MODOS}
        salida[m["id"]] = {"items": items, "por_modo": por_modo, "sin_clasificar": sum(1 for x in items if not x["modo"])}
    return salida


def pares(prueba: dict, doc: dict | None, terminos: dict[str, dict], es_ambiguo) -> list[dict]:
    """McNemar exacta entre cada par de modelos:

    - **detección**, sobre los ítems ambiguos (un error cuenta como no detectado, igual que en la
      exhaustividad);
    - **cada criterio de calidad por separado**, solo en los ítems revisados en los dos modelos y
      con el mismo número de intenciones: juzgar una lectura contra dos no es la misma cantidad
      en los dos lados. Los ítems excluidos por eso se cuentan.
    """
    marcas = (doc or {}).get("marcas", {})
    ambiguos = [i for i in prueba["items"] if es_ambiguo(terminos[i])]
    salida = []
    modelos = prueba["modelos"]
    for k, a in enumerate(modelos):
        for b in modelos[k + 1:]:
            ra, rb = prueba["resultados"].get(a["id"], {}), prueba["resultados"].get(b["id"], {})
            hechos = [i for i in ambiguos if i in ra and i in rb]
            solo_a = sum(1 for i in hechos if _detectado(ra[i]) and not _detectado(rb[i]))
            solo_b = sum(1 for i in hechos if _detectado(rb[i]) and not _detectado(ra[i]))
            ma, mb = marcas.get(a["id"], {}), marcas.get(b["id"], {})
            ambos = [i for i in prueba["items"] if i in ma and i in mb]
            comparables = [i for i in ambos if len(ra[i]["intenciones"]) == len(rb[i]["intenciones"])]
            calidad = {}
            for c in CLAVES:
                ca = sum(1 for i in comparables if ma[i][c] and not mb[i][c])
                cb = sum(1 for i in comparables if mb[i][c] and not ma[i][c])
                calidad[c] = {"n": len(comparables), "solo_a": ca, "solo_b": cb, "p": mcnemar(ca, cb)}
            salida.append({"a": a["id"], "b": b["id"],
                           "deteccion": {"n": len(hechos), "solo_a": solo_a, "solo_b": solo_b, "p": mcnemar(solo_a, solo_b)},
                           "calidad": calidad, "revisados_en_ambos": len(ambos),
                           "excluidos_por_intenciones": len(ambos) - len(comparables)})
    return salida


def aprobacion_legado(prueba: dict, legado: dict | None) -> dict[str, dict] | None:
    """La aprobación de la v2.3 (un ✓/✗ por salida), tal como se guardó y con su criterio viejo.
    No se traduce a los criterios nuevos."""
    if not legado or not legado.get("marcas"):
        return None
    salida = {}
    for m in prueba["modelos"]:
        mm = legado["marcas"].get(m["id"], {})
        revisados = [i for i in prueba["items"] if mm.get(i, {}).get("bueno") is not None]
        salida[m["id"]] = wilson(sum(1 for i in revisados if mm[i]["bueno"]), len(revisados))
    return {"criterio": "aprobacion-v2.3 (un ✓/✗ por salida, sin desglose)", "a_ciegas": legado.get("a_ciegas"),
            "revisor": legado.get("revisor"), "por_modelo": salida}
