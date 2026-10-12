"""Qué proveedor y modelo usa cada agente para la cuenta con sesión (ADR 0021).

Las claves de API se guardan cifradas y nunca salen: GET dice si hay una y sus
últimos cuatro caracteres."""
from __future__ import annotations

from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.llm import PromptRenderizado
from app.llm.proveedores import CATALOGO, POR_ID, FalloProveedor, crear_cliente_de
from app.orchestration import Servicio

from ..dependencias import UsuarioDep, obtener_servicio

router = APIRouter(tags=["modelos"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]
PRUEBA = PromptRenderizado("prueba_proveedor", "Respondes solo JSON.", 'Responde exactamente {"ok": true}')


class Eleccion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    proveedor: str = Field(min_length=1, max_length=40)
    modelo: str = Field(min_length=1, max_length=200)


class DatosProveedor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str | None = Field(None, max_length=300)
    api_key: str | None = Field("", max_length=500)  # "" deja la guardada; null la borra


class CambiosModelos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agentes: dict[str, Eleccion | None] = {}  # null: volver al del servidor
    proveedores: dict[str, DatosProveedor] = {}


class EntradaPrueba(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    proveedor: str = Field(min_length=1, max_length=40)
    modelo: str = Field(min_length=1, max_length=200)
    base_url: str | None = Field(None, max_length=300)
    api_key: str | None = Field(None, max_length=500)  # vacía: la guardada


@router.get("/cuenta/modelos")
def ver(srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """{catalogo, agentes: [{rol, nombre, proveedor, modelo, propio, servidor}], proveedores:
    {id: {base_url, tiene_clave, final}}}. Las elecciones del servidor son las del .env."""
    return {"catalogo": [p.publico() for p in CATALOGO], **srv.perfiles.publico(usuario.usuario_id)}


@router.put("/cuenta/modelos")
def guardar(cambios: CambiosModelos, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    try:
        datos = srv.perfiles.guardar(
            usuario.usuario_id, {r: (e.model_dump() if e else None) for r, e in cambios.agentes.items()},
            {pid: d.model_dump(exclude_unset=True) for pid, d in cambios.proveedores.items()})
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"catalogo": [p.publico() for p in CATALOGO], **datos}


@router.post("/cuenta/modelos/probar")
def probar(entrada: EntradaPrueba, srv: ServicioDep, usuario: UsuarioDep) -> dict:
    """Una llamada mínima con lo que está en el formulario (o la clave guardada): {ok, ms, error}."""
    p = POR_ID.get(entrada.proveedor)
    if p is None:
        raise HTTPException(422, f"proveedor desconocido: {entrada.proveedor}")
    clave = (entrada.api_key or "").strip() or srv.perfiles.clave_guardada(usuario.usuario_id, p.id)
    if p.pide_clave and not clave:
        return {"ok": False, "ms": None, "error": f"Falta la clave de {p.nombre}."}
    base = (entrada.base_url or "").strip() or srv.perfiles.url_guardada(usuario.usuario_id, p.id)
    t0 = perf_counter()
    try:
        cliente = crear_cliente_de({"proveedor": p.id, "modelo": entrada.modelo, "base_url": base, "api_key": clave},
                                   srv.deps.settings)
        respuesta = cliente.completar(PRUEBA, {"type": "object"})
    except (FalloProveedor, TimeoutError) as e:
        return {"ok": False, "ms": None, "error": str(e)}
    except Exception as e:  # noqa: BLE001 — p. ej. Ollama sin el modelo: se informa, no se cae
        return {"ok": False, "ms": None, "error": f"{type(e).__name__}: {str(e)[:300]}"}
    return {"ok": True, "ms": round((perf_counter() - t0) * 1000), "error": None, "respuesta": respuesta[:120]}

