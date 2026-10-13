"""Lo validado en las fases anteriores, como lo leen los agentes en las siguientes (ADR 0024).

Funciones puras: arman el texto de los prompts y verifican referencias (símbolos del LEL y
citas de la entrevista) sin LLM.
"""
from __future__ import annotations

from app.entrevistas import almacen as ea
from app.models import PATRON_CITA

from .claves import clave as clave_de
from .lexico import vigentes

CAMPOS_FICHA = ("problemas", "necesidades", "reglas")
SIN_HECHOS = "(la entrevista no dejó necesidades ni problemas anotados)"


def validadas(entradas: list[dict]) -> list[dict]:
    return sorted((e for e in vigentes(entradas) if e["estado"] in ("validado", "corregido")),
                  key=lambda e: e["simbolo"].lower())


def lel_en_texto(entradas: list[dict], detalle: bool = True) -> str:
    lineas = []
    for e in validadas(entradas):
        if detalle:
            lineas.append(f"- {e['simbolo']} ({e['tipo']}): {' '.join(e['nocion'])} · se busca: {e['intencion']}"
                          + (f" · implica: {' '.join(e['impacto'])}" if e["impacto"] else ""))
        else:
            lineas.append(f"- {e['simbolo']}: {e['nocion'][0]} · se busca: {e['intencion']}")
    return "\n".join(lineas) or "(sin términos validados)"


class Simbolos:
    """Reconoce los símbolos del LEL validado que mencionan los agentes («consultas» → «consulta»)."""

    def __init__(self, entradas: list[dict]):
        self.por_clave: dict[str, str] = {}
        for e in validadas(entradas):
            for k in e.get("claves") or [e["clave"]]:
                self.por_clave.setdefault(k, e["simbolo"])

    def __call__(self, texto: str | None) -> str | None:
        return self.por_clave.get(clave_de(texto or "")) if texto else None

    def filtrar(self, nombres: list[str]) -> tuple[list[str], list[str]]:
        """(los que están en el LEL, con su símbolo; los que no)."""
        buenos, malos = [], []
        for n in nombres:
            s = self(n)
            if s and s not in buenos:
                buenos.append(s)
            elif not s:
                malos.append(n)
        return buenos, malos

    def mencionados(self, texto: str) -> list[str]:
        """Los símbolos que aparecen en un texto (palabra por palabra, en singular)."""
        base = f" {clave_de(texto)} "
        return sorted({s for k, s in self.por_clave.items() if f" {k} " in base})


def entrevistas_listas(entrevistas: list[dict]) -> list[dict]:
    return [e for e in entrevistas if e["estado"] == ea.LISTA]


def citas_validas(entrevistas: list[dict]) -> set[str]:
    return {f"{e['entrevista_id']}:T{t['n']}" for e in entrevistas_listas(entrevistas) for t in e["turnos"]}


def filtrar_citas(citas: list[str], validas: set[str]) -> list[str]:
    salida = []
    for c in citas:
        c = c.strip().upper().replace(" ", "")
        if PATRON_CITA.match(c) and c in validas and c not in salida:
            salida.append(c)
    return salida


def hechos(entrevistas: list[dict]) -> dict:
    """Lo que anotó el Revisor de cada entrevista lista, con citas «E01:T3»."""
    salida: dict = {"objetivos": [], "participantes": [], **{c: [] for c in CAMPOS_FICHA}}
    for e in entrevistas_listas(entrevistas):
        f = e.get("ficha") or {}
        eid = e["entrevista_id"]
        if f.get("objetivo"):
            salida["objetivos"].append({"texto": f["objetivo"], "citas": [], "entrevista": eid})
        for p in f.get("participantes", []):
            salida["participantes"].append({**p, "entrevista": eid})
        for campo in CAMPOS_FICHA:
            for h in f.get(campo, []):
                salida[campo].append({"texto": h["texto"], "citas": [f"{eid}:T{n}" for n in h.get("turnos", [])],
                                      "entrevista": eid})
    return salida


def hechos_en_texto(h: dict, campos=("objetivos", *CAMPOS_FICHA), limite: int = 40) -> str:
    nombres = {"objetivos": "Objetivo", "problemas": "Problema", "necesidades": "Necesidad", "reglas": "Regla"}
    lineas = []
    for campo in campos:
        for x in h.get(campo, []):
            citas = f" [{', '.join(x['citas'])}]" if x.get("citas") else ""
            lineas.append(f"- {nombres[campo]}: {x['texto']}{citas}")
    return "\n".join(lineas[:limite]) or SIN_HECHOS


def proposiciones_en_texto(mapa: dict | None) -> tuple[str, str]:
    """(propósito, proposiciones «a — enlace → b») del mapa validado."""
    if not mapa:
        return "(sin mapa)", "(sin proposiciones)"
    c = mapa["contenido"]
    etiqueta = {x["id"]: x["etiqueta"] for x in c["conceptos"]}
    props = [f"- {etiqueta[r['origen']]} — {r['enlace']} → {etiqueta[r['destino']]}" for r in c["relaciones"]
             if r["origen"] in etiqueta and r["destino"] in etiqueta]
    return c["proposito"], "\n".join(props) or "(sin proposiciones)"
