"""Corpus temporales y guiones de LLM falso por texto de requisito, con resultados conocidos.

Escenario de cuatro requisitos (los números esperados se calculan a mano en las pruebas):

A  «sesión»: ambiguo léxico. Sistema: interpretaciones ortogonales → debate → consenso.
   Línea base: «sesión», léxica.
B  «jalar ahorita»: ambiguo léxico, regional y vago. Sistema: el Clasificador dice que
   «jalar» es unívoco (no hay debate); «ahorita» lo marca el catálogo de vaguedad.
   Línea base: no ambiguo.
C  «Todos los usuarios no…»: ambiguo de alcance. Sistema: el detector lo encuentra, el
   Clasificador lo tipa como sintáctico con paráfrasis cercanas → aceptado directo.
   Línea base: «usuarios», alcance (se empareja por contención).
D  «comprobante»: sin ambigüedad. Sistema: lo declara ambiguo con interpretaciones
   ortogonales → debate de más. Línea base: falla dos veces (salida inválida).
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.escenarios import EXTRACCION_SESION, I1, I2, P1, P2, SESION, clasificacion
from tests.fakes import interp, r3_todas

A = SESION
B = "El sistema debe jalar ahorita los datos del inventario."
C = "Todos los usuarios no deben tener acceso al módulo de nómina."
D = "El cajero debe imprimir el comprobante de pago al cerrar la venta."

REQUISITOS = [{"id": "A", "texto": A}, {"id": "B", "texto": B}, {"id": "C", "texto": C}, {"id": "D", "texto": D}]
GROUND_TRUTH = [
    {"id": "A", "ambiguo": True, "terminos": [
        {"termino": "sesión", "tipo_ambiguedad": "lexica",
         "interpretaciones_validas": ["periodo de uso", "evento de conexión"], "interpretacion_esperada": "periodo de uso"}],
     "vaguedad": [], "regionales": [], "notas": None},
    {"id": "B", "ambiguo": True, "terminos": [
        {"termino": "jalar", "tipo_ambiguedad": "lexica",
         "interpretaciones_validas": ["consultar", "descargar", "procesar"], "interpretacion_esperada": None}],
     "vaguedad": ["ahorita"], "regionales": ["jalar"], "notas": None},
    {"id": "C", "ambiguo": True, "terminos": [
        {"termino": "todos los usuarios", "tipo_ambiguedad": "alcance",
         "interpretaciones_validas": ["ninguno", "no todos"], "interpretacion_esperada": None}],
     "vaguedad": [], "regionales": [], "notas": None},
    {"id": "D", "ambiguo": False, "terminos": [], "vaguedad": [], "regionales": [], "notas": "sin ambigüedad"},
]

C1 = interp("I1", "ningún usuario", "Ningún usuario debe tener acceso al módulo de nómina.")
C2 = interp("I2", "no todos los usuarios", "No todos los usuarios deben tener acceso al módulo de nómina.")
D1 = interp("I1", "comprobante impreso", P1)
D2 = interp("I2", "comprobante electrónico", P2)

EXTRACCION = {
    A: EXTRACCION_SESION,
    B: {"terminos": [{"termino": "sistema", "categoria_tentativa": "sujeto"},
                     {"termino": "datos", "categoria_tentativa": "objeto"}]},
    C: {"terminos": []},
    D: {"terminos": [{"termino": "comprobante", "categoria_tentativa": "objeto"}]},
}
CLASIFICACION = {
    A: clasificacion(I1, I2),
    B: {"resultados": [{"termino": t, "univoco": True} for t in ("sistema", "jalar", "datos")]},
    C: {"resultados": [{"termino": "Todos los usuarios", "tipo_ambiguedad": "sintactica", "interpretaciones": [C1, C2]}]},
    D: {"resultados": [{"termino": "comprobante", "tipo_ambiguedad": "lexica", "interpretaciones": [D1, D2]}]},
}
LINEA_BASE = {
    A: {"ambiguo": True, "terminos": [{"termino": "sesión", "tipo_ambiguedad": "lexica",
                                       "interpretacion_elegida": "periodo de uso"}]},
    B: {"ambiguo": False, "terminos": []},
    C: {"ambiguo": True, "terminos": [{"termino": "usuarios", "tipo_ambiguedad": "alcance",
                                       "interpretacion_elegida": "ningún usuario"}]},
    D: "esto no es JSON",
}


def texto_de(prompt) -> str:
    """El requisito va entre «» al inicio de la sección de usuario de cada prompt."""
    return prompt.usuario.split("«", 1)[1].split("»", 1)[0]


def retirar_las_demas(prompt) -> dict:
    """Refinamiento: conserva I1 tal cual y retira las demás."""
    bloque = prompt.usuario.split("Interpretaciones actuales:\n", 1)[1].split("\n\nObjeciones del Crítico:", 1)[0]
    interps = json.loads(bloque)
    return {"interpretaciones": [interps[0]],
            "retiradas": [{"interpretacion_id": i["id"], "motivo": "objeción aceptada"} for i in interps[1:]]}


def guiones() -> dict:
    return {
        "extractor_v1": lambda p: EXTRACCION[texto_de(p)],
        "clasificador_v2": lambda p: CLASIFICACION[texto_de(p)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": retirar_las_demas,
        "agente_unico_v1": lambda p: LINEA_BASE[texto_de(p)],
    }


def escribir_corpus(raiz: Path, nombre: str, requisitos: list[dict] | None = None, ground_truth: list[dict] | None = None,
                    *, descripcion: dict | None = None, crudo_requisitos: str | None = None,
                    crudo_ground_truth: str | None = None) -> Path:
    d = Path(raiz) / nombre
    d.mkdir(parents=True, exist_ok=True)
    lineas = lambda filas: "\n".join(json.dumps(f, ensure_ascii=False) for f in filas) + "\n"  # noqa: E731
    (d / "requisitos.jsonl").write_text(crudo_requisitos if crudo_requisitos is not None
                                        else lineas(REQUISITOS if requisitos is None else requisitos), encoding="utf-8")
    (d / "ground_truth.jsonl").write_text(crudo_ground_truth if crudo_ground_truth is not None
                                          else lineas(GROUND_TRUTH if ground_truth is None else ground_truth),
                                          encoding="utf-8")
    if descripcion is not None:
        (d / "corpus.json").write_text(json.dumps(descripcion, ensure_ascii=False), encoding="utf-8")
    return d
