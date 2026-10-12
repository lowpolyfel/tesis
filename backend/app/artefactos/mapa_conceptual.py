"""Mapa conceptual del proyecto (ADR 0020).

El Big Picture (big_picture.py) es el grafo completo: sirve para rastrear cada
relación, pero con todos los requisitos, metas y términos a la vista es enorme. El
mapa conceptual es su versión para leer: pocos conceptos unidos por frases
«concepto — enlace → concepto» alrededor de un concepto central.

Se arma con un protocolo de pasos. Todos son funciones puras salvo el 4:

1. reunir       el Big Picture de lo validado (sin LLM).
2. conceptos    candidatos: actores, términos del léxico (los verbos no: son
                enlaces), objetos de las metas, recursos y cualidades (metas
                blandas). Los repetidos se unen («usuario» y «usuarios») y «el
                sistema» pasa a ser el concepto central.
3. relaciones   proposiciones candidatas: actor —verbo de su meta→ objeto,
                objeto —debe cumplir→ cualidad, actor —necesita→ recurso, término
                —se relaciona con→ término. Se pesan por cuántos requisitos las
                respaldan y se recortan (LIMITE_CONCEPTOS, LIMITE_PROPOSICIONES,
                MAX_GRADO).
4. Modelador    elige los conceptos, los agrupa en ramas y nombra las relaciones
                (LLM), solo con los ids candidatos.
5. revisión     verifica las referencias, descarta las relaciones que ningún
                requisito respalda, las repetidas y los conceptos sueltos. Si el
                Modelador falla o no está, queda el mapa del paso 3 (en código).

`generar_mapa` recorre los pasos y va diciendo cuál hace (la pantalla de carga).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from collections.abc import Iterator

from app.nlp import normalizar

from .exportar import ids_saneados, texto_mermaid
from .terminos import numero_req, separar_accion

log = logging.getLogger(__name__)

COLECCION = "mapas_conceptuales"
VERSION = "mapa_v1"  # cambia la huella: un protocolo nuevo no reutiliza mapas viejos
CENTRAL = "central"
LIMITE_CONCEPTOS = 14
LIMITE_PROPOSICIONES = 16
MAX_GRADO = 3  # relaciones por concepto (el central admite el doble)
CANDIDATOS_LLM = 24  # el Modelador elige entre más candidatos de los que caben
MAX_PALABRAS_ENLACE = 5

_ARTICULOS = {"el", "la", "los", "las", "un", "una", "unos", "unas", "al", "del", "lo", "su", "sus", "a", "de"}
_SISTEMA = {"sistema", "el sistema", "aplicacion", "plataforma", "software"}
# si un concepto llega por dos caminos, el tipo más específico gana
_PRIORIDAD = {"actor": 0, "recurso": 1, "cualidad": 2, "termino": 3, "objeto": 4}
_RAMAS = (("actor", "Personas y roles"), ("termino", "Lo que maneja"), ("objeto", "Lo que maneja"),
          ("recurso", "Recursos"), ("cualidad", "Calidad"))


# ---------------------------------------------------------------- paso 2: conceptos

def _singular(palabra: str) -> str:
    if len(palabra) <= 3 or not palabra.endswith("s"):
        return palabra
    if palabra.endswith("es") and palabra[-3] in "lrndzj":  # proveedores → proveedor
        return palabra[:-2]
    return palabra[:-1]  # clientes → cliente, usuarios → usuario


def clave(texto: str) -> str:
    """Forma para unir conceptos repetidos: sin acentos, sin artículo inicial y en singular."""
    palabras = re.sub(r"[^\w\s]", " ", normalizar(texto)).split()
    while palabras and palabras[0] in _ARTICULOS:
        palabras = palabras[1:]
    return " ".join(_singular(p) for p in palabras)


def _limpia(texto: str) -> str:
    """La etiqueta sin artículo inicial ni puntuación al final: «el cliente nuevo.» → «cliente nuevo»."""
    palabras = " ".join(texto.split()).strip(" .,;:").split(" ")
    while len(palabras) > 1 and normalizar(palabras[0]) in _ARTICULOS:
        palabras = palabras[1:]
    return " ".join(palabras)


# presente de los irregulares más comunes en requisitos; el resto sigue la regla
_IRREGULARES = {
    "ir": "va", "ser": "es", "estar": "está", "tener": "tiene", "poder": "puede", "querer": "quiere",
    "mostrar": "muestra", "contar": "cuenta", "encontrar": "encuentra", "recordar": "recuerda", "probar": "prueba",
    "comprobar": "comprueba", "cerrar": "cierra", "empezar": "empieza", "comenzar": "comienza", "entender": "entiende",
    "volver": "vuelve", "devolver": "devuelve", "mover": "mueve", "elegir": "elige", "pedir": "pide",
    "seguir": "sigue", "conseguir": "consigue", "servir": "sirve", "medir": "mide", "repetir": "repite",
    "corregir": "corrige", "preferir": "prefiere", "sentir": "siente", "impedir": "impide", "requerir": "requiere",
}


def conjugar(enlace: str) -> str:
    """«consultar» → «consulta», «dar de alta» → «da de alta»: un mapa conceptual se lee en presente."""
    primera, _, resto = enlace.strip().partition(" ")
    p = primera.lower()
    if p in _IRREGULARES:
        verbo = _IRREGULARES[p]
    elif p.endswith("ar"):
        verbo = p[:-2] + "a"
    elif p.endswith(("er", "ir")):
        verbo = p[:-2] + "e"
    else:
        verbo = p
    return f"{verbo} {resto}".strip()


class _Candidatos:
    """Conceptos y relaciones candidatas, sin repetidos."""

    def __init__(self):
        self.conceptos: dict[str, dict] = {}  # clave → concepto
        self.relaciones: dict[tuple[str, str], dict] = {}

    def concepto(self, etiqueta: str, tipo: str, req_ids, detalle: str | None = None) -> str | None:
        k = clave(etiqueta)
        if not k:
            return None
        if k in _SISTEMA:
            return CENTRAL
        c = self.conceptos.get(k)
        if c is None:
            c = self.conceptos[k] = {"id": f"C{len(self.conceptos) + 1}", "etiqueta": _limpia(etiqueta), "tipo": tipo,
                                     "req_ids": set(), "detalle": detalle}
        elif _PRIORIDAD[tipo] < _PRIORIDAD[c["tipo"]]:
            c["tipo"] = tipo
        c["req_ids"] |= set(req_ids)
        c["detalle"] = c["detalle"] or detalle
        return c["id"]

    def tipo(self, id_: str | None) -> str | None:
        return next((c["tipo"] for c in self.conceptos.values() if c["id"] == id_), None)

    def unir(self, origen: str | None, enlace: str, destino: str | None, req_ids, peso: float) -> None:
        if not origen or not destino or origen == destino:
            return
        par = (origen, destino) if (destino, origen) not in self.relaciones else (destino, origen)
        r = self.relaciones.get(par)
        if r is None:  # la primera relación entre dos conceptos se queda con su enlace
            self.relaciones[par] = {"origen": origen, "enlace": enlace, "destino": destino,
                                    "req_ids": set(req_ids), "peso": peso}
        else:
            r["req_ids"] |= set(req_ids)
            r["peso"] += peso


def candidatos(bp: dict) -> tuple[list[dict], list[dict]]:
    """Pasos 2 y 3 sin recortar: (conceptos, relaciones) con su peso, de más a menos peso."""
    nodos = {n["id"]: n for n in bp["nodos"]}
    de = lambda rel: [(a["origen"], a["destino"]) for a in bp["aristas"] if a["relacion"] == rel]
    cand = _Candidatos()

    concepto_de: dict[str, str | None] = {}  # id del grafo → id del concepto
    for n in bp["nodos"]:
        if n["tipo"] == "actor":
            concepto_de[n["id"]] = cand.concepto(n["etiqueta"], "actor", n["req_ids"])
    for n in bp["nodos"]:  # los verbos del léxico («dar de alta») son enlaces, no conceptos
        if n["tipo"] == "simbolo" and n.get("subtipo") != "verbo":
            tipo = "actor" if n.get("subtipo") == "sujeto" else "termino"  # un sujeto del LEL es un actor
            concepto_de[n["id"]] = cand.concepto(n["etiqueta"], tipo, n["req_ids"], n.get("detalle"))

    actor_de = {m: concepto_de.get(a) for a, m in de("persigue")}
    usa: dict[str, list[str]] = {}
    for m, s in de("usa"):
        usa.setdefault(m, []).append(s)
    aporta_a = dict(de("contribuye_a"))
    metas = [n for n in bp["nodos"] if n["tipo"] in ("meta", "tarea", "meta_blanda", "recurso")]

    objeto_de: dict[str, str | None] = {}
    for m in (x for x in metas if x["tipo"] in ("meta", "tarea")):
        verbo, objeto = separar_accion(m["etiqueta"])
        for s in usa.get(m["id"], []):  # un verbo del léxico («dar de alta») es el enlace completo
            n = nodos[s]
            if n.get("subtipo") == "verbo" and clave(m["etiqueta"]).startswith(clave(n["etiqueta"])):
                largo = len(n["etiqueta"].split())
                verbo, objeto = n["etiqueta"].lower(), " ".join(m["etiqueta"].split()[largo:])
                break
        if verbo is None:  # «Que el cliente quede registrado»: no se inventa el verbo
            continue
        verbo = conjugar(verbo)
        usados = [s for s in usa.get(m["id"], []) if concepto_de.get(s)]
        en_objeto = [s for s in usados if clave(nodos[s]["etiqueta"]) in clave(objeto)]
        if en_objeto:
            obj = concepto_de[en_objeto[0]]
        elif objeto and len(_limpia(objeto).split()) <= 5:
            obj = cand.concepto(objeto, "objeto", m["req_ids"])
        else:
            obj = None
        objeto_de[m["id"]] = obj
        cand.unir(actor_de.get(m["id"]) or CENTRAL, verbo, obj, m["req_ids"], 2)
        for s in usados:  # «Avisar las existencias bajas» que usa «gerente»: existencia —se avisa a→ gerente
            if s not in en_objeto:
                otro = concepto_de[s]
                es_actor = cand.tipo(otro) == "actor"
                cand.unir(obj, f"se {verbo.split()[0]} a" if es_actor else "involucra", otro, m["req_ids"], 1)
    for m in metas:
        destino = aporta_a.get(m["id"])
        if m["tipo"] == "meta_blanda":
            cualidad = cand.concepto(m["etiqueta"], "cualidad", m["req_ids"])
            cand.unir(objeto_de.get(destino) or actor_de.get(destino) or CENTRAL, "debe cumplir", cualidad,
                      m["req_ids"], 1.5)
        elif m["tipo"] == "recurso":
            # «Precio del producto» es el «precio» del léxico, no otro concepto
            k = clave(m["etiqueta"])
            recurso = next((c["id"] for kc, c in cand.conceptos.items() if k.startswith(kc + " ")), None) \
                or cand.concepto(m["etiqueta"], "recurso", m["req_ids"])
            cand.unir(actor_de.get(destino) or objeto_de.get(destino) or CENTRAL, "necesita", recurso,
                      m["req_ids"], 1.5)

    for a, b in de("relacionado_con"):
        if nodos[a]["tipo"] == "simbolo" and nodos[b]["tipo"] == "simbolo":
            cand.unir(concepto_de.get(a), "se relaciona con", concepto_de.get(b),
                      set(nodos[a]["req_ids"]) | set(nodos[b]["req_ids"]), 0.5)

    # nada queda suelto: los actores usan el sistema y lo demás es parte de él
    tocados = {x for r in cand.relaciones.values() for x in (r["origen"], r["destino"])}
    for c in cand.conceptos.values():
        if c["id"] not in tocados:
            if c["tipo"] == "actor":
                cand.unir(c["id"], "usa", CENTRAL, c["req_ids"], 1)
            else:
                cand.unir(CENTRAL, "incluye", c["id"], c["req_ids"], 0.5)

    relaciones = sorted(cand.relaciones.values(), key=lambda r: -r["peso"])  # estable: el orden de llegada desempata
    peso = Counter()
    for r in relaciones:
        peso[r["origen"]] += r["peso"]
        peso[r["destino"]] += r["peso"]
    conceptos = list(cand.conceptos.values())
    for c in conceptos:
        c["peso"] = round(2 * len(c["req_ids"]) + peso[c["id"]], 2)
    conceptos.sort(key=lambda c: -c["peso"])
    return conceptos, relaciones


def recortar(conceptos: list[dict], relaciones: list[dict], max_conceptos: int = LIMITE_CONCEPTOS,
             max_proposiciones: int = LIMITE_PROPOSICIONES, max_grado: int = MAX_GRADO) -> tuple[list[dict], list[dict]]:
    """Los conceptos de más peso y sus relaciones de más peso, sin pasar del grado máximo.
    Un concepto que se queda sin relaciones se va."""
    quedan = {c["id"] for c in conceptos[:max_conceptos]} | {CENTRAL}
    grado: Counter = Counter()
    elegidas = []
    for r in relaciones:
        o, d = r["origen"], r["destino"]
        if o not in quedan or d not in quedan:
            continue
        limite = lambda x: max_grado * 2 if x == CENTRAL else max_grado
        if grado[o] >= limite(o) or grado[d] >= limite(d):
            continue
        elegidas.append(r)
        grado[o] += 1
        grado[d] += 1
        if len(elegidas) == max_proposiciones:
            break
    return [c for c in conceptos if grado[c["id"]]], elegidas


# ---------------------------------------------------------------- paso 5: revisión

def verificar_mapa(salida, ids_candidatos: set[str]) -> None:
    """Para `generar(verificar=…)`: el Modelador solo usa ids candidatos; si no, se reintenta."""
    elegidos = {c.id for c in salida.conceptos}
    if desconocidos := sorted(elegidos - ids_candidatos):
        raise ValueError(f"conceptos que no están entre los candidatos: {desconocidos}")
    for r in salida.ramas:
        if fuera := sorted(set(r.conceptos) - elegidos):
            raise ValueError(f"la rama «{r.nombre}» usa conceptos que no elegiste: {fuera}")
    validos = elegidos | {CENTRAL}
    for p in salida.proposiciones:
        if p.origen not in validos or p.destino not in validos:
            raise ValueError(f"la proposición {p.origen} → {p.destino} usa un concepto que no elegiste")
        if len(p.enlace.split()) > MAX_PALABRAS_ENLACE:
            raise ValueError(f"enlace demasiado largo: «{p.enlace}» (de 1 a 4 palabras)")


def del_modelador(salida, conceptos: list[dict], relaciones: list[dict]) -> tuple[dict, int]:
    """Aplica lo que eligió el Modelador sobre los candidatos. Una relación nueva solo se
    queda si sus dos conceptos comparten un requisito (o uno es el central): así cada
    proposición se puede rastrear a lo validado. Devuelve (mapa sin mermaid, descartadas)."""
    por_id = {c["id"]: c for c in conceptos}
    candidatas = {}
    for r in relaciones:
        candidatas[(r["origen"], r["destino"])] = candidatas[(r["destino"], r["origen"])] = r
    elegidos = {}
    for c in salida.conceptos[:LIMITE_CONCEPTOS]:
        if c.id in por_id and c.id not in elegidos:
            elegidos[c.id] = {**por_id[c.id], "etiqueta": _limpia(c.etiqueta) or por_id[c.id]["etiqueta"]}
    proposiciones, vistas, descartadas = [], set(), 0
    for p in salida.proposiciones:
        o, d = p.origen, p.destino
        if o == d or (o != CENTRAL and o not in elegidos) or (d != CENTRAL and d not in elegidos) or (o, d) in vistas:
            descartadas += 1
            continue
        previa = candidatas.get((o, d))
        if previa is not None:
            req_ids = previa["req_ids"]
        elif CENTRAL in (o, d):
            req_ids = elegidos[d if o == CENTRAL else o]["req_ids"]
        else:
            req_ids = elegidos[o]["req_ids"] & elegidos[d]["req_ids"]
            if not req_ids:  # ningún requisito une a los dos conceptos
                descartadas += 1
                continue
        vistas.update({(o, d), (d, o)})
        proposiciones.append({"origen": o, "enlace": " ".join(p.enlace.lower().split()), "destino": d,
                              "req_ids": req_ids})
        if len(proposiciones) == LIMITE_PROPOSICIONES:
            break
    ramas = [{"nombre": r.nombre, "conceptos": [i for i in dict.fromkeys(r.conceptos) if i in elegidos]}
             for r in salida.ramas]
    return _armar(salida.central, list(elegidos.values()), ramas, proposiciones), descartadas


def en_codigo(nombre: str, conceptos: list[dict], relaciones: list[dict]) -> dict:
    """El mapa del paso 3 tal cual, con ramas por tipo de concepto (el respaldo)."""
    ramas: dict[str, list[str]] = {}
    for tipo, rama in _RAMAS:
        ramas.setdefault(rama, []).extend(c["id"] for c in conceptos if c["tipo"] == tipo)
    return _armar(nombre, conceptos, [{"nombre": n, "conceptos": ids} for n, ids in ramas.items()],
                  [{k: r[k] for k in ("origen", "enlace", "destino", "req_ids")} for r in relaciones])


def _armar(central: str, conceptos: list[dict], ramas: list[dict], proposiciones: list[dict]) -> dict:
    """Sin conceptos sueltos ni ramas vacías; cada concepto en una sola rama."""
    tocados = {x for p in proposiciones for x in (p["origen"], p["destino"])}
    conceptos = [c for c in conceptos if c["id"] in tocados]
    ids = {c["id"] for c in conceptos}
    vistos: set[str] = set()
    limpias = []
    for r in ramas:
        propios = [i for i in r["conceptos"] if i in ids and i not in vistos]
        vistos.update(propios)
        if propios:
            limpias.append({"nombre": r["nombre"], "conceptos": propios})
    if sueltos := [c["id"] for c in conceptos if c["id"] not in vistos]:
        limpias.append({"nombre": "Otros", "conceptos": sueltos})
    orden = lambda xs: sorted(xs, key=lambda r: (numero_req(r), r))
    return {
        "central": {"id": CENTRAL, "etiqueta": " ".join(central.split())},
        "conceptos": [{"id": c["id"], "etiqueta": c["etiqueta"], "tipo": c["tipo"], "detalle": c.get("detalle"),
                       "req_ids": orden(c["req_ids"])} for c in conceptos],
        "ramas": limpias,
        "proposiciones": [{**p, "req_ids": orden(p["req_ids"])} for p in proposiciones],
    }


# ---------------------------------------------------------------- dibujo

_ESTILOS = {
    "central": "fill:#1b1712,stroke:#1b1712,color:#ffffff,font-weight:bold",
    "actor": "fill:#eef0ff,stroke:#5b5bd6,color:#1b1712",
    "termino": "fill:#e6f7f5,stroke:#0f8f80,color:#1b1712",
    "objeto": "fill:#e6f7f5,stroke:#0f8f80,color:#1b1712",
    "recurso": "fill:#f3f0ea,stroke:#8a7f6a,color:#1b1712",
    "cualidad": "fill:#fdeef4,stroke:#c2417a,color:#1b1712,stroke-dasharray:4 3",
}


def a_mermaid(mapa: dict) -> str:
    """De arriba abajo: el central y las proposiciones con su enlace. Las ramas no van como
    cajas (obligan a Mermaid a cruzar las líneas de una caja a otra): ordenan los conceptos
    y la interfaz las muestra como leyenda."""
    ids = ids_saneados([CENTRAL] + [c["id"] for c in mapa["conceptos"]])
    por_id = {c["id"]: c for c in mapa["conceptos"]}
    lineas = ["flowchart TD", f'    {ids[CENTRAL]}(["{texto_mermaid(mapa["central"]["etiqueta"])}"])']
    for r in mapa["ramas"]:
        lineas += [f'    {ids[c]}("{texto_mermaid(por_id[c]["etiqueta"])}")' for c in r["conceptos"]]
    for p in mapa["proposiciones"]:
        lineas.append(f'    {ids[p["origen"]]} -->|"{texto_mermaid(p["enlace"])}"| {ids[p["destino"]]}')
    for tipo, estilo in _ESTILOS.items():
        lineas.append(f"    classDef {tipo} {estilo}")
    lineas.append(f"    class {ids[CENTRAL]} central")
    for tipo in _ESTILOS:
        if del_tipo := [ids[c["id"]] for c in mapa["conceptos"] if c["tipo"] == tipo]:
            lineas.append(f"    class {','.join(del_tipo)} {tipo}")
    return "\n".join(lineas)


# ---------------------------------------------------------------- caché

def huella(bp: dict, nombre: str, contexto: str | None, modelo: str | None, solo: set[str] | None) -> str:
    """Cambia si cambia lo validado, el proyecto, el modelo o el protocolo."""
    datos = {"v": VERSION, "nodos": bp["nodos"], "aristas": bp["aristas"], "nombre": nombre, "contexto": contexto,
             "modelo": modelo, "solo": sorted(solo or [])}
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def id_guardado(proyecto_id: str, solo: set[str] | None) -> str:
    """Un mapa guardado por proyecto y selección (el repositorio pide letras y dígitos)."""
    h = hashlib.sha256(f"{proyecto_id}|{','.join(sorted(solo or []))}".encode()).hexdigest()
    return f"MC{int(h[:15], 16)}"


# ---------------------------------------------------------------- el protocolo completo

def _paso(id_: str, texto: str, estado: str = "curso", detalle: str | None = None) -> dict:
    return {"tipo": "paso", "id": id_, "texto": texto, "estado": estado, "detalle": detalle}


def generar_mapa(bp: dict, nombre: str, contexto: str | None, modelador) -> Iterator[dict]:
    """Recorre el protocolo y va avisando: {"tipo": "paso", …} por cada paso (primero en
    curso y luego terminado) y al final {"tipo": "mapa", "mapa": …}. Sin `modelador`
    (o si falla) el mapa queda en código y lo dice."""
    requisitos = [n for n in bp["nodos"] if n["tipo"] == "requisito"]
    yield _paso("reunir", "Reuniendo lo validado")
    yield _paso("reunir", "Reuniendo lo validado", "ok",
                f"{len(requisitos)} requisito{'s' if len(requisitos) != 1 else ''} · el grafo completo tiene "
                f"{len(bp['nodos'])} nodos y {len(bp['aristas'])} relaciones")

    yield _paso("conceptos", "Eligiendo los conceptos clave")
    conceptos, relaciones = candidatos(bp)
    yield _paso("conceptos", "Eligiendo los conceptos clave", "ok",
                f"{len(conceptos)} candidatos sin repetidos; el sistema es el concepto central")

    yield _paso("relaciones", "Proponiendo relaciones")
    para_llm, rel_llm = recortar(conceptos, relaciones, CANDIDATOS_LLM, LIMITE_PROPOSICIONES * 2, MAX_GRADO + 2)
    base_c, base_r = recortar(conceptos, relaciones)
    yield _paso("relaciones", "Proponiendo relaciones", "ok",
                f"{len(relaciones)} candidatas; las {len(rel_llm)} de más peso pasan al Modelador")

    mapa, aviso, modelo, version, descartadas = None, None, None, None, 0
    if modelador is None:
        aviso = "Sin Modelador: el mapa se armó en código."
    else:
        modelo = getattr(modelador.cliente, "modelo", None)
        texto = f"El Modelador organiza el mapa{f' ({modelo})' if modelo else ''}"
        yield _paso("modelador", texto, detalle="agrupa los conceptos en ramas y nombra cada relación")
        ids = {c["id"] for c in para_llm}
        try:
            r = modelador.mapear(
                nombre, contexto, [n["detalle"] or n["etiqueta"] for n in requisitos][:40],
                [{"id": c["id"], "etiqueta": c["etiqueta"], "tipo": c["tipo"], "peso": c["peso"]} for c in para_llm],
                [{"origen": x["origen"], "enlace": x["enlace"], "destino": x["destino"]} for x in rel_llm],
                LIMITE_CONCEPTOS, LIMITE_PROPOSICIONES, verificar=lambda s: verificar_mapa(s, ids))
            mapa, descartadas = del_modelador(r.valor, para_llm, rel_llm)
            version = r.prompt_version
            yield _paso("modelador", texto, "ok",
                        f"{len(r.valor.ramas)} ramas · {len(r.valor.proposiciones)} relaciones propuestas"
                        f"{' · necesitó un reintento' if r.hubo_reintento else ''}")
        except Exception as e:  # noqa: BLE001 — cualquier falla del LLM deja el mapa en código
            log.warning("El Modelador no armó el mapa conceptual: %s: %s", type(e).__name__, e)
            aviso = f"El Modelador no respondió bien ({type(e).__name__}): el mapa se armó en código."
            yield _paso("modelador", texto, "aviso", aviso)

    yield _paso("revision", "Revisando el mapa")
    if mapa is None or len(mapa["proposiciones"]) < 2:
        if mapa is not None:
            aviso = "La propuesta del Modelador quedó casi vacía: el mapa se armó en código."
        mapa = en_codigo(nombre, base_c, base_r)
        generado_por = "codigo"
    else:
        generado_por = "modelador"
    yield _paso("revision", "Revisando el mapa", "ok",
                f"{len(mapa['conceptos'])} conceptos · {len(mapa['proposiciones'])} relaciones"
                f"{f' · {descartadas} sin respaldo descartadas' if generado_por == 'modelador' and descartadas else ''}")

    mapa.update({
        "mermaid": a_mermaid(mapa),
        "generado_por": generado_por,
        "modelo": modelo if generado_por == "modelador" else None,
        "prompt_version": version if generado_por == "modelador" else None,
        "aviso": aviso,
        "requisitos": [n["id"] for n in requisitos],
        "grafo": {"nodos": len(bp["nodos"]), "aristas": len(bp["aristas"]), "candidatos": len(conceptos)},
    })
    yield {"tipo": "mapa", "mapa": mapa}
