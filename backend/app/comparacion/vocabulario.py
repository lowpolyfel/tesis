"""Inconsistencias de vocabulario entre requisitos. Deterministas, sin LLM.

- LEL: el mismo símbolo (normalizado) con nociones distintas en requisitos distintos.
- Validación: el mismo término léxico validado con significados distintos.

Si un par de requisitos tiene las dos cosas para el mismo término, sale un solo
hallazgo de fuente `lel` que menciona también los significados.
"""
from __future__ import annotations

from itertools import combinations

from app.models import EntradaLELFormalizada
from app.nlp import normalizar

from .bases import SignificadoValidado, numero


def _clave(texto: str) -> str:
    """Minúsculas, sin acentos, sin espacios repetidos ni puntuación al final."""
    return " ".join(normalizar(texto).split()).strip(" .;,:")


def _agrupar(filas: list[tuple[str, str, str, str]]) -> dict[str, dict[str, dict]]:
    """[(clave, req_id, forma normalizada, texto visible)] → {clave: {req_id: {formas, texto}}}."""
    grupos: dict[str, dict[str, dict]] = {}
    for clave, req_id, forma, texto in filas:
        r = grupos.setdefault(clave, {}).setdefault(req_id, {"formas": set(), "texto": texto})
        r["formas"].add(forma)
    return grupos


def _pares_distintos(por_req: dict[str, dict]):
    for a, b in combinations(sorted(por_req, key=lambda r: (numero(r), r)), 2):
        if por_req[a]["formas"] != por_req[b]["formas"]:
            yield a, b


def inconsistencias_vocabulario(lel: list[EntradaLELFormalizada], significados: list[SignificadoValidado]) -> list[dict]:
    """Hallazgos `inconsistencia_vocabulario` sin id ni similitud (los completa quien llama)."""
    hallazgos: list[dict] = []
    por_termino: dict[tuple[str, str, str], dict] = {}  # (clave del término debatido, a, b) → hallazgo del LEL

    simbolos: dict[str, str] = {}  # clave → símbolo como aparece la primera vez
    for e in lel:
        simbolos.setdefault(_clave(e.simbolo), e.simbolo)
    terminos_lel: dict[tuple[str, str], set[str]] = {}
    for e in lel:
        terminos_lel.setdefault((_clave(e.simbolo), e.req_id), set()).add(_clave(e.termino))
    filas_lel = [(_clave(e.simbolo), e.req_id, "|".join(_clave(n) for n in e.nocion), " ".join(e.nocion)) for e in lel]
    for clave, por_req in _agrupar(filas_lel).items():
        for a, b in _pares_distintos(por_req):
            h = {"tipo": "inconsistencia_vocabulario", "requisitos": [a, b], "terminos": [simbolos[clave]],
                 "explicacion": f"El símbolo «{simbolos[clave]}» del LEL tiene nociones distintas en {a} y {b}.",
                 "evidencia": [{"req_id": r, "cita": por_req[r]["texto"], "verificada": True} for r in (a, b)],
                 "fuente": "lel", "modelo": None, "prompt_version": None}
            hallazgos.append(h)
            for t in terminos_lel[(clave, a)] & terminos_lel[(clave, b)] | {clave}:
                por_termino[(t, a, b)] = h

    filas_val = [(_clave(s.termino), s.req_id, _clave(s.significado), s.significado) for s in significados]
    visibles: dict[str, str] = {}
    for s in significados:
        visibles.setdefault(_clave(s.termino), s.termino)
    for clave, por_req in _agrupar(filas_val).items():
        for a, b in _pares_distintos(por_req):
            detalle = f"«{por_req[a]['texto']}» en {a} y «{por_req[b]['texto']}» en {b}"
            existente = por_termino.get((clave, a, b))
            if existente is not None:
                existente["explicacion"] += f" El significado validado también difiere: {detalle}."
                continue
            hallazgos.append({
                "tipo": "inconsistencia_vocabulario", "requisitos": [a, b], "terminos": [visibles[clave]],
                "explicacion": f"«{visibles[clave]}» quedó validado con significados distintos: {detalle}.",
                "evidencia": [{"req_id": r, "cita": por_req[r]["texto"], "verificada": True} for r in (a, b)],
                "fuente": "validacion", "modelo": None, "prompt_version": None})
    return hallazgos
