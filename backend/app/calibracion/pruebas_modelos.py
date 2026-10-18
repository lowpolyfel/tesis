"""Prueba de modelos con el banco de términos ambiguos (ADR 0027).

El banco (`banco/ambiguedad_v1.json`) trae 50 términos ambiguos, cada uno en una cita de
entrevista con su dominio y sus lecturas esperadas. Una prueba corre el Clasificador real de la
versión 2 (`intenciones`, prompt `clasificador_intencion_v1`) con cada modelo elegido sobre los
términos elegidos, un término por llamada, y guarda lo que respondió cada modelo.

Luego una persona revisa, término por término y modelo por modelo, si el modelo hizo un buen
trabajo (✓ / ✗). Las revisiones van en otra colección (`revisiones_modelos`) para que la prueba
pueda seguir corriendo mientras se revisa.

Medidas por modelo (`resumen`):
- detección: cuántos términos marcó como ambiguos (2 o más intenciones), sobre todos los
  términos de la prueba; un error cuenta como no detectado;
- aprobación: ✓ sobre los revisados;
- ambas con su intervalo de Wilson al 95 %, por clase de término, con reintentos, errores y
  latencia;
- entre cada par de modelos, la prueba exacta de McNemar sobre los términos que ambos tienen
  revisados (¿la diferencia de aprobación es más que azar?).

Las llaves de los modelos son M1, M2…: los nombres de modelo llevan puntos («qwen2.5:7b») y
Mongo no los acepta como llaves.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import statistics
import threading
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from time import perf_counter

from app.agents.clasificador import Clasificador
from app.fases.memoria import SIN_ACUERDOS
from app.llm import FalloEstructurado
from app.llm.proveedores import POR_ID, crear_cliente_de

log = logging.getLogger(__name__)

COLECCION_PRUEBAS = "pruebas_modelos"
COLECCION_REVISIONES = "revisiones_modelos"
PREFIJO = "P"
BANCO = Path(__file__).with_name("banco") / "ambiguedad_v1.json"
PROMPT = "clasificador_intencion_v1"
SIN_LEL = "(sin LEL: la prueba usa solo la cita y el contexto)"
Z = 1.959963984540054  # normal al 97.5 %: intervalos al 95 %
TERMINALES = ("terminada", "cancelada", "interrumpida", "error")


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@cache
def banco() -> dict:
    """El banco con su huella (sha256 de los términos), para citar exactamente qué se usó."""
    datos = json.loads(BANCO.read_text(encoding="utf-8"))
    crudo = json.dumps(datos["terminos"], ensure_ascii=False, sort_keys=True).encode()
    return {**datos, "huella": hashlib.sha256(crudo).hexdigest()}


def por_id() -> dict[str, dict]:
    return {t["id"]: t for t in banco()["terminos"]}


def etiqueta_modelo(m: dict) -> str:
    return f"{m['proveedor']} · {m['modelo']}"


# ---------------------------------------------------------------- estadística

def wilson(exitos: int, n: int) -> dict:
    """Proporción con su intervalo de Wilson al 95 % (se porta bien con n chica y con 0 o n)."""
    if not n:
        return {"valor": None, "bajo": None, "alto": None, "exitos": exitos, "n": 0}
    p = exitos / n
    den = 1 + Z * Z / n
    centro = (p + Z * Z / (2 * n)) / den
    medio = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return {"valor": p, "bajo": max(0.0, centro - medio), "alto": min(1.0, centro + medio), "exitos": exitos, "n": n}


def mcnemar(b: int, c: int) -> float | None:
    """p bilateral de la prueba exacta de McNemar: b y c son los pares discordantes
    (✓ en uno y ✗ en el otro). Sin discordantes no hay nada que probar."""
    n = b + c
    if not n:
        return None
    k = min(b, c)
    cola = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * cola)


# ---------------------------------------------------------------- resumen

def _percentil(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    a, b = math.floor(i), math.ceil(i)
    return xs[a] + (xs[b] - xs[a]) * (i - a)


def resumen(prueba: dict, revisiones: dict | None) -> dict:
    """Medidas por modelo y comparación por pares. `revisiones`: el doc de `revisiones_modelos` o None."""
    terminos = por_id()
    items = prueba["items"]
    marcas = (revisiones or {}).get("marcas", {})
    modelos = []
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        rev = marcas.get(m["id"], {})
        hechos = [i for i in items if i in res]
        ok = [i for i in hechos if res[i]["ok"]]
        detectados = [i for i in ok if res[i]["ambiguo"]]
        revisados = [i for i in items if rev.get(i, {}).get("bueno") is not None]
        buenos = [i for i in revisados if rev[i]["bueno"]]
        ms = [res[i]["ms"] for i in ok if res[i].get("ms") is not None]
        por_clase = {}
        for clase in banco()["clases"]:
            de_clase = [i for i in items if terminos[i]["clase"] == clase]
            if not de_clase:
                continue
            rv = [i for i in de_clase if i in revisados]
            por_clase[clase] = {"n": len(de_clase),
                                "deteccion": wilson(sum(i in detectados for i in de_clase), len(de_clase)),
                                "aprobacion": wilson(sum(i in buenos for i in rv), len(rv))}
        modelos.append({
            "id": m["id"], "proveedor": m["proveedor"], "modelo": m["modelo"], "etiqueta": etiqueta_modelo(m),
            "n": len(items), "hechos": len(hechos), "respondidos": len(ok), "errores": len(hechos) - len(ok),
            "reintentos": sum(1 for i in ok if res[i].get("intentos", 1) > 1),
            "deteccion": wilson(len(detectados), len(items)),
            "aprobacion": wilson(len(buenos), len(revisados)),
            "revisados": len(revisados),
            "intenciones_media": statistics.fmean([len(res[i]["intenciones"]) for i in detectados]) if detectados else None,
            "latencia_ms": {"mediana": _percentil(ms, 0.5), "p90": _percentil(ms, 0.9)},
            "por_clase": por_clase,
        })
    pares = []
    for a_i, a in enumerate(prueba["modelos"]):
        for b in prueba["modelos"][a_i + 1:]:
            ra, rb = marcas.get(a["id"], {}), marcas.get(b["id"], {})
            comunes = [i for i in items if ra.get(i, {}).get("bueno") is not None and rb.get(i, {}).get("bueno") is not None]
            solo_a = sum(1 for i in comunes if ra[i]["bueno"] and not rb[i]["bueno"])
            solo_b = sum(1 for i in comunes if rb[i]["bueno"] and not ra[i]["bueno"])
            pares.append({"a": a["id"], "b": b["id"], "comunes": len(comunes), "solo_a": solo_a, "solo_b": solo_b,
                          "p": mcnemar(solo_a, solo_b)})
    avisos = []
    if len(items) < 20:
        avisos.append(f"Solo {len(items)} términos: los intervalos son anchos; para citar, corre el banco completo.")
    sin_revisar = [m["etiqueta"] for m in modelos if m["respondidos"] and m["revisados"] < m["respondidos"]]
    if sin_revisar:
        avisos.append("Faltan revisiones de " + ", ".join(sin_revisar) + ": la aprobación solo cuenta los revisados.")
    if any(m["errores"] for m in modelos):
        avisos.append("Hay términos con error (el modelo no respondió o no dio un JSON válido tras el reintento): "
                      "cuentan como no detectados.")
    if revisiones and revisiones.get("a_ciegas") is False:
        avisos.append("La revisión se hizo viendo el nombre de los modelos.")
    return {"modelos": modelos, "pares": pares, "avisos": avisos}


def resumen_corto(prueba: dict, revisiones: dict | None) -> dict:
    """Lo que muestra el listado."""
    r = resumen(prueba, revisiones)
    return {k: prueba.get(k) for k in ("prueba_id", "nota", "creado", "terminado", "estado", "avance")} | {
        "n_items": len(prueba["items"]),
        "modelos": [{"id": m["id"], "etiqueta": m["etiqueta"], "deteccion": m["deteccion"]["valor"],
                     "aprobacion": m["aprobacion"]["valor"], "revisados": m["revisados"]} for m in r["modelos"]]}


# ---------------------------------------------------------------- creación

def nueva_prueba(pid: str, *, usuario_id: str, modelos: list[dict], items: list[str], nota: str | None,
                 version: str, settings) -> dict:
    b = banco()
    return {
        "prueba_id": pid, "usuario_id": usuario_id, "nota": nota, "creado": ahora(), "terminado": None,
        "estado": "en_proceso", "version_app": version,
        "banco": {"nombre": b["banco"], "version": b["version"], "huella": b["huella"]},
        "configuracion": {"prompt": PROMPT, "temperatura": settings.llm_temperature, "semilla": settings.llm_seed,
                          "significado_max_palabras": settings.significado_max_palabras},
        "items": items,
        "modelos": [{"id": f"M{k + 1}", "proveedor": m["proveedor"], "modelo": m["modelo"]} for k, m in enumerate(modelos)],
        "resultados": {}, "avance": {"hechos": 0, "total": len(items) * len(modelos)}, "error": None,
    }


def resolver(srv, usuario_id: str, modelo: dict) -> dict:
    """{proveedor, modelo, base_url, api_key} con la clave y la URL guardadas por la cuenta.
    ValueError si el proveedor pide clave y la cuenta no tiene."""
    p = POR_ID.get(modelo["proveedor"])
    if p is None:
        raise ValueError(f"proveedor desconocido: {modelo['proveedor']}")
    clave = srv.perfiles.clave_guardada(usuario_id, p.id)
    if p.pide_clave and not clave:
        raise ValueError(f"Falta la clave de {p.nombre}: guárdala en Configuración.")
    base = srv.perfiles.url_guardada(usuario_id, p.id)
    if p.id == "ollama" and not base:
        base = srv.deps.settings.ollama_base_url
    return {"proveedor": p.id, "modelo": modelo["modelo"], "base_url": base, "api_key": clave}


# ---------------------------------------------------------------- ejecución

def clasificar(clasificador: Clasificador, t: dict) -> dict:
    """Una llamada al Clasificador con un término del banco: lo que se guarda como resultado."""
    entrada = [{"termino": t["termino"], "categoria_tentativa": "concepto",
                "origen": "regional" if t["clase"] == "regionalismo" else "extractor", "detalle": None,
                "citas": [f"[T1] {t['cita']}"]}]
    t0 = perf_counter()
    try:
        r = clasificador.intenciones(entrada, SIN_LEL, SIN_ACUERDOS, t["contexto"])
    except FalloEstructurado as e:
        return {"ok": False, "ms": round((perf_counter() - t0) * 1000), "intentos": len(e.intentos),
                "error": str(e)[:400], "crudo": (e.intentos[-1].salida_cruda or "")[:1500] if e.intentos else None}
    except Exception as e:  # noqa: BLE001 — proveedor caído, sin modelo, tiempo agotado: se registra y sigue
        return {"ok": False, "ms": round((perf_counter() - t0) * 1000), "intentos": 0,
                "error": f"{type(e).__name__}: {str(e)[:400]}"}
    res = r.valor.resultados[0]
    return {"ok": True, "ms": round((perf_counter() - t0) * 1000), "intentos": len(r.intentos),
            "ambiguo": not res.univoco, "tipo": res.tipo_ambiguedad.value if res.tipo_ambiguedad else None,
            "intenciones": [{"id": i.id, "significado": i.significado, "intencion": i.intencion, "parafrasis": i.parafrasis}
                            for i in res.intenciones]}


class Ejecutor:
    """Corre las pruebas en hilos propios, fuera de la cola de análisis (ADR 0027): un hilo por
    proveedor, y dentro de cada proveedor los modelos uno tras otro, para no cargar varios
    modelos de Ollama a la vez. El documento se guarda tras cada término (bajo un candado)."""

    def __init__(self):
        self._activas: dict[str, threading.Event] = {}
        self._candado = threading.Lock()

    def activa(self, prueba_id: str) -> bool:
        return prueba_id in self._activas

    def cancelar(self, prueba_id: str) -> bool:
        ev = self._activas.get(prueba_id)
        if ev:
            ev.set()
        return ev is not None

    def lanzar(self, srv, prueba: dict, elecciones: dict[str, dict]) -> None:
        """`elecciones`: {M1: {proveedor, modelo, base_url, api_key}} ya resueltas."""
        cancelar = threading.Event()
        self._activas[prueba["prueba_id"]] = cancelar
        threading.Thread(target=self._correr, args=(srv, prueba, elecciones, cancelar), daemon=True,
                         name=f"prueba-{prueba['prueba_id']}").start()

    def _guardar(self, srv, prueba: dict) -> None:
        with self._candado:
            prueba["avance"]["hechos"] = sum(len(v) for v in prueba["resultados"].values())
            srv.repo.guardar_doc(COLECCION_PRUEBAS, prueba["prueba_id"], prueba)

    def _correr(self, srv, prueba: dict, elecciones: dict[str, dict], cancelar: threading.Event) -> None:
        s = srv.deps.settings
        terminos = por_id()
        por_proveedor: dict[str, list[dict]] = {}
        for m in prueba["modelos"]:
            por_proveedor.setdefault(m["proveedor"], []).append(m)

        def proveedor(modelos: list[dict]) -> None:
            for m in modelos:
                try:
                    clasificador = Clasificador(crear_cliente_de(elecciones[m["id"]], s), s.significado_max_palabras)
                except Exception as e:  # noqa: BLE001 — sin URL, proveedor mal configurado
                    fallo = {"ok": False, "ms": None, "intentos": 0, "error": f"{type(e).__name__}: {e}"}
                    with self._candado:
                        prueba["resultados"].setdefault(m["id"], {}).update({i: dict(fallo) for i in prueba["items"]})
                    self._guardar(srv, prueba)
                    continue
                for item in prueba["items"]:
                    if cancelar.is_set():
                        return
                    if item in prueba["resultados"].get(m["id"], {}):  # ya estaba (reanudación)
                        continue
                    r = clasificar(clasificador, terminos[item])
                    with self._candado:
                        prueba["resultados"].setdefault(m["id"], {})[item] = r
                    self._guardar(srv, prueba)

        hilos = [threading.Thread(target=proveedor, args=(ms,), daemon=True) for ms in por_proveedor.values()]
        try:
            for h in hilos:
                h.start()
            for h in hilos:
                h.join()
            prueba["estado"] = "cancelada" if cancelar.is_set() else "terminada"
        except Exception as e:
            log.exception("Falló la prueba de modelos %s", prueba["prueba_id"])
            prueba["estado"], prueba["error"] = "error", f"{type(e).__name__}: {e}"
        finally:
            prueba["terminado"] = ahora()
            self._guardar(srv, prueba)
            self._activas.pop(prueba["prueba_id"], None)


EJECUTOR = Ejecutor()


def al_dia(prueba: dict) -> dict:
    """Una prueba «en_proceso» que ningún hilo corre quedó a medias por un reinicio: se reporta
    como interrumpida (se puede reanudar)."""
    if prueba.get("estado") == "en_proceso" and not EJECUTOR.activa(prueba["prueba_id"]):
        return {**prueba, "estado": "interrumpida"}
    return prueba
