"""Prueba de modelos con el banco de términos ambiguos (ADR 0027).

Los bancos están en `banco/ambiguedad_vN.json` y no se editan una vez publicados: un cambio es
una versión nueva, para que cada prueba siga correspondiendo a su banco (guarda versión y huella).
- v1: 50 términos ambiguos (31 de polisemia y 19 regionalismos).
- v2: los mismos 50 más 23 controles **inequívocos**: vocabulario de dominio con una sola lectura
  en su dominio, muchos en pareja con un ambiguo del mismo dominio («caja» / «caja registradora»).

Cada término trae una cita de entrevista, su dominio y sus lecturas esperadas. Una prueba corre el
Clasificador real de la versión 2 (`intenciones`, prompt `clasificador_intencion_v1`) con cada
modelo elegido sobre los términos elegidos, un término por llamada, y guarda lo que respondió.

Luego una persona revisa, término por término y modelo por modelo, si el modelo hizo un buen
trabajo (✓ / ✗). Las revisiones van en otra colección (`revisiones_modelos`) para que la prueba
pueda seguir corriendo mientras se revisa.

Medidas por modelo (`resumen`), todas con su intervalo de Wilson al 95 %:
- exhaustividad (`deteccion`): ambiguos que marcó como ambiguos (2 o más intenciones);
- con controles: tasa de falsas alarmas (inequívocos marcados como ambiguos) y precisión;
  y en las parejas del mismo dominio, en cuántas marcó el ambiguo y no su control;
- aprobación: ✓ sobre los revisados;
- por clase de término, con reintentos, errores y latencia;
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
import uuid
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from time import perf_counter

from app.agents.clasificador import Clasificador
from app.fases.memoria import SIN_ACUERDOS
from app.llm import FalloEstructurado
from app.llm.proveedores import POR_ID, crear_cliente_de

from .calidad import (  # noqa: F401 — mcnemar y wilson se reexportan para quien ya las usaba de aquí
    LETRAS,
    aprobacion_legado,
    calidad_de,
    falsos_negativos,
    mcnemar,
    pares,
    subenumeracion,
    wilson,
)
from .intercambio import composicion

log = logging.getLogger(__name__)

COLECCION_PRUEBAS = "pruebas_modelos"
COLECCION_REVISIONES = "revisiones_modelos"
PREFIJO = "P"
BANCOS = Path(__file__).with_name("banco")
PROMPT = "clasificador_intencion_v1"
SIN_LEL = "(sin LEL: la prueba usa solo la cita y el contexto)"
TERMINALES = ("terminada", "cancelada", "interrumpida", "error")


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def versiones() -> list[str]:
    """Las versiones del banco que hay en `banco/`, de la más vieja a la más nueva."""
    return sorted((r.stem.removeprefix("ambiguedad_") for r in BANCOS.glob("ambiguedad_v*.json")),
                  key=lambda v: int(v.removeprefix("v")))


@cache
def banco(version: str | None = None) -> dict:
    """El banco con su huella (sha256 de los términos), para citar exactamente qué se usó. Sin
    versión, el más nuevo. Una versión publicada no se edita: los cambios van en una nueva, para
    que las pruebas viejas sigan correspondiendo a su banco."""
    version = version or versiones()[-1]
    if version not in versiones():
        raise KeyError(version)
    datos = json.loads((BANCOS / f"ambiguedad_{version}.json").read_text(encoding="utf-8"))
    crudo = json.dumps(datos["terminos"], ensure_ascii=False, sort_keys=True).encode()
    return {**datos, "huella": hashlib.sha256(crudo).hexdigest(), "versiones": versiones()}


def banco_de(prueba: dict) -> dict:
    """El banco con que corrió la prueba (las de la v2.3.0 no guardaban más que la v1)."""
    return banco(prueba.get("banco", {}).get("version") or "v1")


def por_id(version: str | None = None) -> dict[str, dict]:
    return {t["id"]: t for t in banco(version)["terminos"]}


def es_ambiguo(t: dict) -> bool:
    """La verdad del banco: en v1 todos son ambiguos; desde v2 lo dice cada término."""
    return t.get("ambiguo", t["clase"] != "inequivoco")


def etiqueta_modelo(m: dict) -> str:
    return f"{m['proveedor']} · {m['modelo']}"


# ---------------------------------------------------------------- resumen

def _percentil(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    a, b = math.floor(i), math.ceil(i)
    return xs[a] + (xs[b] - xs[a]) * (i - a)


def resumen(prueba: dict, legado: dict | None = None, revision: dict | None = None, modos: dict | None = None) -> dict:
    """Medidas por modelo y comparación por pares. `legado`: la revisión ✓/✗ de la v2.3
    (`revisiones_modelos`), que se reporta aparte con su criterio viejo; `revision`: la revisión
    de calidad (`revisiones_calidad`, ADR 0029); `modos`: los modos de falla de los falsos negativos
    (`modos_falla`).

    Positivo = el modelo marcó el término como ambiguo (2 o más intenciones); la verdad es la del
    banco. Con controles negativos (banco v2) hay matriz de confusión completa:
    - exhaustividad (`deteccion`): ambiguos marcados sobre TODOS los ambiguos; un error cuenta como
      no detectado (el sistema fallaría igual);
    - tasa de falsas alarmas: inequívocos marcados como ambiguos sobre los inequívocos que
      respondieron (un error no es ni alarma ni contención: se reporta aparte);
    - precisión: ambiguos marcados sobre todo lo marcado.
    La calidad (tres criterios), la cobertura, la subenumeración y los modos de falla salen de
    `calidad.py`. Una métrica que no se puede calcular queda en null y un aviso dice qué falta.
    """
    b = banco_de(prueba)
    terminos = {t["id"]: t for t in b["terminos"]}
    items = prueba["items"]
    positivos = [i for i in items if es_ambiguo(terminos[i])]
    negativos = [i for i in items if not es_ambiguo(terminos[i])]
    calidad = calidad_de(prueba, revision, terminos, es_ambiguo)
    sub = subenumeracion(prueba, terminos, es_ambiguo)
    fn = falsos_negativos(prueba, modos, terminos, es_ambiguo)
    letras = (revision or {}).get("letras") or {m["id"]: LETRAS[k] for k, m in enumerate(prueba["modelos"])}
    modelos = []
    for m in prueba["modelos"]:
        res = prueba["resultados"].get(m["id"], {})
        hechos = [i for i in items if i in res]
        ok = [i for i in hechos if res[i]["ok"]]
        marcados = {i for i in ok if res[i]["ambiguo"]}
        vp = sum(i in marcados for i in positivos)
        neg_ok = [i for i in negativos if i in ok]
        fp = sum(i in marcados for i in neg_ok)
        ms = [res[i]["ms"] for i in ok if res[i].get("ms") is not None]
        por_clase = {}
        for clase in b["clases"]:
            de_clase = [i for i in items if terminos[i]["clase"] == clase]
            if not de_clase:
                continue
            base = de_clase if clase != "inequivoco" else [i for i in de_clase if i in ok]
            # «marcó ambiguo»: en una clase ambigua es la exhaustividad; en la inequívoca, las falsas alarmas
            por_clase[clase] = {"n": len(de_clase), "ambiguo": clase != "inequivoco",
                                "deteccion": wilson(sum(i in marcados for i in base), len(base))}
        parejas = [(t["pareja"], t["id"]) for t in terminos.values()
                   if t.get("pareja") and t["id"] in items and t["pareja"] in items]
        parejas_ok = [(a, n) for a, n in parejas if a in ok and n in ok]
        discrimina = sum(1 for a, n in parejas_ok if a in marcados and n not in marcados)
        modelos.append({
            "id": m["id"], "letra": letras.get(m["id"]), "proveedor": m["proveedor"], "modelo": m["modelo"],
            "etiqueta": etiqueta_modelo(m),
            "n": len(items), "n_ambiguos": len(positivos), "n_inequivocos": len(negativos),
            "hechos": len(hechos), "respondidos": len(ok), "errores": len(hechos) - len(ok),
            "errores_inequivocos": sum(1 for i in negativos if i in res and not res[i]["ok"]),
            "reintentos": sum(1 for i in ok if res[i].get("intentos", 1) > 1),
            "confusion": {"vp": vp, "fn": len(positivos) - vp, "fp": fp, "vn": len(neg_ok) - fp},
            "deteccion": wilson(vp, len(positivos)),
            "falsas_alarmas": wilson(fp, len(neg_ok)) if negativos else None,
            "precision": wilson(vp, vp + fp) if negativos else None,
            "parejas": {"n": len(parejas_ok), "discrimina": discrimina, "proporcion": wilson(discrimina, len(parejas_ok))}
            if parejas else None,
            "calidad": calidad[m["id"]],
            "subenumeracion": sub[m["id"]],
            "falsos_negativos": fn[m["id"]],
            "intenciones_media": statistics.fmean([len(res[i]["intenciones"]) for i in marcados]) if marcados else None,
            "latencia_ms": {"mediana": _percentil(ms, 0.5), "p90": _percentil(ms, 0.9), "n": len(ms)},
            "por_clase": por_clase,
        })
    avisos = []
    if len(items) < 20:
        avisos.append(f"Solo {len(items)} términos: los intervalos son anchos; para citar, corre el banco completo.")
    if not negativos:
        avisos.append("Sin controles inequívocos: la detección es solo la exhaustividad; precisión y falsas alarmas "
                      "quedan en «---». Para calcularlas, corre la prueba con el banco v2 o posterior.")
    elif len(negativos) < 20:
        avisos.append(f"Solo {len(negativos)} controles inequívocos: la tasa de falsas alarmas y la precisión tienen "
                      "intervalos muy anchos.")
    if any(m["errores"] for m in modelos):
        avisos.append("Hay términos con error (el modelo no respondió o no dio un JSON válido tras el reintento): en los "
                      "ambiguos cuentan como no detectados; en los inequívocos se dejan fuera de las falsas alarmas.")
    # sin nombres de modelos: la pantalla puede estar revisando a ciegas
    revisadas = sum(m["calidad"]["revisadas"] for m in modelos)
    revisables_ = sum(m["calidad"]["revisables"] for m in modelos)
    if not revision:
        avisos.append("Calidad y cobertura en «---»: falta la revisión de calidad (fidelidad, delimitación e intención).")
    elif revisadas < revisables_:
        avisos.append(f"Revisión de calidad incompleta ({revisadas} de {revisables_} salidas): la calidad y la cobertura "
                      "solo cuentan las revisadas.")
    if revision and revision.get("a_ciegas") is False:
        avisos.append("La revisión de calidad se hizo con los nombres de los modelos a la vista.")
    comp = composicion(revision)
    if comp["ia"]:
        avisos.append(f"{comp['ia']} de {revisadas} marcas de calidad las puso una IA ({', '.join(comp['quienes_ia'])}) "
                      "con un archivo exportado: es una evaluación con un LLM como juez, no una revisión humana. "
                      "Repórtala así y valídala contra marcas humanas (el acuerdo queda en cada importación).")
    if comp["persona"]:
        avisos.append(f"{comp['persona']} de {revisadas} marcas de calidad se contestaron fuera del sistema, en un "
                      f"archivo a ciegas ({', '.join(comp['quienes_persona'])}).")
    sin_clasificar = sum(m["falsos_negativos"]["sin_clasificar"] for m in modelos)
    if sin_clasificar:
        avisos.append(f"{sin_clasificar} falsos negativos sin modo de falla asignado.")
    legado_ = aprobacion_legado(prueba, legado)
    if legado_:
        avisos.append("Esta prueba tiene una revisión con el criterio viejo (un ✓/✗ por salida, v2.3): se muestra aparte "
                      "como «aprobación (criterio v2.3)» y no se traduce a los criterios nuevos.")
    return {"modelos": modelos, "pares": pares(prueba, revision, terminos, es_ambiguo), "avisos": avisos,
            "aprobacion_legado": legado_,
            "banco": {"version": b["version"], "huella": b["huella"],
                      "coincide": b["huella"] == prueba.get("banco", {}).get("huella", b["huella"])}}


def codigo_de(prueba: dict) -> str:
    """El código citable: id, versión y huella corta del banco (P05-v2-84c2d8). Las pruebas
    anteriores a la v2.4.0 no lo guardaban: se deriva igual."""
    if prueba.get("codigo"):
        return prueba["codigo"]
    b = prueba.get("banco") or {}
    return f"{prueba['prueba_id']}-{b.get('version', 'v1')}-{(b.get('huella') or '')[:6]}"


def resumen_corto(prueba: dict, legado: dict | None = None, revision: dict | None = None,
                  modos: dict | None = None) -> dict:
    """Lo que muestra el listado."""
    r = resumen(prueba, legado, revision, modos)
    return {k: prueba.get(k) for k in ("prueba_id", "nota", "creado", "terminado", "estado", "avance", "uid")} | {
        "codigo": codigo_de(prueba), "serie": prueba.get("serie") or prueba["prueba_id"], "corrida": prueba.get("corrida", 1),
        "n_items": len(prueba["items"]),
        "banco": prueba.get("banco", {}).get("version"),
        "modelos": [{"id": m["id"], "letra": m["letra"], "etiqueta": m["etiqueta"], "deteccion": m["deteccion"]["valor"],
                     "falsas_alarmas": (m["falsas_alarmas"] or {}).get("valor"),
                     "revisadas": m["calidad"]["revisadas"], "revisables": m["calidad"]["revisables"]}
                    for m in r["modelos"]]}


# ---------------------------------------------------------------- creación

def nueva_prueba(pid: str, *, usuario_id: str, modelos: list[dict], items: list[str], nota: str | None,
                 version: str, settings, banco_version: str | None = None, serie: str | None = None,
                 corrida: int = 1) -> dict:
    """Una prueba en proceso. `uid` la hace única aunque dos bases distintas repitan el número;
    `codigo` la cita con la versión y la huella de su banco; `serie` agrupa las corridas idénticas
    (para la estabilidad) y `corrida` es su número dentro de la serie."""
    b = banco(banco_version)
    p = {
        "prueba_id": pid, "uid": str(uuid.uuid4()), "usuario_id": usuario_id, "nota": nota, "creado": ahora(),
        "terminado": None, "estado": "en_proceso", "version_app": version,
        "banco": {"nombre": b["banco"], "version": b["version"], "huella": b["huella"]},
        "configuracion": {"prompt": PROMPT, "temperatura": settings.llm_temperature, "semilla": settings.llm_seed,
                          "significado_max_palabras": settings.significado_max_palabras},
        "items": items,
        "modelos": [{"id": f"M{k + 1}", "proveedor": m["proveedor"], "modelo": m["modelo"]} for k, m in enumerate(modelos)],
        "resultados": {}, "avance": {"hechos": 0, "total": len(items) * len(modelos)}, "error": None,
        "serie": serie or pid, "corrida": corrida,
    }
    p["codigo"] = codigo_de(p)
    return p


def lapida(prueba: dict) -> dict:
    """Lo que queda de una prueba borrada: su número no vuelve a usarse (crear_doc toma el
    siguiente al mayor que existe) y queda constancia de qué era."""
    return {"prueba_id": prueba["prueba_id"], "usuario_id": prueba["usuario_id"], "borrada": True,
            "borrada_en": ahora(), "uid": prueba.get("uid"), "codigo": codigo_de(prueba), "banco": prueba.get("banco"),
            "creado": prueba.get("creado")}


def colisiones(*fuentes: tuple[str, list[dict]]) -> list[dict]:
    """Ids de prueba que aparecen en más de una fuente (por ejemplo, la base JSON local y Mongo)
    con contenido distinto (otro uid u otro banco)::

        [{prueba_id, fuentes: [{fuente, uid, codigo, banco}]}]
    """
    por_id: dict[str, list[dict]] = {}
    for nombre, docs in fuentes:
        for d in docs:
            por_id.setdefault(d["prueba_id"], []).append(
                {"fuente": nombre, "uid": d.get("uid"), "codigo": codigo_de(d), "borrada": bool(d.get("borrada")),
                 "banco": (d.get("banco") or {}).get("version"), "huella": (d.get("banco") or {}).get("huella")})
    salida = []
    for pid, vistos in sorted(por_id.items()):
        firmas = {(v["uid"], v["banco"], v["huella"]) for v in vistos}
        if len(vistos) > 1 and len(firmas) > 1:
            salida.append({"prueba_id": pid, "fuentes": vistos})
    return salida


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

    def lanzar_serie(self, srv, pruebas: list[dict], elecciones: dict[str, dict]) -> None:
        """Corre varias pruebas una tras otra en un solo hilo (una serie de corridas idénticas): en
        paralelo competirían por el mismo Ollama y la latencia no sería comparable."""
        eventos = {}
        for p in pruebas:
            eventos[p["prueba_id"]] = threading.Event()
            self._activas[p["prueba_id"]] = eventos[p["prueba_id"]]

        def todas() -> None:
            for p in pruebas:
                if eventos[p["prueba_id"]].is_set():  # cancelada antes de empezar
                    p.update(estado="cancelada", terminado=ahora())
                    self._guardar(srv, p)
                    self._activas.pop(p["prueba_id"], None)
                    continue
                self._correr(srv, p, elecciones, eventos[p["prueba_id"]])

        threading.Thread(target=todas, daemon=True, name=f"serie-{pruebas[0]['prueba_id']}").start()

    def _guardar(self, srv, prueba: dict) -> None:
        with self._candado:
            prueba["avance"]["hechos"] = sum(len(v) for v in prueba["resultados"].values())
            srv.repo.guardar_doc(COLECCION_PRUEBAS, prueba["prueba_id"], prueba)

    def _correr(self, srv, prueba: dict, elecciones: dict[str, dict], cancelar: threading.Event) -> None:
        s = srv.deps.settings
        terminos = {t["id"]: t for t in banco_de(prueba)["terminos"]}
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
