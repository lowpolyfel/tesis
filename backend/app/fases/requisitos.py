"""Fase 4: los requisitos, desde la entrevista, el LEL, el contexto, el mapa y las metas (ADR 0024).

El Modelador los escribe por meta estratégica: en cada llamada recibe esa estrategia, sus
metas específicas, lo que se dijo de ellas en la entrevista (con sus citas), el LEL y el
mapa validados, los acuerdos del proyecto y los requisitos que ya escribió (para no
repetir). El código verifica que cada requisito realice metas de esa estrategia (se
reintenta una vez si no), numera RF y RNF, liga los símbolos al LEL, deja solo las citas
que existen y avisa de lo que una persona debe mirar: expresiones vagas, requisitos que
no usan el LEL o metas específicas que ningún requisito realiza.

`a_markdown` arma la especificación completa con su trazabilidad: es el producto final.
"""
from __future__ import annotations

import re

from app.models import RequisitosEditables, SalidaRequisitos, TipoRequisito

from .documento import DocumentosDeFase, ahora
from .memoria import acuerdos_en_texto
from .progreso import Avisar, paso
from .textos import (
    Simbolos,
    citas_validas,
    filtrar_citas,
    hechos,
    hechos_en_texto,
    lel_en_texto,
    proposiciones_en_texto,
    validadas,
)

# Expresiones vagas en un requisito (además del catálogo de vaguedad): una persona debe concretarlas
VAGAS = ("rápido", "rapido", "rápida", "rapida", "ahorita", "pronto", "fácil", "facil", "amigable", "eficiente",
         "adecuado", "adecuada", "oportuno", "oportuna", "intuitivo", "intuitiva", "etc", "lo antes posible",
         "en un tiempo razonable", "suficiente", "flexible", "moderno", "moderna")


def vagas_en(texto: str, extra: tuple[str, ...] = ()) -> list[str]:
    base = texto.lower()
    return sorted({v for v in (*VAGAS, *extra) if re.search(rf"(?<!\w){re.escape(v)}(?!\w)", base)})


def numerar(requisitos: list[dict]) -> list[dict]:
    """RF01, RF02… y RNF01… en el orden en que están."""
    rf = rnf = 0
    for r in requisitos:
        if r["tipo"] == TipoRequisito.FUNCIONAL.value:
            rf += 1
            r["id"] = f"RF{rf:02d}"
        else:
            rnf += 1
            r["id"] = f"RNF{rnf:02d}"
    return requisitos


def ids_estables(requisitos: list[dict]) -> list[dict]:
    """Al editar, cada requisito conserva su id; solo el que cambió de tipo (RF ↔ RNF) toma el
    siguiente libre de su tipo. Así la trazabilidad no se mueve al quitar uno de en medio."""
    usados = {r["id"] for r in requisitos}
    for r in requisitos:
        prefijo = "RF" if r["tipo"] == TipoRequisito.FUNCIONAL.value else "RNF"
        if re.fullmatch(rf"{prefijo}\d+", r["id"]):
            continue
        n = max((int(x[len(prefijo):]) for x in usados if re.fullmatch(rf"{prefijo}\d+", x)), default=0) + 1
        usados.discard(r["id"])
        r["id"] = f"{prefijo}{n:02d}"
        usados.add(r["id"])
    return requisitos


def avisos_de(r: dict, extra_vagas: tuple[str, ...] = ()) -> list[str]:
    avisos = []
    vagas = vagas_en(r["texto"], extra_vagas)
    if vagas:
        avisos.append(f"expresión vaga: {', '.join(vagas)}")
    if not r["simbolos"]:
        avisos.append("no usa ningún término del LEL")
    if not r["evidencia"]:
        avisos.append("sin una cita de la entrevista")
    if not r["criterios"]:
        avisos.append("sin criterios de aceptación")
    return avisos


def _relevantes(h: dict, citas: set[str]) -> dict:
    """Lo de la entrevista que comparte citas con las metas; si nada coincide, todo."""
    salida = {"objetivos": h["objetivos"]}
    for campo in ("problemas", "necesidades", "reglas"):
        cerca = [x for x in h[campo] if set(x["citas"]) & citas]
        salida[campo] = cerca or h[campo]
    return salida


