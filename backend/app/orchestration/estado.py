"""Estado tipado del grafo (ADR 0005).

Todo lo que viaja en el estado es JSON plano (dicts, listas, str, números): así el
checkpointer lo guarda sin depender de clases de Python, y la traza y el
checkpoint se pueden leer con cualquier herramienta. Los agentes reciben y
devuelven contratos Pydantic; la conversión ocurre en los nodos.
"""
from __future__ import annotations

from typing import Any, TypedDict


class TerminoEnProceso(TypedDict, total=False):
    """Un término candidato a lo largo del proceso."""

    termino: str
    categoria_tentativa: str
    origen: str  # extractor | regional | alcance | anafora
    detalle: str | None  # por qué es candidato (catálogo, antecedentes, patrón)
    univoco: bool
    tipo_ambiguedad: str | None  # TipoAmbiguedad; None si es unívoco
    interpretaciones: list[dict]  # vigentes (Interpretacion)
    todas: dict[str, dict]  # id → última versión de cada interpretación generada, incluidas las retiradas
    retiradas: list[dict]  # Retiro + ronda
    similitud: float | None
    decision: str | None  # aceptado_directo | en_debate | consenso | arbitrado (None si es unívoco)
    via: str | None  # Via
    propuesta: str | None  # id de la interpretación que se propone al humano
    historial: list[dict]  # RondaDebate
    justificacion: list[dict] | None  # arbitraje: JustificacionRegla
    final: dict | None  # interpretación validada por el humano
    cambio: str | None  # ninguno | eleccion | edicion


class EstadoGrafo(TypedDict, total=False):
    req_id: str
    proyecto_id: str
    texto: str
    estado: str  # Estado
    ronda: int
    lel: list[dict]  # EntradaLEL vigente al cargar el requisito (no cambia durante el proceso)
    terminos: list[dict]  # TerminoFiltrado: todos los términos con su decision_filtro
    candidatos: dict[str, TerminoEnProceso]  # los que pasaron al Clasificador, por término
    validacion: dict | None  # Validacion
    fallo: dict | None  # qué falló, si el caso terminó en error


def con_interpretaciones(candidatos: dict[str, TerminoEnProceso]) -> dict[str, TerminoEnProceso]:
    return {k: c for k, c in candidatos.items() if not c.get("univoco") and c.get("interpretaciones")}


def interpretacion_por_id(c: TerminoEnProceso, id_: str | None) -> dict[str, Any] | None:
    return c.get("todas", {}).get(id_) if id_ else None
