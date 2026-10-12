"""Ficha del contexto del proyecto y triaje de requisitos contra ella (ADR 0022)."""
from __future__ import annotations

import json
import queue
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.preparacion import conexiones
from app.contexto import COLECCION_FICHAS, ficha_al_dia, generar_ficha, triar
from app.llm.perfiles import con_perfil
from app.models import Proyecto
from app.orchestration import Servicio

from ..dependencias import obtener_servicio
from .proyectos import ProyectoDep

router = APIRouter(tags=["contexto"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


class EntradaTriaje(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requisitos: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(min_length=1, max_length=200)


def _vista(p: Proyecto, doc: dict | None) -> dict:
    return {"ficha": doc, "al_dia": ficha_al_dia(doc, p.nombre, p.contexto),
            "tiene_contexto": bool((p.contexto or "").strip())}


@router.get("/proyectos/{proyecto_id}/ficha")
def ver_ficha(p: ProyectoDep, srv: ServicioDep) -> dict:
    """{ficha (con su JSON y su Markdown) | null, al_dia, tiene_contexto}. `al_dia` es falso si
    alguien editó el nombre o el contexto después de armarla."""
    return _vista(p, srv.repo.obtener_doc(COLECCION_FICHAS, p.proyecto_id))


@router.post("/proyectos/{proyecto_id}/ficha")
def armar_ficha(p: ProyectoDep, srv: ServicioDep) -> dict:
    """La arma (o la rehace) el Revisor. 422 sin contexto; 502 si el Revisor falla."""
    try:
        with con_perfil(srv.perfil(p.proyecto_id)):
            doc = generar_ficha(p, srv.deps.revisor, srv.repo)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # el LLM no respondió o no dio una ficha válida
        raise HTTPException(502, f"El Revisor no pudo armar la ficha ({type(e).__name__}: {str(e)[:200]})") from e
    return _vista(p, doc)


def _triaje(entrada: EntradaTriaje, p: Proyecto, srv: Servicio, avance=None) -> dict:
    avisar = avance or (lambda _e: None)
    perfil = srv.perfil(p.proyecto_id)
    doc = srv.repo.obtener_doc(COLECCION_FICHAS, p.proyecto_id)
    aviso_ficha = None
    if (p.contexto or "").strip() and not ficha_al_dia(doc, p.nombre, p.contexto):
        avisar({"tipo": "paso", "id": "ficha", "estado": "curso", "detalle": "el contexto cambió: el Revisor arma su ficha"})
        try:
            with con_perfil(perfil):
                doc = generar_ficha(p, srv.deps.revisor, srv.repo)
            avisar({"tipo": "paso", "id": "ficha", "estado": "ok", "detalle": "ficha del contexto lista"})
        except Exception as e:  # noqa: BLE001 — sin ficha nueva se compara con la anterior o con nada
            aviso_ficha = f"No se pudo armar la ficha del contexto ({type(e).__name__})."
            avisar({"tipo": "paso", "id": "ficha", "estado": "aviso", "detalle": aviso_ficha})
    else:
        avisar({"tipo": "paso", "id": "ficha", "estado": "ok",
                "detalle": "ficha del contexto al día" if doc else "el proyecto no tiene contexto"})
    md = doc["markdown"] if doc else None
    with con_perfil(perfil):
        r = triar([t.strip() for t in entrada.requisitos], md, srv.deps.revisor, avance=avance)
    avisos = [a for a in (aviso_ficha, r["aviso"]) if a]
    return {**r, "aviso": " ".join(avisos) or None,
            "ficha": {"al_dia": ficha_al_dia(doc, p.nombre, p.contexto), "creada": doc.get("creada")} if doc else None}


@router.post("/proyectos/{proyecto_id}/triaje")
def triaje(entrada: EntradaTriaje, p: ProyectoDep, srv: ServicioDep) -> dict:
    """Clasifica cada requisito contra la ficha del contexto: claro, ambiguo o incompleto, con su
    motivo y preguntas (no guarda nada). Si la ficha no está al día, primero la arma.
    {resultados: [...], modelo, aviso, ficha: {al_dia, creada} | null}."""
    return _triaje(entrada, p, srv)


@router.post("/proyectos/{proyecto_id}/triaje/flujo")
def triaje_en_vivo(entrada: EntradaTriaje, p: ProyectoDep, srv: ServicioDep) -> StreamingResponse:
    """Lo mismo, diciendo qué hace (NDJSON): {"tipo": "paso", id: "ficha", …} · {"tipo": "tanda", i,
    total, desde, hasta, requisitos, estado, cuenta} · {"tipo": "resultado", triaje} · {"tipo": "error", mensaje}."""
    eventos: queue.Queue = queue.Queue()

    def trabajar():
        try:
            u = p.propietario
            conexiones(srv.repo, srv.deps.settings, srv.perfiles.eleccion(u, "revisor"), eventos.put,
                       ollama_url=srv.perfiles.url_ollama(u))
            eventos.put({"tipo": "resultado", "triaje": _triaje(entrada, p, srv, avance=eventos.put)})
        except Exception as e:  # noqa: BLE001 — se informa en el flujo
            eventos.put({"tipo": "error", "mensaje": f"{type(e).__name__}: {e}"})
        eventos.put(None)

    threading.Thread(target=trabajar, daemon=True).start()

    def lineas():
        while (e := eventos.get()) is not None:
            yield json.dumps(e, ensure_ascii=False) + "\n"
    return StreamingResponse(lineas(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})