def generar(deps, proyecto, entradas: list[dict], acuerdos: list[dict], entrevistas: list[dict], mapa: dict,
            metas: dict, huella_origen: str, avisar: Avisar) -> dict:
    todas = metas["contenido"]["metas"]
    estrategicas = [m for m in todas if m["nivel"] == "estrategica"]
    h = hechos(entrevistas)
    proposito, proposiciones = proposiciones_en_texto(mapa)
    simbolos, validas = Simbolos(entradas), citas_validas(entrevistas)
    extra_vagas = tuple(t["expresion"] for t in deps.filtros.catalogos.vaguedad.entradas) \
        if getattr(deps, "filtros", None) is not None else ()
    comunes = {"proyecto": proyecto.nombre, "acuerdos": acuerdos_en_texto(acuerdos),
               "contexto": (proyecto.contexto or "").strip() or "(el proyecto no tiene contexto general)",
               "lel": lel_en_texto(entradas, detalle=False), "proposito": proposito, "proposiciones": proposiciones}
    avisar(paso("insumos", "Reuniendo la entrevista, el LEL, el mapa y las metas", "ok",
                f"{len(validadas(entradas))} términos · {len(estrategicas)} estrategias · "
                f"{sum(m['nivel'] == 'especifica' for m in todas)} metas específicas"))

    escritos: list[dict] = []
    ultimo = None
    for i, me in enumerate(estrategicas, 1):
        especificas = [m for m in todas if m["contribuye_a"] == me["id"]]
        if not especificas:
            avisar(paso(f"me{i}", f"{me['id']}: sin metas específicas", "aviso", "no hay qué realizar"))
            continue
        ids = {m["id"] for m in especificas}
        avisar(paso(f"me{i}", f"Requisitos para {me['id']} ({i} de {len(estrategicas)})", detalle=me["enunciado"]))

        def verificar(s: SalidaRequisitos, ids=ids) -> None:
            malos = [f"«{r.texto[:40]}…» → {sorted(set(r.metas) - ids)}" for r in s.requisitos if set(r.metas) - ids]
            sin = [f"«{r.texto[:40]}…»" for r in s.requisitos if not r.metas]
            if malos or sin:
                raise ValueError(f"cada requisito realiza metas específicas de esta estrategia ({sorted(ids)}); "
                                 f"fuera de ellas: {malos}; sin metas: {sin}")

        citas = {c for m in especificas for c in m["evidencia"]}
        r = deps.modelador.requisitos(
            verificar=verificar, **comunes, estrategica=f"{me['id']}: {me['enunciado']}",
            especificas="\n".join(f"- {m['id']}: {m['enunciado']}" + (f" (indicador: {m['indicador']})" if m.get("indicador") else "")
                                  + (f" [{', '.join(m['evidencia'])}]" if m["evidencia"] else "") for m in especificas),
            entrevista=hechos_en_texto(_relevantes(h, citas), limite=25),
            previos="\n".join(f"- {x['texto']}" for x in escritos) or "(ninguno todavía)")
        ultimo = r
        for x in r.valor.requisitos:
            buenos, _ = simbolos.filtrar(x.simbolos)
            for extra in simbolos.mencionados(x.texto):
                if extra not in buenos:
                    buenos.append(extra)
            req = {"id": "RF00", "texto": x.texto, "tipo": x.tipo.value,
                   "categoria": x.categoria.value if x.categoria else None, "prioridad": x.prioridad,
                   "metas": x.metas, "simbolos": buenos, "evidencia": filtrar_citas(x.evidencia, validas),
                   "criterios": x.criterios, "supuestos": x.supuestos, "validado": False, "origen": "agentes"}
            req["avisos"] = avisos_de(req, extra_vagas)
            escritos.append(req)
        avisar(paso(f"me{i}", f"{me['id']}: {len(r.valor.requisitos)} requisito(s)", "ok",
                    "con un reintento" if r.hubo_reintento else None))
    if not escritos:
        raise ValueError("Ninguna meta estratégica tiene metas específicas: no hay requisitos que escribir.")

    numerar(escritos)
    realizadas = {m for x in escritos for m in x["metas"]}
    sin_requisito = [m["id"] for m in todas if m["nivel"] == "especifica" and m["id"] not in realizadas]
    avisos = [f"Metas específicas que ningún requisito realiza: {', '.join(sin_requisito)}."] if sin_requisito else []
    con_aviso = sum(1 for x in escritos if x["avisos"])
    if con_aviso:
        avisos.append(f"{con_aviso} requisito(s) con algo que revisar.")
    RequisitosEditables.model_validate({"requisitos": escritos})
    fecha = ahora()
    doc = {"proyecto_id": proyecto.proyecto_id, "fase": "requisitos", "contenido": {"requisitos": escritos},
           "huella_origen": huella_origen, "avisos": avisos, "modelo": ultimo.modelo if ultimo else None,
           "prompt_version": ultimo.prompt_version if ultimo else None, "generado": fecha, "actualizado": fecha,
           "historial": [{"fecha": fecha, "accion": "generar", "autor": "agentes",
                          "detalle": f"{len(escritos)} requisitos"}]}
    return DocumentosDeFase(deps.repo).guardar("requisitos", doc)


