"""Especificación del proyecto: requisitos funcionales y no funcionales (ADR 0017).

Se arma en código, sin LLM, desde los documentos de `formalizados`: el requisito
reescrito completo, el tipo y la categoría que asignó el Modelador (o que corrigió
una persona) y los supuestos que tomó del contexto del proyecto. Entran los mismos
requisitos que en el modelo de metas y el Big Picture (`seleccion`). Los
formalizados antes de que el Modelador clasificara quedan en `sin_clasificar`.
"""
from __future__ import annotations

from app.models import EntradaLELFormalizada, TipoRequisito

from .seleccion import seleccionar
from .simbolos import agrupar_lel

PREFIJOS = {TipoRequisito.FUNCIONAL.value: "RF", TipoRequisito.NO_FUNCIONAL.value: "RNF"}


def _marca(resumen: dict | None) -> str | None:
    origen = (resumen or {}).get("origen") or {}
    return origen.get("marca") if isinstance(origen, dict) else getattr(origen, "marca", None)


def especificacion_proyecto(formalizados: list[dict], lel: list[EntradaLELFormalizada],
                            trazas_resumen: list[dict] | None, solo: set[str] | None = None) -> dict:
    """{funcionales, no_funcionales, sin_clasificar, glosario, requisitos_fuera}.
    Cada requisito: {clave, req_id, marca, original, reescrito, tipo_requisito, categoria,
    supuestos, corregido}; `clave` numera por tipo en el orden del proyecto (RF-01, RNF-01).
    Forma: `formas.Especificacion`."""
    docs, fuera = seleccionar(formalizados, trazas_resumen)
    if solo is not None:
        docs, fuera = [d for d in docs if d["req_id"] in solo], [f for f in fuera if f["req_id"] in solo]
    resumen = {t["req_id"]: t for t in trazas_resumen or []}
    grupos: dict[str | None, list[dict]] = {TipoRequisito.FUNCIONAL.value: [], TipoRequisito.NO_FUNCIONAL.value: [], None: []}
    for d in docs:
        tipo = d.get("tipo_requisito") if d.get("tipo_requisito") in PREFIJOS else None
        lista = grupos[tipo]
        lista.append({
            "clave": f"{PREFIJOS[tipo]}-{len(lista) + 1:02d}" if tipo else d["req_id"],
            "req_id": d["req_id"], "marca": _marca(resumen.get(d["req_id"])),
            "original": d.get("requisito_original") or "",
            "reescrito": (d.get("requisito_reescrito") or "").strip() or d.get("requisito_original") or "",
            "tipo_requisito": tipo, "categoria": d.get("categoria") if tipo == TipoRequisito.NO_FUNCIONAL.value else None,
            "supuestos": list(d.get("supuestos") or []), "corregido": d.get("corregido"),
        })
    glosario = [{"simbolo": s.simbolo, "tipo": s.subtipo, "nocion": s.nocion, "req_ids": s.req_ids}
                for s in sorted(agrupar_lel(lel), key=lambda s: s.simbolo.lower())]
    return {
        "funcionales": grupos[TipoRequisito.FUNCIONAL.value],
        "no_funcionales": grupos[TipoRequisito.NO_FUNCIONAL.value],
        "sin_clasificar": grupos[None],
        "glosario": glosario,
        "requisitos_fuera": fuera,
    }
