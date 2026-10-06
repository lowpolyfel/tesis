"""Qué requisitos entran a los artefactos del proyecto (ADR 0011).

Entra cada requisito `formalizado` con su documento de `formalizados`. Quedan
fuera, con su motivo: los que siguen en proceso, los rechazados, los que
terminaron en error, los formalizados antes de que existiera el documento por
requisito (ADR 0010) y los que otro requisito vigente vuelve a procesar
(`origen.reproceso_de`, mismo criterio que la comparación, ADR 0012).
"""
from __future__ import annotations

from app.models import Estado

from .terminos import numero_req

_EXCLUIDOS = {Estado.RECHAZADO.value: "rechazado", Estado.ERROR.value: "error"}


def _reproceso_de(resumen: dict) -> str | None:
    origen = resumen.get("origen") or {}
    return origen.get("reproceso_de") if isinstance(origen, dict) else getattr(origen, "reproceso_de", None)


def ordenar(formalizados: list[dict]) -> list[dict]:
    return sorted(formalizados, key=lambda d: (numero_req(d["req_id"]), d["req_id"]))


def seleccionar(formalizados: list[dict], trazas_resumen: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """(documentos que entran, requisitos fuera [{req_id, estado, motivo, detalle}]).

    Sin `trazas_resumen` entran todos los documentos dados."""
    if trazas_resumen is None:
        return ordenar(formalizados), []
    docs = {d["req_id"]: d for d in formalizados}
    vigentes = [t for t in trazas_resumen if t.get("estado") not in _EXCLUIDOS]
    reprocesado_en = {r: t["req_id"] for t in vigentes if (r := _reproceso_de(t))}

    dentro, fuera = [], []
    for t in sorted(trazas_resumen, key=lambda t: (numero_req(t["req_id"]), t["req_id"])):
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
