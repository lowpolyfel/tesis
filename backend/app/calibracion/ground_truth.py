"""Contraste del umbral contra el ground truth del corpus (ADR 0013).

Las etiquetas las escribe el módulo de evaluación en la colección `evaluaciones`
(un documento por corrida con `proyecto_id` y `etiquetas`). Aquí solo se leen:
la clase positiva es «debate» (similitud < umbral) y la verdad es `ambiguo`.
"""
from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.divergence.similitud import decidir
from app.models import Estado
from app.nlp import normalizar

from .sensibilidad import redondear

COLECCION_EVALUACIONES = "evaluaciones"


class Etiqueta(BaseModel):
    """Contrato fijo con el módulo de evaluación: qué término de qué requisito es ambiguo."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    req_id: str = Field(min_length=1)
    termino: str = Field(min_length=1)
    ambiguo: bool
    tipo_ambiguedad: str | None = None


def clave(req_id: str, termino: str) -> tuple[str, str]:
    """Una etiqueta y una similitud se emparejan por requisito y término normalizado."""
    return req_id, normalizar(termino)


def seleccionar_etiquetas(docs: Iterable[dict]) -> tuple[list[dict], list[dict], int]:
    """De los documentos de `evaluaciones`, el último con `etiquetas` de cada proyecto.

    Devuelve `(fuentes, etiquetas, n_invalidas)`: `fuentes` es
    `[{proyecto_id, evaluacion_id, n_etiquetas}]`; las etiquetas que no cumplen el
    contrato se cuentan y se dejan fuera. Si dos etiquetas tienen la misma clave,
    cuenta la última.
    """
    ultimo: dict[str, dict] = {}
    for d in docs:
        if isinstance(d.get("etiquetas"), list) and d.get("proyecto_id"):
            ultimo[d["proyecto_id"]] = d  # la lista viene ordenada por id: gana la corrida más reciente
    fuentes, por_clave, invalidas = [], {}, 0
    for proyecto_id, d in sorted(ultimo.items()):
        validas = 0
        for e in d["etiquetas"]:
            try:
                et = Etiqueta.model_validate({k: e.get(k) for k in Etiqueta.model_fields} if isinstance(e, dict) else e)
            except ValidationError:
                invalidas += 1
                continue
            validas += 1
            por_clave[clave(et.req_id, et.termino)] = et.model_dump()
        fuentes.append({"proyecto_id": proyecto_id, "evaluacion_id": d.get("evaluacion_id"), "n_etiquetas": validas})
    return fuentes, list(por_clave.values()), invalidas


def _proporcion(a: int, b: int) -> float | None:
    return redondear(a / b) if b else None


def metricas(vp: int, fp: int, vn: int, fn: int) -> dict:
    """Precisión, exhaustividad (recall) y F1 de «debate» contra «ambiguo»;
    `null` cuando el denominador es cero (p. ej. ningún debate)."""
    precision, exhaustividad = _proporcion(vp, vp + fp), _proporcion(vp, vp + fn)
    f1 = None if precision is None or exhaustividad is None else _proporcion(2 * vp, 2 * vp + fp + fn)
    return {"vp": vp, "fp": fp, "vn": vn, "fn": fn, "precision": precision, "exhaustividad": exhaustividad, "f1": f1}


def contrastar(valores: list[dict], etiquetas: list[dict], umbrales: Iterable[float]) -> dict:
    """Matriz de confusión y métricas por umbral, y si la similitud separa los casos::

        {n_etiquetas, n_emparejados, n_ambiguos, n_no_ambiguos,
         etiquetas_sin_similitud: [{req_id, termino, ambiguo, tipo_ambiguedad}],
         valores_sin_etiqueta: [{req_id, termino, similitud}],
         separacion: {max_ambiguos, min_no_ambiguos, separa},
         por_umbral: [{umbral, vp, fp, vn, fn, precision, exhaustividad, f1,
                       mal_separados: [{req_id, termino, similitud, ambiguo,
                                        decision_con_umbral, tipo_error}]}]}

    Solo cuentan los pares emparejados. Una etiqueta sin similitud es un término
    que nunca llegó al umbral (unívoco, filtrado, vaguedad, requisito en error…):
    ningún umbral puede corregirla y se informa aparte. `separa` es verdadero si
    existe un umbral que manda a debate todos los ambiguos y a ninguno de los
    otros (máximo de los ambiguos < mínimo de los no ambiguos); `null` si falta
    una de las dos clases.
    """
    por_clave = {clave(e["req_id"], e["termino"]): e for e in etiquetas}
    claves_valores = {clave(v["req_id"], v["termino"]) for v in valores}
    pares = [(v, por_clave[k]) for v in valores if (k := clave(v["req_id"], v["termino"])) in por_clave]

    ambiguos = [v["similitud"] for v, e in pares if e["ambiguo"]]
    no_ambiguos = [v["similitud"] for v, e in pares if not e["ambiguo"]]
    max_amb, min_no = (max(ambiguos) if ambiguos else None), (min(no_ambiguos) if no_ambiguos else None)

    por_umbral = []
    for u in umbrales:
        vp = fp = vn = fn = 0
        mal = []
        for v, e in pares:
            decision = decidir(v["similitud"], u)
            debate = decision == Estado.EN_DEBATE
            if debate and e["ambiguo"]:
                vp += 1
            elif not debate and not e["ambiguo"]:
                vn += 1
            else:
                fp, fn = (fp + 1, fn) if debate else (fp, fn + 1)
                mal.append({"req_id": v["req_id"], "termino": v["termino"], "similitud": v["similitud"],
                            "ambiguo": e["ambiguo"], "decision_con_umbral": decision.value,
                            "tipo_error": "falso_positivo" if debate else "falso_negativo"})
        por_umbral.append({"umbral": u, **metricas(vp, fp, vn, fn), "mal_separados": mal})

    return {
        "n_etiquetas": len(por_clave),
        "n_emparejados": len(pares),
        "n_ambiguos": len(ambiguos),
        "n_no_ambiguos": len(no_ambiguos),
        "etiquetas_sin_similitud": [{"req_id": e["req_id"], "termino": e["termino"], "ambiguo": e["ambiguo"],
                                     "tipo_ambiguedad": e.get("tipo_ambiguedad")}
                                    for k, e in por_clave.items() if k not in claves_valores],
        "valores_sin_etiqueta": [{"req_id": v["req_id"], "termino": v["termino"], "similitud": v["similitud"]}
                                 for v in valores if clave(v["req_id"], v["termino"]) not in por_clave],
        "separacion": {"max_ambiguos": max_amb, "min_no_ambiguos": min_no,
                       "separa": (max_amb < min_no) if ambiguos and no_ambiguos else None},
        "por_umbral": por_umbral,
    }
