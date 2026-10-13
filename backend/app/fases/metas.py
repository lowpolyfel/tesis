"""Fase 3: las metas en tres niveles (ADR 0024).

- **De la organización** (MO): lo que la organización quiere lograr en su negocio.
- **Estratégicas** (ME): lo que el sistema debe conseguir para contribuir a una de ellas.
- **Específicas** (MS): concretas y verificables (con su indicador); realizan una estrategia.

Las propone el Modelador con el LEL y el mapa validados y lo que se dijo en la entrevista.
El código verifica la jerarquía (se reintenta una vez si una meta contribuye a otra que no
existe o no es del nivel de arriba), renumera por nivel, liga los símbolos al LEL y deja
solo las citas que existen. La persona valida, corrige, agrega o quita cada meta.
"""
from __future__ import annotations

from app.models import MetasEditables, SalidaMetas

from .documento import DocumentosDeFase, ahora
from .memoria import acuerdos_en_texto
from .progreso import Avisar, paso
from .textos import Simbolos, citas_validas, filtrar_citas, hechos, hechos_en_texto, lel_en_texto, proposiciones_en_texto

NIVELES = (("organizacionales", "organizacional", "MO"), ("estrategicas", "estrategica", "ME"),
           ("especificas", "especifica", "MS"))


def verificar_metas(s: SalidaMetas) -> None:
    todas = [m.id for nivel, _, _ in NIVELES for m in getattr(s, nivel)]
    if len(todas) != len(set(todas)):
        raise ValueError(f"ids de meta repetidos: {todas}; usa MO1…, ME1… y MS1…")
    org = {m.id for m in s.organizacionales}
    est = {m.id for m in s.estrategicas}
    errores = [f"{m.id} contribuye a {m.contribuye_a}, que no es una meta de la organización ({sorted(org)})"
               for m in s.estrategicas if m.contribuye_a not in org]
    errores += [f"{m.id} contribuye a {m.contribuye_a}, que no es una meta estratégica ({sorted(est)})"
                for m in s.especificas if m.contribuye_a not in est]
    if errores:
        raise ValueError("; ".join(errores))


def armar_metas(s: SalidaMetas, simbolos: Simbolos, validas: set[str]) -> tuple[list[dict], list[str]]:
    """Renumera MO/ME/MS en orden, liga símbolos al LEL y deja solo citas que existen."""
    nuevo_id: dict[str, str] = {}
    for nivel, _, prefijo in NIVELES:
        for i, m in enumerate(getattr(s, nivel), 1):
            nuevo_id[m.id] = f"{prefijo}{i}"
    metas, avisos, fuera = [], [], set()
    for nivel, nombre, _ in NIVELES:
        for m in getattr(s, nivel):
            buenos, malos = simbolos.filtrar(m.simbolos)
            fuera.update(malos)
            for extra in simbolos.mencionados(m.enunciado):
                if extra not in buenos:
                    buenos.append(extra)
            metas.append({"id": nuevo_id[m.id], "nivel": nombre, "enunciado": m.enunciado,
                          "contribuye_a": nuevo_id.get(m.contribuye_a) if nombre != "organizacional" else None,
                          "indicador": m.indicador if nombre == "especifica" else None,
                          "simbolos": buenos, "evidencia": filtrar_citas(m.evidencia, validas),
                          "validada": False, "origen": "agentes"})
    sin_especificas = [m["id"] for m in metas if m["nivel"] == "estrategica"
                       and not any(x["contribuye_a"] == m["id"] for x in metas)]
    if sin_especificas:
        avisos.append(f"Metas estratégicas sin metas específicas: {', '.join(sin_especificas)}.")
    if fuera:
        avisos.append(f"Se quitaron símbolos que no están en el LEL validado: {', '.join(sorted(fuera))}.")
    sin_evidencia = [m["id"] for m in metas if m["nivel"] == "especifica" and not m["evidencia"]]
    if sin_evidencia:
        avisos.append(f"Metas específicas sin una cita de la entrevista: {', '.join(sin_evidencia)}.")
    MetasEditables.model_validate({"metas": metas})
    return metas, avisos


