"""Estabilidad entre corridas idénticas de la prueba de modelos (ADR 0029).

Una **serie** son N pruebas con la misma configuración sobre el mismo banco (mismos modelos,
términos, prompt, temperatura y semilla). Con temperatura 0 y semilla fija Ollama debería repetir
exactamente; la API de Google no garantiza determinismo. Esto no se explica de palabra: se mide.

Por modelo y por corrida: cuántos ambiguos detectó (y la exhaustividad), las falsas alarmas y la
detección por clase; y el rango (mínimo y máximo) de la detección en la serie. Funciones puras.
"""
from __future__ import annotations

from .pruebas_modelos import banco_de, codigo_de, es_ambiguo, etiqueta_modelo

CAMPOS_IGUALES = ("prompt", "temperatura", "semilla", "significado_max_palabras")


def firma(prueba: dict) -> tuple:
    """Lo que debe coincidir para que dos corridas sean «la misma configuración»."""
    cfg = prueba.get("configuracion") or {}
    return (tuple(cfg.get(k) for k in CAMPOS_IGUALES), (prueba.get("banco") or {}).get("huella"),
            tuple(prueba["items"]), tuple((m["proveedor"], m["modelo"]) for m in prueba["modelos"]))


def estabilidad(pruebas: list[dict]) -> dict:
    """`pruebas`: las corridas de una serie. Forma::

        {serie, corridas: [{prueba_id, codigo, corrida, estado, creado}],
         modelos: [{etiqueta, detecciones: [n|null], exhaustividad: [p|null], falsas_alarmas: [n|null],
                    por_clase: {clase: [n|null]}, minimo, maximo, rango, n_ambiguos}],
         misma_configuracion, avisos}

    Las corridas que no terminaron dan null en su lugar y no entran al rango.
    """
    pruebas = sorted(pruebas, key=lambda p: (p.get("corrida", 1), p["creado"]))
    avisos = []
    if not pruebas:
        return {"serie": None, "corridas": [], "modelos": [], "misma_configuracion": None,
                "avisos": ["La serie no tiene corridas."]}
    misma = len({firma(p) for p in pruebas}) == 1
    if not misma:
        avisos.append("Las corridas no tienen la misma configuración (modelos, términos, banco, prompt, temperatura o "
                      "semilla): el rango no mide solo la variación del modelo.")
    terminadas = [p for p in pruebas if p.get("estado") == "terminada"]
    if len(terminadas) < 2:
        avisos.append("Para medir la estabilidad hacen falta al menos dos corridas terminadas; el rango queda en «---».")
    claves = []
    for p in pruebas:
        for m in p["modelos"]:
            k = (m["proveedor"], m["modelo"])
            if k not in claves:
                claves.append(k)
    modelos = []
    for proveedor, modelo in claves:
        fila = {"etiqueta": etiqueta_modelo({"proveedor": proveedor, "modelo": modelo}), "detecciones": [],
                "exhaustividad": [], "falsas_alarmas": [], "por_clase": {}, "n_ambiguos": None}
        for p in pruebas:
            terminos = {t["id"]: t for t in banco_de(p)["terminos"]}
            m = next((x for x in p["modelos"] if (x["proveedor"], x["modelo"]) == (proveedor, modelo)), None)
            res = p["resultados"].get(m["id"], {}) if m else {}
            hecha = p.get("estado") == "terminada" and m is not None
            positivos = [i for i in p["items"] if es_ambiguo(terminos[i])]
            negativos = [i for i in p["items"] if not es_ambiguo(terminos[i])]
            marcado = {i for i, r in res.items() if r.get("ok") and r.get("ambiguo")}
            vp = sum(i in marcado for i in positivos)
            fila["n_ambiguos"] = len(positivos)
            fila["detecciones"].append(vp if hecha else None)
            fila["exhaustividad"].append(vp / len(positivos) if hecha and positivos else None)
            fila["falsas_alarmas"].append(sum(i in marcado for i in negativos) if hecha and negativos else None)
            for clase in banco_de(p)["clases"]:
                de_clase = [i for i in positivos if terminos[i]["clase"] == clase]
                if de_clase:
                    fila["por_clase"].setdefault(clase, []).append(sum(i in marcado for i in de_clase) if hecha else None)
        validas = [d for d in fila["detecciones"] if d is not None]
        fila["minimo"] = min(validas) if len(validas) >= 2 else None
        fila["maximo"] = max(validas) if len(validas) >= 2 else None
        fila["rango"] = fila["maximo"] - fila["minimo"] if fila["minimo"] is not None else None
        modelos.append(fila)
    variables = [m["etiqueta"] for m in modelos if m["rango"]]
    if variables:
        avisos.append("La detección cambió entre corridas idénticas en " + ", ".join(variables) +
                      ": con este modelo una sola corrida no basta para citar un número.")
    return {"serie": pruebas[0].get("serie") or pruebas[0]["prueba_id"],
            "corridas": [{"prueba_id": p["prueba_id"], "codigo": codigo_de(p), "corrida": p.get("corrida", 1),
                          "estado": p.get("estado"), "creado": p["creado"]} for p in pruebas],
            "modelos": modelos, "misma_configuracion": misma, "avisos": avisos}