def editar(repo, previo: dict, nuevos: RequisitosEditables, entradas: list[dict], entrevistas: list[dict],
           metas: dict | None, extra_vagas: tuple[str, ...] = ()) -> dict:
    simbolos, validas = Simbolos(entradas), citas_validas(entrevistas)
    especificas = {m["id"] for m in (metas or {}).get("contenido", {}).get("metas", []) if m["nivel"] == "especifica"}
    requisitos = nuevos.model_dump(mode="json")["requisitos"]
    antes = {r["id"]: r for r in previo["contenido"]["requisitos"]}
    for r in requisitos:
        r["simbolos"], _ = simbolos.filtrar(r["simbolos"] + simbolos.mencionados(r["texto"]))
        r["evidencia"] = filtrar_citas(r["evidencia"], validas)
        r["metas"] = [m for m in r["metas"] if not especificas or m in especificas]
        r["avisos"] = avisos_de(r, extra_vagas)
    ids_estables(requisitos)
    despues = {r["id"]: r for r in requisitos}
    cambios = [f"agregó {i}" for i in despues.keys() - antes.keys()]
    cambios += [f"quitó {i}" for i in antes.keys() - despues.keys()]
    cambios += [f"corrigió {i}" for i in antes.keys() & despues.keys()
                if (antes[i]["texto"], antes[i]["tipo"], antes[i]["criterios"]) != (despues[i]["texto"], despues[i]["tipo"], despues[i]["criterios"])]
    n = sum(1 for i in antes.keys() & despues.keys() if despues[i]["validado"] and not antes[i]["validado"])
    if n:
        cambios.append(f"validó {n} requisito(s)")
    fecha = ahora()
    previo["contenido"] = {"requisitos": requisitos}
    previo["actualizado"] = fecha
    if cambios:
        previo["historial"].append({"fecha": fecha, "accion": "editar", "autor": "persona", "cambios": cambios})
    return DocumentosDeFase(repo).guardar("requisitos", previo)


# ---------------------------------------------------------------- la especificación completa

