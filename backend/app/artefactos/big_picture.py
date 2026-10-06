"""Big Picture del proyecto como grafo de conocimiento (CONTEXTO §7, ADR 0011).

Se arma en código, sin LLM, a partir de lo validado: los documentos de
`formalizados` (requisito reescrito, resoluciones y metas) y el LEL del
proyecto. Cada nodo y cada arista se puede rastrear a un campo de esos
documentos o a una coincidencia de texto comprobable.

    actor -persigue-> meta            meta -contribuye_a-> meta
    meta -deriva_de-> requisito       meta -usa-> símbolo
    requisito -resuelve-> símbolo     requisito -menciona-> símbolo
    símbolo -relacionado_con-> símbolo
    actor -relacionado_con-> símbolo (el actor es un sujeto del LEL)
"""
from __future__ import annotations

from app.models import EntradaLELFormalizada
from app.nlp import Analizador, normalizar

from .exportar import a_mermaid, a_plantuml
from .metas import construir, vaguedad_candidata
from .seleccion import seleccionar
from .simbolos import Simbolo, agrupar_lel, clave
from .terminos import Comparador, numero_req, separar_accion


def _reescrito(doc: dict) -> str:
    return (doc.get("requisito_reescrito") or "").strip() or doc.get("requisito_original") or ""


def _nodo(id_: str, tipo: str, etiqueta: str, req_ids: list[str], subtipo: str | None = None,
          detalle: str | None = None) -> dict:
    return {"id": id_, "tipo": tipo, "subtipo": subtipo, "etiqueta": etiqueta, "detalle": detalle, "req_ids": req_ids}


def _ordenados(req_ids) -> list[str]:
    return sorted(set(req_ids), key=lambda r: (numero_req(r), r))


class _Aristas(list):
    """Lista de aristas sin repetidas, en el orden en que se agregan."""

    def __init__(self):
        super().__init__()
        self._vistas: set[tuple[str, str, str]] = set()

    def unir(self, origen: str, destino: str, relacion: str) -> None:
        if (origen, destino, relacion) not in self._vistas:
            self._vistas.add((origen, destino, relacion))
            self.append({"origen": origen, "destino": destino, "relacion": relacion})


def _resueltos_por(doc: dict, simbolos: list[Simbolo]) -> set[str]:
    """Símbolos que vinieron de la formalización del requisito."""
    claves = {clave(s) for s in doc.get("entradas_lel") or []}
    return {s.id for s in simbolos
            if clave(s.simbolo) in claves or any(e.req_id == doc["req_id"] for e in s.entradas)}


def _terminos_resueltos(docs: list[dict], lel: list[EntradaLELFormalizada], fuera: list[dict]) -> list[dict]:
    salida = []
    for doc in docs:
        for r in doc.get("resoluciones") or []:
            salida.append({"termino": r.get("termino"), "significado": (r.get("interpretacion") or {}).get("significado", ""),
                           "via": r.get("via"), "tipo_ambiguedad": r.get("tipo_ambiguedad") or "lexica",
                           "cambio": r.get("cambio"), "req_id": doc["req_id"]})
    # requisitos formalizados antes del documento por requisito: sus términos solo están en el LEL
    anteriores = {f["req_id"] for f in fuera if f["motivo"] == "sin_formalizacion"}
    for e in sorted((e for e in lel if e.req_id in anteriores), key=lambda e: numero_req(e.req_id)):
        salida.append({"termino": e.termino, "significado": e.interpretacion.significado, "via": e.via.value,
                       "tipo_ambiguedad": "lexica", "cambio": "edicion" if e.editada_por_humano else None,
                       "req_id": e.req_id})
    return salida


