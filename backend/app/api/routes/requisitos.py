"""Procesar un requisito, seguir su traza en vivo, validarlo y borrarlo. Solo los
requisitos de los proyectos de la cuenta con sesión; los de otra cuenta responden 404."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ConfigDict, Field

from app.comparacion.ejecucion import COLECCION as COLECCION_COMPARACIONES
from app.evaluacion.modelos import COLECCION as COLECCION_EVALUACIONES
from app.models import (
    ESTADOS_TERMINALES,
    Categoria,
    CategoriaNoFuncional,
    EntradaLELFormalizada,
    Estado,
    TipoRequisito,
    Traza,
    Validacion,
)
from app.orchestration import ConflictoDeEstado, Servicio

from ..dependencias import TrazaDep, UsuarioDep, apagando, exigir_suyo, obtener_servicio, proyectos_de

router = APIRouter(tags=["requisitos"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]


class EntradaProcesar(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    texto: str = Field(min_length=1, max_length=2000)
    proyecto_id: str = Field(min_length=1)


class Aceptado(BaseModel):
    req_id: str
    estado: Estado


@router.post("/procesar", status_code=202, response_model=Aceptado)
def procesar(entrada: EntradaProcesar, srv: ServicioDep, usuario: UsuarioDep) -> Aceptado:
    """Registra el requisito en un proyecto de la cuenta y lo encola; los mensajes se siguen
    en `/eventos/{req_id}`."""
    exigir_suyo(srv, usuario, entrada.proyecto_id, f"el proyecto {entrada.proyecto_id}")
    try:
        req_id = srv.solicitar(entrada.texto, entrada.proyecto_id)
    except KeyError:
        raise HTTPException(404, f"No existe el proyecto {entrada.proyecto_id}")
    return Aceptado(req_id=req_id, estado=Estado.CARGADO)


@router.get("/trazas")
def trazas(srv: ServicioDep, usuario: UsuarioDep, proyecto_id: str | None = None) -> list[dict]:
    """Resumen de los requisitos de la cuenta, opcionalmente de uno de sus proyectos."""
    if proyecto_id is not None:
        exigir_suyo(srv, usuario, proyecto_id, f"el proyecto {proyecto_id}")
        return srv.trazas(proyecto_id)
    suyos = proyectos_de(srv, usuario)
    return [t for t in srv.trazas() if t["proyecto_id"] in suyos]


@router.get("/cola")
def cola(srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """Qué se está procesando y qué espera turno de la cuenta. La cola es una sola para
    todas: `de_otras_cuentas` cuenta los trabajos ajenos (sin decir cuáles)."""
    suyos = proyectos_de(srv, usuario)
    claves = {t["req_id"] for t in srv.trazas() if t["proyecto_id"] in suyos}
    for coleccion, campo in ((COLECCION_COMPARACIONES, "comparacion_id"), (COLECCION_EVALUACIONES, "evaluacion_id")):
        claves |= {d.get(campo) for d in srv.repo.listar_docs(coleccion) if d.get("proyecto_id") in suyos}
    estado = srv.cola.estado()
    todos = ([estado["en_proceso"]] if estado["en_proceso"] else []) + estado["pendientes"]
    propio = lambda t: t is not None and t["clave"] in claves  # noqa: E731
    return {"en_proceso": estado["en_proceso"] if propio(estado["en_proceso"]) else None,
            "pendientes": [t for t in estado["pendientes"] if propio(t)],
            "de_otras_cuentas": sum(not propio(t) for t in todos)}


@router.get("/traza/{req_id}", response_model=Traza)
def traza(t: TrazaDep) -> Traza:
    return t


@router.delete("/requisitos/{req_id}", status_code=204)
def borrar(t: TrazaDep, srv: ServicioDep) -> None:
    """Borra el requisito con lo que salió de él (entradas del LEL, documento formalizado).
    409 si se está analizando o espera turno."""
    try:
        srv.borrar_requisito(t.req_id)
    except ConflictoDeEstado as e:
        raise HTTPException(409, str(e)) from e


@router.get("/eventos/{req_id}", response_class=EventSourceResponse)
async def eventos(
    request: Request,
    srv: ServicioDep,
    t: TrazaDep,
    desde: int = 0,
    last_event_id: Annotated[str | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    """SSE: `mensaje` por cada mensaje nuevo (id = secuencia), `estado` en cada
    cambio de estado y `fin` al llegar a un estado terminal. Sondea el repositorio
    (ADR 0006). Al reconectar, `Last-Event-ID` evita repetir mensajes. Si el servidor
    se apaga, el stream termina sin `fin` y el navegador reconecta cuando vuelva."""
    enviados = desde
    if last_event_id and last_event_id.isdigit():
        enviados = max(enviados, int(last_event_id))
    ultimo_estado = None
    while True:
        actual = await run_in_threadpool(srv.traza, t.req_id)
        if actual is None:  # se borró mientras se seguía
            return
        for m in actual.mensajes:
            if m.secuencia > enviados:
                yield ServerSentEvent(data=m.model_dump(mode="json"), event="mensaje", id=str(m.secuencia))
                enviados = m.secuencia
        if actual.estado != ultimo_estado:
            ultimo_estado = actual.estado
            yield ServerSentEvent(data={"estado": actual.estado.value, "secuencia": enviados}, event="estado")
        if actual.estado in ESTADOS_TERMINALES:
            yield ServerSentEvent(data={"estado": actual.estado.value}, event="fin")
            return
        if await request.is_disconnected() or apagando(request):
            return
        await asyncio.sleep(srv.deps.settings.sse_intervalo_s)


@router.post("/validar/{req_id}", status_code=202)
def validar(req_id: str, validacion: Validacion, srv: ServicioDep, _: TrazaDep) -> dict:
    """Aprobar, rechazar o editar. `interpretaciones_editadas` lleva, por término,
    la interpretación elegida (otra existente) o reescrita. Se encola con prioridad."""
    try:
        srv.solicitar_validacion(req_id, validacion)
    except KeyError:
        raise HTTPException(404, f"No existe el requisito {req_id}")
    except ConflictoDeEstado as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"req_id": req_id, "decision": validacion.decision}


# ---------------------------------------------------------------- correcciones (ADR 0017)

class CorreccionFormalizacion(BaseModel):
    """Lo que la persona corrige del requisito formalizado; solo cambia lo que viene."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    requisito_reescrito: str | None = Field(None, min_length=1, max_length=2000)
    tipo_requisito: TipoRequisito | None = None
    categoria: CategoriaNoFuncional | None = None
    supuestos: list[Annotated[str, Field(min_length=1, max_length=400)]] | None = Field(None, max_length=10)


