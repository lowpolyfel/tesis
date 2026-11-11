"""Cuestionario de evaluación de la experiencia (ADR 0032, `docs/cuestionario-evaluacion.md`).

- `GET /cuestionario`: si la cuenta ya puede contestarlo, las preguntas y su respuesta guardada.
- `PUT /cuestionario`: guarda lo contestado hasta ahora (borrador; se puede dejar a medias).
- `POST /cuestionario/enviar`: lo da por terminado; exige todas las obligatorias.
- `GET /cuestionario/resultados`, `/resultados.csv` y `/resultados/overleaf.zip` (LaTeX con
  figuras): lo agregado y anónimo, solo para los correos de `CUESTIONARIO_ADMINS` (ADR 0033).

Se abre cuando la cuenta tiene al menos un proyecto que llegó a la quinta fase (existe su
documento de requisitos). Hay un cuestionario por cuenta: el id del documento es el de la
cuenta, solo para que no se conteste dos veces; los resultados y el CSV no la incluyen.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict

from app import cuestionario as cq
from app.auth import Usuario
from app.cuestionario.latex import paquete_overleaf
from app.fases.documento import DocumentosDeFase
from app.orchestration import Servicio

from ..dependencias import UsuarioDep
from .proyectos import ServicioDep

router = APIRouter(tags=["cuestionario"])


class EntradaCuestionario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    respuestas: dict[str, object] = {}


def proyectos_terminados(srv: Servicio, usuario: Usuario) -> list[dict]:
    """Los proyectos de la cuenta que llegaron a requisitos (la quinta fase)."""
    docs = DocumentosDeFase(srv.repo)
    return [{"proyecto_id": p.proyecto_id, "nombre": p.nombre}
            for p in srv.proyectos.listar(usuario.usuario_id) if docs.obtener("requisitos", p.proyecto_id)]


def es_admin(srv: Servicio, usuario: Usuario) -> bool:
    return usuario.correo.lower() in srv.deps.settings.admins_cuestionario()


def _resumen(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    return {k: doc.get(k) for k in ("respuestas", "estado", "sus", "creado", "actualizado", "enviado")}


def _exigir_disponible(srv: Servicio, usuario: Usuario) -> None:
    if not proyectos_terminados(srv, usuario):
        raise HTTPException(403, "El cuestionario se abre cuando termines un proyecto hasta la fase de requisitos.")


def _etiqueta(qid: str) -> str:
    p = cq.PREGUNTAS.get(qid)
    return f"pregunta {p['n']}" if p else qid


def _validas(respuestas: dict) -> dict:
    limpias, errores = cq.limpiar(respuestas)
    if errores:
        raise HTTPException(422, {"mensaje": "Hay respuestas que no son válidas.",
                                  "errores": [f"{_etiqueta(e['id'])}: {e['motivo']}" for e in errores]})
    return limpias


@router.get("/cuestionario")
def obtener(srv: ServicioDep, usuario: UsuarioDep) -> dict:
    terminados = proyectos_terminados(srv, usuario)
    disponible = bool(terminados)
    return {
        "disponible": disponible,
        "motivo": None if disponible else
        "Se abre cuando termines al menos un proyecto con sus cinco fases (hasta los requisitos).",
        "proyectos_terminados": terminados,
        "preguntas": cq.publico() if disponible else None,
        "respuesta": _resumen(srv.repo.obtener_doc(cq.COLECCION, usuario.usuario_id)),
        "es_admin": es_admin(srv, usuario),
    }


@router.put("/cuestionario")
def guardar(entrada: EntradaCuestionario, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """Guarda el borrador. Si ya se envió, se puede corregir, pero sin dejar obligatorias vacías."""
    _exigir_disponible(srv, usuario)
    limpias = _validas(entrada.respuestas)
    doc = srv.repo.obtener_doc(cq.COLECCION, usuario.usuario_id) or cq.nuevo(usuario.usuario_id)
    if doc["estado"] == "enviado":
        if falta := cq.faltantes(limpias):
            raise HTTPException(422, {"mensaje": "El cuestionario ya se envió: no puede quedar sin contestar "
                                                 "una pregunta obligatoria.", "faltantes": falta})
        doc["sus"] = cq.puntaje_sus(limpias)
    doc.update(respuestas=limpias, actualizado=cq.ahora())
    srv.repo.guardar_doc(cq.COLECCION, usuario.usuario_id, doc)
    return _resumen(doc)


@router.post("/cuestionario/enviar")
def enviar(entrada: EntradaCuestionario, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    _exigir_disponible(srv, usuario)
    limpias = _validas(entrada.respuestas)
    if falta := cq.faltantes(limpias):
        raise HTTPException(422, {"mensaje": f"Faltan {len(falta)} pregunta(s) obligatoria(s).", "faltantes": falta})
    doc = srv.repo.obtener_doc(cq.COLECCION, usuario.usuario_id) or cq.nuevo(usuario.usuario_id)
    doc.update(respuestas=limpias, estado="enviado", sus=cq.puntaje_sus(limpias), actualizado=cq.ahora(),
               enviado=doc.get("enviado") or cq.ahora())
    srv.repo.guardar_doc(cq.COLECCION, usuario.usuario_id, doc)
    return _resumen(doc)


def _exigir_admin(srv: Servicio, usuario: Usuario) -> list[dict]:
    if not es_admin(srv, usuario):
        raise HTTPException(403, "Solo quien coordina la evaluación ve los resultados (CUESTIONARIO_ADMINS).")
    return srv.repo.listar_docs(cq.COLECCION)


@router.get("/cuestionario/resultados")
def resultados(srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """Lo agregado, con las preguntas y los grupos de escalas para que la página de resultados los grafique."""
    return {**cq.resultados(_exigir_admin(srv, usuario)), "cuestionario": cq.publico(), "grupos": cq.GRUPOS_ESCALA}


@router.get("/cuestionario/resultados/overleaf.zip")
def resultados_overleaf(srv: ServicioDep, usuario: UsuarioDep) -> Response:
    """Paquete LaTeX (pgfplots y booktabs) con figuras, tablas y datos; compila en Overleaf (ADR 0033)."""
    fecha = cq.ahora()[:10]
    return Response(paquete_overleaf(_exigir_admin(srv, usuario), fecha), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="cuestionario-dudamel-{fecha}.zip"'})


@router.get("/cuestionario/resultados.csv", response_class=PlainTextResponse)
def resultados_csv(srv: ServicioDep, usuario: UsuarioDep) -> PlainTextResponse:
    salida = io.StringIO()
    csv.writer(salida).writerows(cq.filas_csv(_exigir_admin(srv, usuario)))
    # con BOM para que Excel lea bien los acentos
    return PlainTextResponse("﻿" + salida.getvalue(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="cuestionario-dudamel.csv"'})
