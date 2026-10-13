"""Las fases del proyecto después de la entrevista (ADR 0024).

- `/proyectos/{id}/fases`: en qué va cada fase y cuál sigue.
- LEL interactivo: `/proyectos/{id}/lexico` y las acciones de la persona experta sobre cada
  entrada (`/lexico/{id}/validar|corregir|descartar|restaurar`); lo aprendido en
  `/proyectos/{id}/memoria`.
- Mapa, metas y requisitos: `/proyectos/{id}/fases/{fase}` (GET el documento, PUT lo que la
  persona editó y validó), `/generar` (NDJSON con el avance) y `/conservar` (seguir con el
  documento aunque lo de atrás haya cambiado).
- La especificación completa en Markdown: `/proyectos/{id}/fases/requisitos/markdown`.
"""
from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.fases import mapa as fase_mapa
from app.fases import metas as fase_metas
from app.fases import requisitos as fase_requisitos
from app.fases.documento import DocumentosDeFase, ahora, estado_del_proyecto
from app.fases.lexico import ErrorLexico, Lexico
from app.fases.lexico import resumen as resumen_lexico
from app.fases.progreso import EnCurso, en_cola, ocupado
from app.llm.perfiles import con_perfil
from app.models import (
    CambiosEntradaLexico,
    EntradaLexicoNueva,
    MapaEditable,
    MetasEditables,
    Proyecto,
    RequisitosEditables,
)
from app.orchestration import Servicio

from ..dependencias import UsuarioDep, es_suyo, obtener_servicio
from .proyectos import ProyectoDep, ServicioDep

router = APIRouter(tags=["fases"])
Fase = Literal["mapa", "metas", "requisitos"]


class EntradaCorreccion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cambios: CambiosEntradaLexico = CambiosEntradaLexico()
    alternativa: str | None = Field(None, pattern=r"^I\d+$")  # partir de otra intención de los agentes