class CorreccionLEL(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    simbolo: str | None = Field(None, min_length=1, max_length=120)
    tipo: Categoria | None = None
    nocion: list[Annotated[str, Field(min_length=1, max_length=600)]] | None = Field(None, min_length=1, max_length=6)
    impacto: list[Annotated[str, Field(min_length=1, max_length=600)]] | None = Field(None, min_length=1, max_length=6)


def _cambios(c: BaseModel, anulables: tuple[str, ...] = ()) -> dict:
    """Los campos enviados; `null` solo cuenta en los que se pueden vaciar."""
    datos = c.model_dump(mode="json", exclude_unset=True)
    return {k: v for k, v in datos.items() if v is not None or k in anulables}


@router.patch("/requisitos/{req_id}/formalizacion")
def corregir_formalizacion(req_id: str, correccion: CorreccionFormalizacion, srv: ServicioDep, _: TrazaDep) -> dict:
    """Corrige el requisito reescrito, su tipo, categoría o supuestos. 409 si no está formalizado."""
    cambios = _cambios(correccion, anulables=("categoria",))
    if not cambios:
        raise HTTPException(422, "no hay nada que corregir")
    try:
        return srv.corregir_formalizacion(req_id, cambios)
    except KeyError:
        raise HTTPException(404, f"No existe el requisito {req_id}")
    except ConflictoDeEstado as e:
        raise HTTPException(409, str(e))


@router.patch("/requisitos/{req_id}/lel/{termino}", response_model=EntradaLELFormalizada)
def corregir_lel(req_id: str, termino: str, correccion: CorreccionLEL, srv: ServicioDep,
                 _: TrazaDep) -> EntradaLELFormalizada:
    """Corrige la entrada del LEL que salió de este requisito para `termino`."""
    cambios = _cambios(correccion)
    if not cambios:
        raise HTTPException(422, "no hay nada que corregir")
    try:
        return srv.corregir_lel(req_id, termino, cambios)
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))
    except ConflictoDeEstado as e:
        raise HTTPException(409, str(e))