def a_markdown(proyecto, entrevistas: list[dict], entradas: list[dict], acuerdos: list[dict], mapa: dict | None,
               metas: dict | None, requisitos: dict | None) -> str:
    L: list[str] = [f"# Especificación de requisitos — {proyecto.nombre}", ""]
    if mapa:
        L += [f"> {mapa['contenido']['proposito']}", ""]
    if (proyecto.contexto or "").strip():
        L += ["## Contexto", "", proyecto.contexto.strip(), ""]

    L += ["## Entrevistas", ""]
    for e in entrevistas:
        quienes = ", ".join(f"{p['nombre']} ({p['rol']})" for p in (e.get("ficha") or {}).get("participantes", []))
        L.append(f"- **{e['entrevista_id']}** {e['titulo']} — {len(e['turnos'])} turnos" + (f"; {quienes}" if quienes else ""))
    L.append("")

    if requisitos:
        reqs = requisitos["contenido"]["requisitos"]
        for titulo, tipo in (("Requisitos funcionales", "funcional"), ("Requisitos no funcionales", "no_funcional")):
            del_tipo = [r for r in reqs if r["tipo"] == tipo]
            if not del_tipo:
                continue
            L += [f"## {titulo}", ""]
            for r in del_tipo:
                cat = f" · {r['categoria']}" if r.get("categoria") else ""
                L += [f"### {r['id']} · prioridad {r['prioridad']}{cat}", "", r["texto"], ""]
                if r["criterios"]:
                    L += ["**Criterios de aceptación**", "", *(f"- {c}" for c in r["criterios"]), ""]
                if r["supuestos"]:
                    L += ["**Supuestos**", "", *(f"- {s}" for s in r["supuestos"]), ""]
                traza = []
                if r["metas"]:
                    traza.append(f"metas {', '.join(r['metas'])}")
                if r["simbolos"]:
                    traza.append(f"términos {', '.join(r['simbolos'])}")
                if r["evidencia"]:
                    traza.append(f"entrevista {', '.join(r['evidencia'])}")
                if traza:
                    L += [f"*Trazabilidad:* {' · '.join(traza)}", ""]

    if metas:
        L += ["## Metas", ""]
        ms = metas["contenido"]["metas"]
        for mo in (m for m in ms if m["nivel"] == "organizacional"):
            L.append(f"- **{mo['id']}** (organización) {mo['enunciado']}")
            for me in (m for m in ms if m["contribuye_a"] == mo["id"]):
                L.append(f"  - **{me['id']}** (estratégica) {me['enunciado']}")
                for mx in (m for m in ms if m["contribuye_a"] == me["id"]):
                    ind = f" — *indicador:* {mx['indicador']}" if mx.get("indicador") else ""
                    L.append(f"    - **{mx['id']}** {mx['enunciado']}{ind}")
        L.append("")

    if mapa:
        c = mapa["contenido"]
        et = {x["id"]: x["etiqueta"] for x in c["conceptos"]}
        L += ["## Mapa conceptual", "", f"**Propósito:** {c['proposito']}", ""]
        L += [f"- {et[r['origen']]} — *{r['enlace']}* → {et[r['destino']]}" for r in c["relaciones"]
              if r["origen"] in et and r["destino"] in et]
        L.append("")

    L += ["## Léxico Extendido del Lenguaje (LEL)", ""]
    for e in validadas(entradas):
        L += [f"### {e['simbolo']} ({e['tipo']})", "", f"**Noción:** {' '.join(e['nocion'])}", "",
              f"**Intención:** {e['intencion']}", ""]
        if e["impacto"]:
            L += [f"**Impacto:** {' '.join(e['impacto'])}", ""]
        if e.get("sinonimos"):
            L += [f"**Sinónimos:** {', '.join(e['sinonimos'])}", ""]

    if acuerdos:
        L += ["## Acuerdos del proyecto", "", "Significados que una persona experta confirmó o corrigió.", ""]
        for a in sorted(acuerdos, key=lambda x: x["simbolo"].lower()):
            if a.get("descartado"):
                L.append(f"- **{a['simbolo']}**: no es un término del dominio.")
            else:
                no = f" No significa: {'; '.join(a['no_significa'])}." if a.get("no_significa") else ""
                L.append(f"- **{a['simbolo']}**: {a.get('significa')}.{no}")
        L.append("")

    if requisitos:
        L += ["## Matriz de trazabilidad", "", "| Requisito | Metas | Términos del LEL | Entrevista |", "|---|---|---|---|"]
        for r in requisitos["contenido"]["requisitos"]:
            L.append(f"| {r['id']} | {', '.join(r['metas']) or '—'} | {', '.join(r['simbolos']) or '—'} | "
                     f"{', '.join(r['evidencia']) or '—'} |")
        L.append("")
    return "\n".join(L).rstrip() + "\n"
