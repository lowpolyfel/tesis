"""Qué requisitos entran a los artefactos del proyecto (ADR 0011).

Entra cada requisito `formalizado` con su documento de `formalizados`. Quedan
fuera, con su motivo: los que siguen en proceso, los rechazados, los que
terminaron en error, los formalizados antes de que existiera el documento por
requisito (ADR 0010) y los que una versión más nueva y vigente vuelve a procesar
(`origen.reproceso_de`). La cadena se sigue hacia atrás, como en la calibración
(ADR 0013): R01 → R02 que falló → R03 deja fuera a R01.
"""
from __future__ import annotations

from app.models import Estado

from .terminos import numero_req

_EXCLUIDOS = {Estado.RECHAZADO.value: "rechazado", Estado.ERROR.value: "error"}


def _reproceso_de(resumen: dict) -> str | None:
    origen = resumen.get("origen") or {}
    return origen.get("reproceso_de") if isinstance(origen, dict) else getattr(origen, "reproceso_de", None)


def _orden(req_id: str) -> tuple[int, str]:
    return numero_req(req_id), req_id


def ordenar(formalizados: list[dict]) -> list[dict]:
    return sorted(formalizados, key=lambda d: _orden(d["req_id"]))


def reprocesados(trazas_resumen: list[dict]) -> dict[str, str]:
    """{req_id: versión vigente más nueva que lo vuelve a procesar}.

    Vigente = ni en error ni rechazada. Desde cada versión vigente se sigue
    `reproceso_de` hacia atrás, pasando por las versiones intermedias aunque estén en
    error o rechazadas. Solo se sustituye a requisitos anteriores (un reproceso
    siempre es un requisito nuevo): una referencia a sí mismo o circular no deja
    fuera a todos los de la cadena."""
    trazas = sorted(trazas_resumen, key=lambda t: _orden(t["req_id"]))
    anterior = {t["req_id"]: r for t in trazas if (r := _reproceso_de(t))}
    sustituido_por: dict[str, str] = {}
    for t in trazas:  # de la más antigua a la más nueva: gana la versión más reciente
        if t.get("estado") in _EXCLUIDOS:
            continue
        r, vistos = anterior.get(t["req_id"]), set()
        while r is not None and r not in vistos and _orden(r) < _orden(t["req_id"]):
            vistos.add(r)
            sustituido_por[r] = t["req_id"]
            r = anterior.get(r)
    return sustituido_por


def seleccionar(formalizados: list[dict], trazas_resumen: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """(documentos que entran, requisitos fuera [{req_id, estado, motivo, detalle}]).

    Sin `trazas_resumen` entran todos los documentos dados."""
    if trazas_resumen is None:
        return ordenar(formalizados), []
    docs = {d["req_id"]: d for d in formalizados}
    reprocesado_en = reprocesados(trazas_resumen)

    dentro, fuera = [], []
    for t in sorted(trazas_resumen, key=lambda t: _orden(t["req_id"])):
        req_id, estado = t["req_id"], t.get("estado")
        if estado in _EXCLUIDOS:
            fuera.append({"req_id": req_id, "estado": estado, "motivo": _EXCLUIDOS[estado], "detalle": None})
        elif req_id in reprocesado_en:
            fuera.append({"req_id": req_id, "estado": estado, "motivo": "reprocesado",
                          "detalle": f"lo vuelve a procesar {reprocesado_en[req_id]}"})
        elif estado != Estado.FORMALIZADO.value:
            fuera.append({"req_id": req_id, "estado": estado, "motivo": "en_proceso", "detalle": None})
        elif req_id not in docs:
            fuera.append({"req_id": req_id, "estado": estado, "motivo": "sin_formalizacion",
                          "detalle": "formalizado antes del documento por requisito (ADR 0010)"})
        else:
            dentro.append(docs[req_id])
    conocidos = {t["req_id"] for t in trazas_resumen}
    fuera += [{"req_id": d["req_id"], "estado": None, "motivo": "sin_traza", "detalle": None}
              for d in ordenar(formalizados) if d["req_id"] not in conocidos]
    return dentro, fuera
