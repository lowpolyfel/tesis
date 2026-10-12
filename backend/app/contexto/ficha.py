"""Ficha del contexto del proyecto (ADR 0022).

El contexto general es texto libre. La ficha lo ordena (resumen, objetivo, actores,
conceptos, procesos, reglas, fuera de alcance y vacíos) para que sea fácil de leer y
de comparar: el triaje le compara cada requisito. Se guarda en `fichas_contexto`, una
por proyecto, en JSON y en Markdown, con la huella del nombre y el contexto de los
que salió: si alguien edita el contexto, la ficha deja de estar al día.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

COLECCION = "fichas_contexto"


def huella_contexto(nombre: str, contexto: str | None) -> str:
    return hashlib.sha256(f"{nombre}\n{(contexto or '').strip()}".encode()).hexdigest()


def ficha_al_dia(doc: dict | None, nombre: str, contexto: str | None) -> bool:
    return bool(doc) and doc.get("huella") == huella_contexto(nombre, contexto)


def _lista(titulo: str, elementos: list[str]) -> list[str]:
    return [f"## {titulo}", "", *(f"- {e}" for e in elementos), ""] if elementos else []


def a_markdown(nombre: str, f: dict) -> str:
    """La ficha como Markdown: es lo que lee el triaje y lo que se descarga."""
    lineas = [f"# {nombre}", "", f["resumen"], "", f"**Objetivo:** {f['objetivo']}", ""]
    lineas += _lista("Actores", [f"**{a['nombre']}**: {a['rol']}" for a in f.get("actores", [])])
    lineas += _lista("Conceptos del dominio", [f"**{c['termino']}**: {c['significado']}" for c in f.get("conceptos", [])])
    lineas += _lista("Procesos", f.get("procesos", []))
    lineas += _lista("Reglas del negocio", f.get("reglas", []))
    lineas += _lista("Fuera de alcance", f.get("fuera_de_alcance", []))
    lineas += _lista("Lo que el contexto no dice", f.get("vacios", []))
    return "\n".join(lineas).rstrip() + "\n"


def generar_ficha(proyecto, revisor, repo) -> dict:
    """Pide la ficha al Revisor y la guarda. Sin contexto no hay ficha que armar (ValueError)."""
    contexto = (proyecto.contexto or "").strip()
    if not contexto:
        raise ValueError("El proyecto no tiene contexto general: escríbelo para armar su ficha.")
    r = revisor.ficha(proyecto.nombre, contexto)
    ficha = r.valor.model_dump(mode="json")
    doc = {"proyecto_id": proyecto.proyecto_id, "huella": huella_contexto(proyecto.nombre, proyecto.contexto),
           "ficha": ficha, "markdown": a_markdown(proyecto.nombre, ficha), "modelo": r.modelo,
           "prompt_version": r.prompt_version, "creada": datetime.now(UTC).isoformat(timespec="seconds")}
    repo.guardar_doc(COLECCION, proyecto.proyecto_id, doc)
    return doc
