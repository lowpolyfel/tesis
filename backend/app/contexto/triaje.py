"""Triaje de requisitos contra la ficha del contexto (ADR 0022).

Antes de analizar, cada requisito se clasifica:

- claro       se entiende con el contexto: va al análisis como siempre.
- ambiguo     se entiende qué pide, pero algo admite más de una interpretación o es vago: va al
              análisis con revisión humana obligatoria (el grafo se detiene en `humano`).
- incompleto  no se entiende sin inventar o no tiene que ver con el contexto: una persona
              lo precisa antes de analizarlo (o decide analizarlo así, con revisión).

Primero reglas en código (lo demasiado corto es incompleto sin preguntarle a nadie);
luego el Revisor, por tandas. Si el Revisor falla, el resultado lo dice y no inventa
veredictos.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

TANDA = 15  # requisitos por llamada al Revisor
MIN_PALABRAS = 4
SIN_FICHA = "(el proyecto no tiene contexto general: juzga solo si el requisito se entiende por sí mismo)"


def _corto(indice: int, texto: str) -> dict:
    return {"indice": indice, "veredicto": "incompleto",
            "motivo": f"Tiene menos de {MIN_PALABRAS} palabras: no dice qué se pide ni sobre qué.",
            "faltantes": ["qué se pide", "sobre qué"],
            "preguntas": ["¿Qué debe hacer el sistema exactamente?", "¿Quién lo hace y sobre qué dato?"],
            "terminos_ambiguos": [], "origen": "regla"}


def triar(requisitos: list[str], ficha_md: str | None, revisor, avance=None) -> dict:
    """{resultados: [{indice, veredicto, motivo, faltantes, preguntas, terminos_ambiguos, origen}],
    modelo, aviso}. `indice` desde 1, en el orden recibido; veredicto None si el Revisor falló."""
    resultados: dict[int, dict] = {}
    pendientes = []
    for i, texto in enumerate(requisitos, 1):
        if len(texto.split()) < MIN_PALABRAS:
            resultados[i] = _corto(i, texto)
        else:
            pendientes.append(i)
    modelo, aviso = None, None
    avisar = avance or (lambda _e: None)
    total = (len(pendientes) + TANDA - 1) // TANDA
    for k, inicio in enumerate(range(0, len(pendientes), TANDA), 1):
        tanda = pendientes[inicio:inicio + TANDA]
        evento = {"tipo": "tanda", "i": k, "total": total, "desde": tanda[0], "hasta": tanda[-1],
                  "requisitos": len(requisitos)}
        avisar({**evento, "estado": "curso"})
        try:
            r = revisor.triar(ficha_md or SIN_FICHA, [requisitos[i - 1] for i in tanda])
        except Exception as e:  # noqa: BLE001 — sin Revisor no se inventa un veredicto
            log.warning("El Revisor no hizo el triaje: %s: %s", type(e).__name__, e)
            aviso = f"El Revisor no respondió ({type(e).__name__}: {str(e)[:160]}). Revisa estos requisitos tú."
            for i in tanda:
                resultados[i] = {"indice": i, "veredicto": None, "motivo": "Sin revisar: el Revisor no respondió.",
                                 "faltantes": [], "preguntas": [], "terminos_ambiguos": [], "origen": None}
            avisar({**evento, "estado": "aviso"})
            continue
        modelo = r.modelo
        for x in r.valor.requisitos:
            global_i = tanda[x.indice - 1]
            resultados[global_i] = {**x.model_dump(mode="json"), "indice": global_i, "origen": "revisor"}
        avisar({**evento, "estado": "ok", "modelo": modelo,
                "cuenta": {v: sum(1 for x in resultados.values() if x["veredicto"] == v) for v in ("claro", "ambiguo", "incompleto")}})
    return {"resultados": [resultados[i] for i in range(1, len(requisitos) + 1)], "modelo": modelo, "aviso": aviso}
