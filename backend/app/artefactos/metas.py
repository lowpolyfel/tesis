"""Modelo de metas estratégicas del proyecto (CONTEXTO §7, ADR 0011).

Agrega en código, sin LLM, las metas que el Modelador derivó de cada requisito
validado (documento de `formalizados`, ADR 0010): ids globales, actores
normalizados y unidos con los sujetos del LEL, conteo por tipo y expresiones
vagas que son candidatas a metas blandas. No inventa metas ni actores.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import EntradaLELFormalizada
from app.nlp import Analizador, normalizar

from .seleccion import ordenar, seleccionar
from .simbolos import Simbolo, agrupar_lel
from .terminos import Comparador, nombre_actor, numero_meta

TIPOS_META = ("meta", "meta_blanda", "tarea", "recurso")


@dataclass
class GrupoActor:
    nombre: str
    simbolo_lel: str | None
    variantes: list[str]  # formas contra las que se compara un actor nuevo
    metas: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "actor:" + "_".join(normalizar(self.nombre).split())


def id_global(req_id: str, meta_id: str) -> str:
    return f"{req_id}.{meta_id}"


def _metas_del_doc(doc: dict) -> list[dict]:
    """Metas del documento en orden de id; una meta sin id o con id repetido no
    podría ser un nodo del grafo y se omite (el contrato del Modelador ya lo impide)."""
    unicas: dict[str, dict] = {}
    for m in doc.get("metas") or []:
        if m.get("id") and m["id"] not in unicas:
            unicas[m["id"]] = m
    return sorted(unicas.values(), key=lambda m: numero_meta(m["id"]))


def construir(docs: list[dict], simbolos: list[Simbolo], comp: Comparador) -> tuple[list[dict], list[GrupoActor]]:
    """(metas con id global, actores). Los sujetos del LEL abren los grupos de
    actores (su escritura manda); un actor de una meta se une al primer grupo
    con el que coincide por forma o lema, sin artículo."""
    grupos = [GrupoActor(nombre=s.simbolo, simbolo_lel=s.simbolo, variantes=[nombre_actor(f) for f in s.formas])
              for s in simbolos if s.subtipo == "sujeto"]

    def grupo_de(actor: str) -> GrupoActor:
        # se compara ya sin mayúscula inicial: spaCy toma «Usuarios» como nombre propio y no lo lematiza
        limpio = nombre_actor(actor)
        for g in grupos:
            if any(comp.mismo(limpio, v) for v in g.variantes):
                return g
        g = GrupoActor(nombre=limpio, simbolo_lel=None, variantes=[limpio])
        grupos.append(g)
        return g

    metas = []
    for doc in ordenar(docs):
        req_id = doc["req_id"]
        locales = {m.get("id") for m in _metas_del_doc(doc)}
        for m in _metas_del_doc(doc):
            mid = id_global(req_id, m["id"])
            original = (m.get("actor") or "").strip() or None
            g = grupo_de(original) if original else None
            if g is not None:
                g.metas.append(mid)
            destino = m.get("contribuye_a")
            metas.append({
                "id": mid, "req_id": req_id, "enunciado": m.get("enunciado", ""), "tipo": m.get("tipo"),
                "actor": g.nombre if g else None, "actor_original": original,
                "simbolos": list(dict.fromkeys(t.strip() for t in m.get("simbolos") or [] if t and t.strip())),
                # el contrato del Modelador solo permite apuntar a otra meta del mismo requisito
                "contribuye_a": id_global(req_id, destino) if destino in locales and destino != m["id"] else None,
            })
    return metas, sorted(grupos, key=lambda g: (normalizar(g.nombre), g.nombre))


def vaguedad_candidata(docs: list[dict], metas: list[dict], comp: Comparador) -> list[dict]:
    """Expresiones vagas de cada requisito y la meta blanda que ya las recoge, si la hay."""
    salida = []
    for doc in ordenar(docs):
        blandas = [m for m in metas if m["req_id"] == doc["req_id"] and m["tipo"] == "meta_blanda"]
        vistas = set()
        for texto in doc.get("vaguedad") or []:
            if normalizar(texto) in vistas:
                continue
            vistas.add(normalizar(texto))
            recoge = next((m["id"] for m in blandas
                           if comp.aparece(texto, m["enunciado"]) or any(comp.mismo(texto, s) for s in m["simbolos"])), None)
            salida.append({"texto": texto, "req_id": doc["req_id"], "meta_blanda": recoge})
    return salida


def metas_proyecto(formalizados: list[dict], lel: list[EntradaLELFormalizada],
                   trazas_resumen: list[dict] | None = None, analizador: Analizador | None = None) -> dict:
    """{metas, actores, por_tipo, metas_blandas_desde_vaguedad, sin_actor,
    requisitos_fuera}. Forma: `formas.MetasProyecto`."""
    docs, fuera = seleccionar(formalizados, trazas_resumen)
    comp = Comparador(analizador)
    metas, actores = construir(docs, agrupar_lel(lel), comp)
    return {
        "metas": metas,
        "actores": [{"nombre": g.nombre, "simbolo_lel": g.simbolo_lel, "metas": g.metas} for g in actores],
        "por_tipo": {t: sum(m["tipo"] == t for m in metas) for t in TIPOS_META},
        "metas_blandas_desde_vaguedad": vaguedad_candidata(docs, metas, comp),
        "sin_actor": [m["id"] for m in metas if m["actor"] is None],
        "requisitos_fuera": fuera,
    }


def artefactos_requisito(req_id: str, proyecto_id: str, estado: str, formalizado: dict | None,
                         lel: list[EntradaLELFormalizada], analizador: Analizador | None = None) -> dict:
    """{req_id, proyecto_id, estado, formalizado, entradas_lel, metas}: el documento
    formalizado tal cual, las entradas del LEL que salieron de este requisito y sus
    metas con id global (actores nombrados contra los sujetos del LEL del proyecto).
    Forma: `formas.ArtefactosRequisito`."""
    metas, _ = construir([formalizado] if formalizado else [], agrupar_lel(lel), Comparador(analizador))
    return {
        "req_id": req_id, "proyecto_id": proyecto_id, "estado": estado, "formalizado": formalizado,
        "entradas_lel": [e.model_dump(mode="json") for e in lel if e.req_id == req_id],
        "metas": metas,
    }