class EntradaDescarte(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: str | None = Field(None, max_length=300)


class EntradaFase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contenido: dict


# ---------------------------------------------------------------- insumos

def _insumos(srv: Servicio, proyecto_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    lexico = Lexico(srv.repo)
    return lexico.listar(proyecto_id), lexico.memoria.listar(proyecto_id), srv.entrevistas.almacen.listar(proyecto_id)


def _estado(srv: Servicio, proyecto_id: str) -> dict:
    entradas, acuerdos, entrevistas = _insumos(srv, proyecto_id)
    return estado_del_proyecto(srv.repo, proyecto_id, entrevistas, entradas, acuerdos,
                               set(srv.entrevistas.ocupadas_del_proyecto(proyecto_id)))


def _fase(estado: dict, fase: str) -> dict:
    return next(f for f in estado["fases"] if f["id"] == fase)


@router.get("/proyectos/{proyecto_id}/fases")
def fases(p: ProyectoDep, srv: ServicioDep) -> dict:
    """{fases: [{id, disponible, hecho, motivo, …}], siguiente, entrevistas, lexico}."""
    return _estado(srv, p.proyecto_id)


# ---------------------------------------------------------------- LEL interactivo

def entrada_existente(entrada_id: str, request: Request, usuario: UsuarioDep) -> dict:
    srv = obtener_servicio(request)
    e = Lexico(srv.repo).obtener(entrada_id)
    if e is None or not es_suyo(srv, usuario, e["proyecto_id"]):
        raise HTTPException(404, f"No existe el término {entrada_id}")
    return e


EntradaDep = Annotated[dict, Depends(entrada_existente)]


@router.get("/proyectos/{proyecto_id}/lexico")
def lexico(p: ProyectoDep, srv: ServicioDep) -> dict:
    """{entradas, resumen, acuerdos, procesando}. `procesando`: hay entrevistas en la cola."""
    entradas, acuerdos, _ = _insumos(srv, p.proyecto_id)
    entradas.sort(key=lambda e: ({"propuesto": 0, "corregido": 1, "validado": 1, "descartado": 2}[e["estado"]],
                                 not e.get("ambiguedad"), e["simbolo"].lower()))
    return {"entradas": entradas, "resumen": resumen_lexico(entradas), "acuerdos": acuerdos,
            "procesando": len(srv.entrevistas.ocupadas_del_proyecto(p.proyecto_id))}


@router.post("/proyectos/{proyecto_id}/lexico", status_code=201)
def agregar(nueva: EntradaLexicoNueva, p: ProyectoDep, srv: ServicioDep) -> dict:
    try:
        return Lexico(srv.repo).agregar(p.proyecto_id, nueva, ahora())
    except ErrorLexico as e:
        raise HTTPException(409, str(e)) from e


def _accion(fn):
    try:
        return fn()
    except ErrorLexico as e:
        raise HTTPException(409, str(e)) from e


@router.post("/lexico/{entrada_id}/validar")
def validar(e: EntradaDep, srv: ServicioDep) -> dict:
    return _accion(lambda: Lexico(srv.repo).validar(e, ahora()))


@router.post("/lexico/{entrada_id}/corregir")
def corregir(entrada: EntradaCorreccion, e: EntradaDep, srv: ServicioDep) -> dict:
    """La persona cambia lo que haga falta (o parte de otra intención de los agentes). Se guarda
    y el sistema lo aprende como acuerdo del proyecto."""
    return _accion(lambda: Lexico(srv.repo).corregir(e, entrada.cambios, ahora(), entrada.alternativa))


@router.post("/lexico/{entrada_id}/descartar")
def descartar(entrada: EntradaDescarte, e: EntradaDep, srv: ServicioDep) -> dict:
    return _accion(lambda: Lexico(srv.repo).descartar(e, ahora(), entrada.motivo))


@router.post("/lexico/{entrada_id}/restaurar")
def restaurar(e: EntradaDep, srv: ServicioDep) -> dict:
    return _accion(lambda: Lexico(srv.repo).restaurar(e, ahora()))


@router.post("/proyectos/{proyecto_id}/lexico/validar-sin-ambiguedad")
def validar_en_bloque(p: ProyectoDep, srv: ServicioDep) -> dict:
    """Valida de una vez los términos propuestos en los que los agentes no vieron ambigüedad."""
    return {"validadas": Lexico(srv.repo).validar_sin_ambiguedad(p.proyecto_id, ahora())}


@router.get("/proyectos/{proyecto_id}/memoria")
def memoria(p: ProyectoDep, srv: ServicioDep) -> list[dict]:
    return Lexico(srv.repo).memoria.listar(p.proyecto_id)


@router.delete("/memoria/{aprendizaje_id}")
def olvidar(aprendizaje_id: str, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """Olvida un acuerdo: las entrevistas siguientes vuelven a interpretar ese término."""
    m = Lexico(srv.repo).memoria
    a = m.obtener(aprendizaje_id)
    if a is None or not es_suyo(srv, usuario, a["proyecto_id"]):
        raise HTTPException(404, f"No existe el acuerdo {aprendizaje_id}")
    m.olvidar(aprendizaje_id)
    return {"olvidado": aprendizaje_id}


# ---------------------------------------------------------------- mapa, metas y requisitos

def _vista_fase(srv: Servicio, p: Proyecto, fase: str) -> dict:
    estado = _estado(srv, p.proyecto_id)
    info = _fase(estado, fase)
    return {"documento": DocumentosDeFase(srv.repo).obtener(fase, p.proyecto_id), "al_dia": info["al_dia"],
            "disponible": info["disponible"], "motivo": info["motivo"], "hecho": info["hecho"],
            "generando": ocupado(f"{fase}:{p.proyecto_id}")}


@router.get("/proyectos/{proyecto_id}/fases/{fase}")
def ver_fase(fase: Fase, p: ProyectoDep, srv: ServicioDep) -> dict:
    """{documento | null, al_dia, disponible, motivo, hecho, generando}."""
    return _vista_fase(srv, p, fase)


@router.post("/proyectos/{proyecto_id}/fases/{fase}/generar")
def generar(fase: Fase, p: ProyectoDep, srv: ServicioDep) -> StreamingResponse:
    """Genera la fase con el Modelador y va diciendo qué hace (NDJSON): {"tipo": "paso", …} ·
    {"tipo": "resultado", documento} · {"tipo": "error", mensaje}. 409 si la fase todavía no se
    abre (falta validar la anterior) o si ya se está generando."""
    info = _fase(_estado(srv, p.proyecto_id), fase)
    if not info["disponible"]:
        raise HTTPException(409, info["motivo"])
    docs = DocumentosDeFase(srv.repo)

    def trabajo(avisar):
        with con_perfil(srv.perfil(p.proyecto_id)):
            entradas, acuerdos, entrevistas = _insumos(srv, p.proyecto_id)
            huellas = docs.huellas(p.proyecto_id, entradas, acuerdos)
            previo = docs.obtener(fase, p.proyecto_id)
            if fase == "mapa":
                doc = fase_mapa.generar(srv.deps, p, entradas, acuerdos, entrevistas, huellas["mapa"], avisar)
            elif fase == "metas":
                doc = fase_metas.generar(srv.deps, p, entradas, acuerdos, entrevistas, docs.obtener("mapa", p.proyecto_id),
                                         huellas["metas"], avisar)
            else:
                doc = fase_requisitos.generar(srv.deps, p, entradas, acuerdos, entrevistas,
                                              docs.obtener("mapa", p.proyecto_id), docs.obtener("metas", p.proyecto_id),
                                              huellas["requisitos"], avisar)
            if previo:  # el historial sigue de una versión a la siguiente
                doc["historial"] = previo.get("historial", []) + doc["historial"]
                doc = docs.guardar(fase, doc)
        avisar({"tipo": "resultado", "documento": doc})

    try:
        eventos = en_cola(srv.cola, f"{fase}:{p.proyecto_id}", trabajo)
    except EnCurso as e:
        raise HTTPException(409, "Ya se está generando; espera a que termine.") from e
    lineas = (json.dumps(e, ensure_ascii=False) + "\n" for e in eventos)
    return StreamingResponse(lineas, media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


@router.put("/proyectos/{proyecto_id}/fases/{fase}")
def editar(fase: Fase, entrada: EntradaFase, p: ProyectoDep, srv: ServicioDep) -> dict:
    """Guarda lo que la persona editó y validó (el contenido completo). El documento queda validado
    cuando cada componente lo está."""
    docs = DocumentosDeFase(srv.repo)
    previo = docs.obtener(fase, p.proyecto_id)
    if previo is None:
        raise HTTPException(404, "Todavía no se genera esta fase.")
    if ocupado(f"{fase}:{p.proyecto_id}"):
        raise HTTPException(409, "Se está generando de nuevo; espera a que termine.")
    entradas, _, entrevistas = _insumos(srv, p.proyecto_id)
    try:
        if fase == "mapa":
            doc = fase_mapa.editar(srv.repo, previo, MapaEditable.model_validate(entrada.contenido), entradas)
        elif fase == "metas":
            doc = fase_metas.editar(srv.repo, previo, MetasEditables.model_validate(entrada.contenido), entradas,
                                    entrevistas)
        else:
            vagas = tuple(t["expresion"] for t in srv.deps.filtros.catalogos.vaguedad.entradas)
            doc = fase_requisitos.editar(srv.repo, previo, RequisitosEditables.model_validate(entrada.contenido),
                                         entradas, entrevistas, docs.obtener("metas", p.proyecto_id), vagas)
    except ValueError as e:  # ValidationError incluido: el contenido no es válido
        raise HTTPException(422, str(e)) from e
    return {**_vista_fase(srv, p, fase), "documento": doc}


@router.post("/proyectos/{proyecto_id}/fases/{fase}/conservar")
def conservar(fase: Fase, p: ProyectoDep, srv: ServicioDep) -> dict:
    """Lo de atrás cambió, pero la persona decide seguir con este documento: queda al día."""
    docs = DocumentosDeFase(srv.repo)
    doc = docs.obtener(fase, p.proyecto_id)
    if doc is None:
        raise HTTPException(404, "Todavía no se genera esta fase.")
    entradas, acuerdos, _ = _insumos(srv, p.proyecto_id)
    doc["huella_origen"] = docs.huellas(p.proyecto_id, entradas, acuerdos)[fase]
    doc["historial"].append({"fecha": ahora(), "accion": "conservar", "autor": "persona",
                             "detalle": "se conserva aunque cambió lo validado antes"})
    docs.guardar(fase, doc)
    return _vista_fase(srv, p, fase)


@router.get("/proyectos/{proyecto_id}/fases/mapa/mermaid", response_class=PlainTextResponse)
def mapa_mermaid(p: ProyectoDep, srv: ServicioDep) -> str:
    doc = DocumentosDeFase(srv.repo).obtener("mapa", p.proyecto_id)
    if doc is None:
        raise HTTPException(404, "Todavía no se genera el mapa.")
    return fase_mapa.a_mermaid(doc["contenido"])


@router.get("/proyectos/{proyecto_id}/fases/requisitos/markdown", response_class=PlainTextResponse)
def especificacion(p: ProyectoDep, srv: ServicioDep) -> PlainTextResponse:
    """La especificación completa: requisitos, metas, mapa, LEL, acuerdos y trazabilidad."""
    entradas, acuerdos, entrevistas = _insumos(srv, p.proyecto_id)
    docs = DocumentosDeFase(srv.repo)
    md = fase_requisitos.a_markdown(p, [e for e in entrevistas if e["estado"] == "lista"], entradas, acuerdos,
                                    docs.obtener("mapa", p.proyecto_id), docs.obtener("metas", p.proyecto_id),
                                    docs.obtener("requisitos", p.proyecto_id))
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")