def generar(deps, proyecto, entradas: list[dict], acuerdos: list[dict], entrevistas: list[dict], mapa: dict,
            huella_origen: str, avisar: Avisar) -> dict:
    h = hechos(entrevistas)
    proposito, proposiciones = proposiciones_en_texto(mapa)
    avisar(paso("insumos", "Reuniendo lo validado", "ok",
                f"{len(h['necesidades'])} necesidades · {len(h['problemas'])} problemas · mapa con "
                f"{len(mapa['contenido']['relaciones'])} proposiciones"))
    avisar(paso("modelador", "El Modelador propone las metas en tres niveles"))
    r = deps.modelador.metas_en_niveles(
        verificar=verificar_metas, proyecto=proyecto.nombre,
        contexto=(proyecto.contexto or "").strip() or "(el proyecto no tiene contexto general)",
        acuerdos=acuerdos_en_texto(acuerdos), entrevista=hechos_en_texto(h), lel=lel_en_texto(entradas, detalle=False),
        proposito=proposito, proposiciones=proposiciones)
    v = r.valor
    avisar(paso("modelador", "Metas propuestas", "ok",
                f"{len(v.organizacionales)} de la organización · {len(v.estrategicas)} estratégicas · "
                f"{len(v.especificas)} específicas" + (" (con un reintento)" if r.hubo_reintento else "")))
    avisar(paso("revision", "Revisando la jerarquía, los símbolos y las citas"))
    metas, avisos = armar_metas(v, Simbolos(entradas), citas_validas(entrevistas))
    avisar(paso("revision", "Revisión en código", "aviso" if avisos else "ok",
                f"{len(avisos)} aviso(s)" if avisos else "todo se rastrea"))
    fecha = ahora()
    doc = {"proyecto_id": proyecto.proyecto_id, "fase": "metas", "contenido": {"metas": metas},
           "huella_origen": huella_origen, "avisos": avisos, "modelo": r.modelo, "prompt_version": r.prompt_version,
           "intentos": len(r.intentos), "generado": fecha, "actualizado": fecha,
           "historial": [{"fecha": fecha, "accion": "generar", "autor": "agentes", "detalle": f"{len(metas)} metas"}]}
    return DocumentosDeFase(deps.repo).guardar("metas", doc)


def editar(repo, previo: dict, nuevas: MetasEditables, entradas: list[dict], entrevistas: list[dict]) -> dict:
    simbolos, validas = Simbolos(entradas), citas_validas(entrevistas)
    metas = nuevas.model_dump(mode="json")["metas"]
    for m in metas:
        m["simbolos"], _ = simbolos.filtrar(m["simbolos"] + simbolos.mencionados(m["enunciado"]))
        m["evidencia"] = filtrar_citas(m["evidencia"], validas)
        if m["nivel"] != "especifica":
            m["indicador"] = None
    antes = {m["id"]: m for m in previo["contenido"]["metas"]}
    despues = {m["id"]: m for m in metas}
    cambios = [f"agregó {i}" for i in despues.keys() - antes.keys()]
    cambios += [f"quitó {i}" for i in antes.keys() - despues.keys()]
    cambios += [f"corrigió {i}" for i in antes.keys() & despues.keys()
                if {k: v for k, v in antes[i].items() if k != "validada"} != {k: v for k, v in despues[i].items() if k != "validada"}]
    n = sum(1 for i in antes.keys() & despues.keys() if despues[i]["validada"] and not antes[i]["validada"])
    if n:
        cambios.append(f"validó {n} meta(s)")
    fecha = ahora()
    previo["contenido"] = {"metas": metas}
    previo["actualizado"] = fecha
    if cambios:
        previo["historial"].append({"fecha": fecha, "accion": "editar", "autor": "persona", "cambios": cambios})
    return DocumentosDeFase(repo).guardar("metas", previo)
