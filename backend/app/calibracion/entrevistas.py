"""Calibración sobre las entrevistas de la versión 2 (ADR 0026): de dónde salen las
similitudes y el ground truth.

- **Similitudes iniciales.** De la bitácora de cada entrevista (colección `bitacoras`,
  última corrida): por término, el mensaje `similitud` de ronda 0 con valor no nulo. Si un
  nodo se repitió tras una caída (ADR 0008), cuenta el último. La vía final sale de los
  mensajes posteriores (consenso o arbitraje) o de la propia decisión (aceptado directo).
- **Ground truth.** La persona anotadora marca, por entrevista, qué términos son ambiguos
  (colección `etiquetas_entrevista`, un documento por entrevista). Se empareja con las
  similitudes por entrevista y término normalizado, de forma literal, como en ADR 0014.

Funciones puras sobre documentos ya leídos: nada aquí llama a un LLM ni a los embeddings.
"""
from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from app.models import Estado
from app.nlp import normalizar

COLECCION_ETIQUETAS = "etiquetas_entrevista"
TIPOS = ("lexica", "alcance", "anaforica", "sintactica", "regional", "vaguedad")


def clave(entrevista_id: str, termino: str) -> tuple[str, str]:
    return entrevista_id, normalizar(termino)


def _numero(x) -> float | None:
    """Un número finito (el repositorio guarda NaN como null)."""
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float("inf") else None


def similitudes_de_entrevista(entrevista: dict, bitacora: dict) -> list[dict]:
    """Las similitudes iniciales de una entrevista, en el orden en que aparecieron::

        [{entrevista_id, proyecto_id, titulo, termino, similitud, umbral_usado, decision_real,
          tipo_ambiguedad, via, estado_entrevista, modelo_embeddings, modelo_clasificador}]

    `via` es null mientras el término se debate o si la entrevista se cortó antes de decidir.
    """
    eid = entrevista["entrevista_id"]
    tipos: dict[str, str | None] = {}
    clasificador: dict[str, str | None] = {}
    valores: dict[str, dict] = {}
    for m in bitacora.get("mensajes", []):
        p = m.get("payload") or {}
        if m["tipo"] == "interpretaciones":
            for r in p.get("resultados", []):
                k = normalizar(r.get("termino", ""))
                tipos[k] = r.get("tipo_ambiguedad")
                clasificador[k] = m.get("modelo")
        elif m["tipo"] == "similitud" and m.get("ronda", 0) == 0 and p.get("termino"):
            s = _numero(p.get("similitud"))
            if s is None:
                continue
            k = normalizar(p["termino"])
            decision = p.get("decision")
            valores.pop(k, None)  # un nodo repetido: cuenta el último mensaje
            valores[k] = {
                "entrevista_id": eid, "proyecto_id": entrevista.get("proyecto_id"), "titulo": entrevista.get("titulo"),
                "termino": p["termino"], "similitud": s, "umbral_usado": _numero(p.get("umbral")),
                "decision_real": decision if decision in (Estado.ACEPTADO_DIRECTO.value, Estado.EN_DEBATE.value) else None,
                "tipo_ambiguedad": tipos.get(k) or "lexica",  # sin tipo: léxica, como en ADR 0010
                "via": "aceptado_directo" if decision == Estado.ACEPTADO_DIRECTO.value else None,
                "estado_entrevista": entrevista.get("estado"),
                "modelo_embeddings": p.get("modelo_embeddings") or m.get("modelo"),
                "modelo_clasificador": clasificador.get(k),
            }
        elif m["tipo"] in ("consenso", "arbitraje") and p.get("termino"):
            v = valores.get(normalizar(p["termino"]))
            if v is not None:
                v["via"] = m["tipo"]
    return [v for v in valores.values() if v["decision_real"] is not None]


def terminos_de_entrevista(bitacora: dict) -> list[dict]:
    """Los términos que encontró el Extractor (el último mensaje `filtrado`), para etiquetar::

        [{termino, decision_filtro}]
    """
    filtrado = [m for m in bitacora.get("mensajes", []) if m["tipo"] == "filtrado"]
    if not filtrado:
        return []
    vistos, salida = set(), []
    for t in filtrado[-1]["payload"].get("terminos", []):
        k = normalizar(t.get("termino", ""))
        if k and k not in vistos:
            vistos.add(k)
            salida.append({"termino": t["termino"], "decision_filtro": t.get("decision_filtro")})
    return salida


class EtiquetaEntrevista(BaseModel):
    """Qué término de la entrevista es ambiguo, según la persona anotadora."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    termino: str = Field(min_length=1, max_length=120)
    ambiguo: bool
    tipo: str | None = Field(None, description="tipo de ambigüedad, si es ambiguo")
    nota: str | None = Field(None, max_length=500)


class EtiquetadoEntrevista(BaseModel):
    """Lo que se guarda de una entrevista: quién etiquetó, si lo hizo sin ver al sistema y las etiquetas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    anotador: str = Field(min_length=1, max_length=120)
    a_ciegas: bool = Field(True, description="etiquetó sin ver la similitud ni la decisión del sistema")
    etiquetas: list[EtiquetaEntrevista] = Field(default_factory=list, max_length=500)


def etiquetas_planas(docs: Iterable[dict]) -> list[dict]:
    """Las etiquetas de varios documentos de `etiquetas_entrevista`, una por entrevista y término
    (si un término se repite, cuenta la última)::

        [{entrevista_id, termino, ambiguo, tipo, a_ciegas, anotador}]
    """
    por_clave: dict[tuple[str, str], dict] = {}
    for d in docs:
        for e in d.get("etiquetas", []):
            por_clave[clave(d["entrevista_id"], e["termino"])] = {
                "entrevista_id": d["entrevista_id"], "termino": e["termino"], "ambiguo": bool(e["ambiguo"]),
                "tipo": e.get("tipo"), "a_ciegas": bool(d.get("a_ciegas")), "anotador": d.get("anotador")}
    return list(por_clave.values())
