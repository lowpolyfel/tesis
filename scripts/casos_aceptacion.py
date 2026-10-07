"""Corre los 3 casos de aceptación de la fase con Ollama real y reporta lo observado.

Uso (desde la raíz del repo, con el venv del backend activo y Ollama corriendo):

    python scripts/casos_aceptacion.py

Cada requisito corre por el grafo real hasta la pausa de validación humana (o
hasta `error`) y queda en la persistencia configurada (Mongo o JSON), así que
después se puede validar desde la sandbox. El reporte se imprime y se guarda en
`data/resultados/aceptacion/AAAAMMDD-HHMMSS.json`.

No ajusta el umbral: usa SIMILARITY_THRESHOLD de la configuración. Si la
similitud no separa los casos como se esperaba, eso es un hallazgo y se reporta.

Puede correr con la API arriba, también con el respaldo JSON: las escrituras de
los dos procesos se serializan con un candado de archivo y los req_id no se
repiten (ADR 0006). No arranques la API mientras el script está a mitad de un
requisito: al arrancar retoma lo que encuentra a medias y lo correría en paralelo.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.orchestration import Servicio, crear_dependencias  # noqa: E402

CASOS = [
    ("eliminar_usuarios", "El sistema debe permitir al administrador eliminar usuarios inactivos.",
     "termina en aceptado_directo o sin candidatos"),
    ("sesion", "El sistema debe registrar la sesión del usuario.",
     "al menos 2 interpretaciones y cálculo de similitud visible"),
    ("jalar_ahorita", "El sistema debe jalar los datos del servidor ahorita.",
     "jalar → regional; ahorita → vaguedad sin debate"),
]


def verificar_ollama(settings) -> None:
    try:
        with urllib.request.urlopen(f"{settings.ollama_base_url}/api/tags", timeout=5) as r:
            disponibles = {m["name"] for m in json.load(r)["models"]}
    except Exception as e:  # noqa: BLE001
        sys.exit(f"No responde Ollama en {settings.ollama_base_url} ({e}). Arráncalo con `ollama serve`.")
    requeridos = {settings.extractor_model, settings.clasificador_model, settings.modelador_model,
                  settings.embedding_model}
    if settings.critico_provider == "ollama":
        requeridos.add(settings.critico_model)
    faltan = sorted(m for m in requeridos if m not in disponibles and f"{m}:latest" not in disponibles)
    if faltan:
        sys.exit("Faltan modelos en Ollama: " + ", ".join(faltan) + ". Descárgalos con `ollama pull <modelo>`.")


def observar(traza) -> dict:
    """Extrae de la traza lo que piden los criterios de aceptación."""
    por_tipo = lambda t: [m for m in traza.mensajes if m.tipo == t]  # noqa: E731
    filtrado = por_tipo("filtrado")
    interpretaciones = por_tipo("interpretaciones")
    return {
        "req_id": traza.req_id,
        "estado": traza.estado.value,
        "ruta": [t.estado.value for t in traza.transiciones],
        "filtros": {t["termino"]: t["decision_filtro"] for t in filtrado[0].payload["terminos"]} if filtrado else {},
        "interpretaciones": {
            r["termino"]: ("univoco" if r["univoco"] else
                           [{"id": i["id"], "significado": i["significado"], "parafrasis": i["parafrasis_del_requisito"]}
                            for i in r["interpretaciones"]])
            for r in (interpretaciones[0].payload["resultados"] if interpretaciones else [])
        },
        "similitudes": [
            {"ronda": m.ronda, "termino": m.payload.get("termino"), "similitud": m.payload.get("similitud"),
             "umbral": m.payload.get("umbral"), "decision": m.payload.get("decision"),
             "pares": m.payload.get("pares"), "motivo": m.payload.get("motivo")}
            for m in por_tipo("similitud")
        ],
        "objeciones": sum(len(m.payload.get("objeciones", [])) for m in por_tipo("objecion")),
        "consensos": [{k: m.payload[k] for k in ("termino", "motivo", "propuesta")} for m in por_tipo("consenso")],
        "arbitrajes": [{"termino": m.payload["termino"], "elegida": m.payload["interpretacion_elegida"]}
                       for m in por_tipo("arbitraje")],
        "reintentos": [{"tipo": m.tipo.value, "prompt": m.prompt_version} for m in traza.mensajes
                       if m.payload.get("intentos", 1) > 1],
        "errores": [m.payload for m in por_tipo("error")],
    }


def cumple(clave: str, obs: dict) -> tuple[bool, str]:
    if clave == "eliminar_usuarios":
        ruta = obs["ruta"]
        ok = "aceptado_directo" in ruta and "en_debate" not in ruta
        return ok, f"ruta: {' → '.join(ruta)}"
    if clave == "sesion":
        terminos = [v for v in obs["interpretaciones"].values() if isinstance(v, list) and len(v) >= 2]
        con_valor = [s for s in obs["similitudes"] if s["similitud"] is not None]
        return bool(terminos and con_valor), f"{len(terminos)} término(s) con ≥2 interpretaciones; {len(con_valor)} cálculo(s) de similitud"
    if clave == "jalar_ahorita":
        f = {k.lower(): v for k, v in obs["filtros"].items()}
        jalar = next((v for k, v in f.items() if k.startswith("jal")), None)
        ahorita = f.get("ahorita")
        debatido = any("ahorita" in (s["termino"] or "").lower() for s in obs["similitudes"])
        return jalar == "regional" and ahorita == "vaguedad" and not debatido, f"jalar: {jalar}; ahorita: {ahorita}; ahorita debatido: {debatido}"
    return False, "caso desconocido"


def imprimir(clave: str, texto: str, esperado: str, obs: dict, ok: bool, detalle: str) -> None:
    print(f"\n=== {clave} · {obs['req_id']} ===\n«{texto}»")
    print(f"esperado: {esperado}\nobservado: {'✓' if ok else '✗'} {detalle}")
    print(f"estado: {obs['estado']}")
    print("filtros:", ", ".join(f"{k}={v}" for k, v in obs["filtros"].items()) or "—")
    for termino, v in obs["interpretaciones"].items():
        if v == "univoco":
            print(f"  {termino}: unívoco")
        else:
            print(f"  {termino}:")
            for i in v:
                print(f"    {i['id']} [{i['significado']}] {i['parafrasis']}")
    for s in obs["similitudes"]:
        valor = "—" if s["similitud"] is None else f"{s['similitud']:.4f}"
        pares = ", ".join(f"{k}={v:.4f}" for k, v in (s["pares"] or {}).items())
        print(f"  similitud ronda {s['ronda']} «{s['termino'] or '—'}»: {valor} (umbral {s['umbral']}) → {s['decision']}"
              + (f" [{pares}]" if pares else "") + (f" ({s['motivo']})" if s["motivo"] else ""))
    if obs["objeciones"] or obs["consensos"] or obs["arbitrajes"]:
        print(f"  debate: {obs['objeciones']} objeción(es); consensos {obs['consensos']}; arbitrajes {obs['arbitrajes']}")
    if obs["reintentos"]:
        print(f"  reintentos: {obs['reintentos']}")
    for e in obs["errores"]:
        print(f"  ERROR {e.get('excepcion')} en {e.get('nodo')}: {e.get('mensaje')}")


def main() -> None:
    settings = get_settings()
    verificar_ollama(settings)
    deps = crear_dependencias(settings)
    servicio = Servicio(deps)
    print(f"persistencia: {deps.repo.descripcion} · umbral {settings.similarity_threshold} · "
          f"rondas {settings.max_debate_rounds}")

    reporte = {"fecha": datetime.now().isoformat(timespec="seconds"), "config": deps.config_traza(), "casos": []}
    for clave, texto, esperado in CASOS:
        req_id = servicio.procesar(texto)
        obs = observar(servicio.traza(req_id))
        ok, detalle = cumple(clave, obs)
        imprimir(clave, texto, esperado, obs, ok, detalle)
        reporte["casos"].append({"caso": clave, "texto": texto, "esperado": esperado, "cumple": ok,
                                 "detalle": detalle, **obs})

    destino = settings.ruta(settings.resultados_dir) / "aceptacion"
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    archivo.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReporte: {archivo}")
    print("Los requisitos quedaron en pendiente_validacion: valídalos en http://localhost:8000/sandbox")


if __name__ == "__main__":
    main()
