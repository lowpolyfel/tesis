"""Arma la respuesta de la calibración a partir de trazas y etiquetas ya leídas (ADR 0013).

Función pura: la ruta lee el repositorio y la configuración y delega aquí.
Nada de esto escribe la configuración ni vuelve a calcular similitudes.
"""
from __future__ import annotations

from typing import Iterable

from app.models import Traza

from .ground_truth import contrastar, seleccionar_etiquetas
from .sensibilidad import distribucion, extraer_similitudes, rejilla, reprocesados, sensibilidad

NOTA = ("Análisis de sensibilidad: qué habría decidido la regla «similitud >= umbral» con otros umbrales, "
        "sobre las similitudes iniciales (ronda 0) ya calculadas. No cambia la configuración, no recalcula "
        "embeddings y no predice cómo habría terminado un debate. El umbral no se ajusta para que los casos "
        "salgan bien: si la similitud no separa los casos, es un hallazgo.")


def _marcar(filas: list[dict], umbral_configurado: float) -> list[dict]:
    """Agrega `configurado` después de `umbral`: la fila que reproduce lo que pasó."""
    return [{"umbral": f["umbral"], "configurado": f["umbral"] == umbral_configurado,
             **{k: v for k, v in f.items() if k != "umbral"}} for f in filas]


def _avisos(valores: list[dict], modelos: list[str], umbrales_usados: list[float], umbral_configurado: float,
            con_ground_truth: dict | None) -> list[str]:
    avisos = []
    if not valores:
        avisos.append("sin similitudes calculadas: ningún término con interpretaciones llegó al mecanismo "
                      "de divergencia")
    if len(modelos) > 1:
        avisos.append(f"las similitudes vienen de {len(modelos)} modelos de embeddings distintos "
                      f"({', '.join(modelos)}): no son comparables entre sí")
    otros = [u for u in umbrales_usados if u != umbral_configurado]
    if otros:
        avisos.append(f"hay términos decididos con un umbral distinto del configurado ({', '.join(map(str, otros))}): "
                      "decision_real es la que se tomó con el umbral de su traza")
    if con_ground_truth and con_ground_truth["separacion"]["separa"] is False:
        avisos.append("con las etiquetas, la similitud no separa los casos: ningún umbral manda a debate a todos los "
                      "ambiguos y solo a ellos. Es un hallazgo, no un motivo para mover el umbral")
    return avisos


def informe_calibracion(trazas: Iterable[Traza], docs_evaluacion: Iterable[dict], *, umbral_configurado: float,
                        max_rondas: int, desde: float, hasta: float, paso: float,
                        proyecto_id: str | None = None) -> dict:
    """Forma: `formas.Calibracion`::

        {proyecto_id, umbral_configurado, max_rondas, parametros{desde, hasta, paso},
         n_valores, valores, umbrales_usados, modelos_embeddings, reprocesados,
         distribucion, rejilla: [{umbral, configurado, directos, debates, cambian}],
         con_ground_truth | null, avisos, nota}

    `docs_evaluacion` son los documentos de `evaluaciones` de los proyectos que
    entran; el histograma usa `paso` como ancho y `desde` como origen, para que
    sus bordes coincidan con los umbrales de la rejilla.
    """
    trazas = list(trazas)
    valores = extraer_similitudes(trazas)
    umbrales = rejilla(desde, hasta, paso, incluir=umbral_configurado)
    umbrales_usados = sorted({v["umbral_usado"] for v in valores if v["umbral_usado"] is not None})
    modelos = sorted({v["modelo_embeddings"] for v in valores if v["modelo_embeddings"]})

    fuentes, etiquetas, invalidas = seleccionar_etiquetas(docs_evaluacion)
    con_ground_truth = None
    if etiquetas or invalidas:
        c = contrastar(valores, etiquetas, umbrales)
        con_ground_truth = {"fuentes": fuentes, "n_invalidas": invalidas,
                            **{**c, "por_umbral": _marcar(c["por_umbral"], umbral_configurado)}}

    return {
        "proyecto_id": proyecto_id,
        "umbral_configurado": umbral_configurado,
        "max_rondas": max_rondas,
        "parametros": {"desde": desde, "hasta": hasta, "paso": paso},
        "n_valores": len(valores),
        "valores": valores,
        "umbrales_usados": umbrales_usados,
        "modelos_embeddings": modelos,
        "reprocesados": sorted(reprocesados(trazas) & {t.req_id for t in trazas}, key=lambda r: (len(r), r)),
        "distribucion": distribucion(valores, paso, origen=desde),
        "rejilla": _marcar(sensibilidad(valores, umbrales), umbral_configurado),
        "con_ground_truth": con_ground_truth,
        "avisos": _avisos(valores, modelos, umbrales_usados, umbral_configurado, con_ground_truth),
        "nota": NOTA,
    }