def big_picture_proyecto(formalizados: list[dict], lel: list[EntradaLELFormalizada], trazas_resumen: list[dict] | None,
                         analizador: Analizador | None = None) -> dict:
    """{nodos, aristas, panorama, terminos_sin_simbolo, requisitos_fuera, mermaid,
    plantuml}. Forma: `formas.BigPicture`. Con `analizador` las coincidencias de
    texto también comparan lemas; sin él, solo la forma normalizada."""
    docs, fuera = seleccionar(formalizados, trazas_resumen)
    comp = Comparador(analizador)
    simbolos = agrupar_lel(lel)
    metas, actores = construir(docs, simbolos, comp)
    req_de_meta = {m["id"]: m["req_id"] for m in metas}
    simbolo_por_nombre = {s.simbolo: s for s in simbolos}

    nodos = [_nodo(d["req_id"], "requisito", d["req_id"], [d["req_id"]], detalle=_reescrito(d)) for d in docs]
    nodos += [_nodo(m["id"], m["tipo"], m["enunciado"], [m["req_id"]]) for m in metas]
    for g in actores:
        origen_lel = simbolo_por_nombre[g.simbolo_lel].req_ids if g.simbolo_lel else []
        nodos.append(_nodo(g.id, "actor", g.nombre, _ordenados([req_de_meta[m] for m in g.metas] + origen_lel)))
    nodos += [_nodo(s.id, "simbolo", s.simbolo, s.req_ids, subtipo=s.subtipo, detalle=s.nocion) for s in simbolos]

    aristas = _Aristas()
    id_actor = {g.nombre: g.id for g in actores}
    for m in metas:
        if m["actor"]:
            aristas.unir(id_actor[m["actor"]], m["id"], "persigue")
    for m in metas:
        if m["contribuye_a"]:
            aristas.unir(m["id"], m["contribuye_a"], "contribuye_a")
    for m in metas:
        aristas.unir(m["id"], m["req_id"], "deriva_de")

    sin_simbolo: dict[str, dict] = {}
    usan: dict[str, set[str]] = {s.id: set() for s in simbolos}  # símbolo → requisitos que lo usan
    for m in metas:
        for termino in m["simbolos"]:
            encontrados = [s for s in simbolos if any(comp.aparece(f, termino) for f in s.formas)]
            for s in encontrados:
                aristas.unir(m["id"], s.id, "usa")
                usan[s.id].add(m["req_id"])
            if not encontrados:
                sin_simbolo.setdefault(normalizar(termino), {"termino": termino, "metas": []})["metas"].append(m["id"])

    resueltos = {d["req_id"]: _resueltos_por(d, simbolos) for d in docs}
    for d in docs:
        for s in simbolos:
            if s.id in resueltos[d["req_id"]]:
                aristas.unir(d["req_id"], s.id, "resuelve")
                usan[s.id].add(d["req_id"])
    for d in docs:
        textos = [t for t in (d.get("requisito_original"), d.get("requisito_reescrito")) if t]
        for s in simbolos:
            if s.id not in resueltos[d["req_id"]] and any(comp.aparece(f, t) for f in s.formas for t in textos):
                aristas.unir(d["req_id"], s.id, "menciona")
                usan[s.id].add(d["req_id"])

    for a in simbolos:
        for b in simbolos:
            if a is not b and any(comp.aparece(f, t) for f in b.formas for t in a.textos):
                aristas.unir(a.id, b.id, "relacionado_con")
    for g in actores:
        if g.simbolo_lel:
            aristas.unir(g.id, simbolo_por_nombre[g.simbolo_lel].id, "relacionado_con")

    return {
        "nodos": nodos,
        "aristas": list(aristas),
        "panorama": _panorama(docs, metas, actores, simbolos, usan, lel, fuera, comp),
        "terminos_sin_simbolo": list(sin_simbolo.values()),
        "requisitos_fuera": fuera,
        "mermaid": a_mermaid(nodos, list(aristas)),
        "plantuml": a_plantuml(nodos, list(aristas), simbolos),
    }


def _panorama(docs, metas, actores, simbolos, usan, lel, fuera, comp) -> dict:
    acciones = []
    for m in metas:
        if m["tipo"] in ("meta", "tarea"):
            verbo, objeto = separar_accion(m["enunciado"])
            acciones.append({"actor": m["actor"], "verbo": verbo, "objeto": objeto, "req_id": m["req_id"], "meta": m["id"]})

    # una expresión vaga que ya recoge una meta blanda no se repite como restricción
    vagas = vaguedad_candidata(docs, metas, comp)
    restricciones = []
    for d in docs:
        restricciones += [{"texto": m["enunciado"], "req_id": m["req_id"], "origen": "meta_blanda", "meta": m["id"]}
                          for m in metas if m["req_id"] == d["req_id"] and m["tipo"] == "meta_blanda"]
        restricciones += [{"texto": v["texto"], "req_id": v["req_id"], "origen": "vaguedad", "meta": None}
                          for v in vagas if v["req_id"] == d["req_id"] and v["meta_blanda"] is None]

    # R03 depende de R01 si usa un símbolo que resolvió la formalización de R01
    dependencias = {}
    for s in simbolos:
        for de in usan[s.id]:
            for a in s.req_ids:
                if de != a:
                    dependencias[(numero_req(de), de, numero_req(a), a, normalizar(s.simbolo))] = {
                        "de": de, "a": a, "por": s.simbolo}
    return {
        "actores": [g.nombre for g in actores],
        "acciones": acciones,
        "restricciones": restricciones,
        "terminos_resueltos": _terminos_resueltos(docs, lel, fuera),
        "dependencias": [dependencias[k] for k in sorted(dependencias)],
        "requisitos": [{"req_id": d["req_id"], "requisito_reescrito": _reescrito(d)} for d in docs],
    }
