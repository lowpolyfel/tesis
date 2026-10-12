"""Cuentas: registro con código por correo, entrar, salir y restablecer la contraseña.

La sesión viaja en una cookie HttpOnly (`dudamel_sesion`, SameSite=Lax): el frontend
no ve el token y `EventSource` la manda sola. Los errores responden
`{detail: {codigo, mensaje}}`; `codigo` le dice al frontend qué pantalla mostrar
(p. ej. `sin_verificar` lleva a escribir el código).
"""
from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import ErrorCorreo, ErrorCuenta, EsperaReenvio, UsuarioPublico, normalizar_correo, publico
from app.orchestration import Servicio

from ..dependencias import COOKIE_SESION, UsuarioDep, obtener_servicio

router = APIRouter(prefix="/auth", tags=["cuentas"])
ServicioDep = Annotated[Servicio, Depends(obtener_servicio)]

_PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _ConCorreo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    correo: str = Field(min_length=3, max_length=254)

    @field_validator("correo")
    @classmethod
    def _correo_valido(cls, v: str) -> str:
        v = normalizar_correo(v)
        if not _PATRON_CORREO.match(v):
            raise ValueError("escribe un correo válido, como nombre@dominio.com")
        return v


Contrasena = Annotated[str, Field(min_length=8, max_length=128)]
CodigoSeis = Annotated[str, Field(pattern=r"^\d{6}$")]


class EntradaRegistro(_ConCorreo):
    nombre: str = Field(min_length=1, max_length=80)
    contrasena: Contrasena


class EntradaEntrar(_ConCorreo):
    contrasena: str = Field(min_length=1, max_length=128)


class EntradaCodigo(_ConCorreo):
    codigo: CodigoSeis


class EntradaRestablecer(_ConCorreo):
    codigo: CodigoSeis
    contrasena: Contrasena


def _error(e: ErrorCuenta | ErrorCorreo) -> HTTPException:
    if isinstance(e, ErrorCorreo):
        return HTTPException(502, {"codigo": "correo", "mensaje": str(e)})
    detalle = {"codigo": e.codigo, "mensaje": str(e)}
    if isinstance(e, EsperaReenvio):
        detalle["segundos"] = e.segundos
    return HTTPException(e.estado, detalle)


def _con_sesion(respuesta: Response, srv: Servicio, usuario) -> UsuarioPublico:
    s = srv.deps.settings
    respuesta.set_cookie(COOKIE_SESION, srv.cuentas.abrir_sesion(usuario), max_age=s.sesion_dias * 86400,
                         httponly=True, samesite="lax", secure=s.sesion_cookie_segura, path="/")
    return publico(usuario)


def _pendiente(srv: Servicio, correo: str, que: str) -> dict:
    """Respuesta cuando falta escribir un código. `sin_smtp`: el código está en la consola del backend."""
    return {"pendiente": que, "correo": correo, "sin_smtp": not srv.cuentas.correo.configurado,
            "minutos": srv.deps.settings.codigo_minutos}


@router.post("/registro", status_code=201)
def registro(entrada: EntradaRegistro, srv: ServicioDep) -> dict:
    """Crea la cuenta sin verificar y manda el código al correo. 409 si el correo ya tiene cuenta."""
    try:
        srv.cuentas.registrar(entrada.nombre, entrada.correo, entrada.contrasena)
    except (ErrorCuenta, ErrorCorreo) as e:
        raise _error(e) from e
    return _pendiente(srv, entrada.correo, "registro")


@router.post("/verificar", response_model=UsuarioPublico)
def verificar(entrada: EntradaCodigo, srv: ServicioDep, respuesta: Response) -> UsuarioPublico:
    """Código de registro o de entrar: verifica el correo y abre la sesión."""
    try:
        u = srv.cuentas.verificar(entrada.correo, entrada.codigo)
    except ErrorCuenta as e:
        raise _error(e) from e
    return _con_sesion(respuesta, srv, u)


@router.post("/reenviar", status_code=202)
def reenviar(entrada: _ConCorreo, srv: ServicioDep) -> dict:
    """Otro código para lo pendiente. 429 con `segundos` si se pidió hace muy poco."""
    try:
        srv.cuentas.reenviar(entrada.correo)
    except (ErrorCuenta, ErrorCorreo) as e:
        raise _error(e) from e
    return {"enviado": True}


@router.post("/entrar")
def entrar(entrada: EntradaEntrar, srv: ServicioDep, respuesta: Response) -> dict:
    """Correo y contraseña. Devuelve la cuenta (y la cookie) o, si se exige código al
    entrar, 202 con `pendiente: "entrar"`. 403 `sin_verificar` si falta confirmar el correo."""
    try:
        u, falta_codigo = srv.cuentas.entrar(entrada.correo, entrada.contrasena)
    except (ErrorCuenta, ErrorCorreo) as e:
        raise _error(e) from e
    if falta_codigo:
        respuesta.status_code = 202
        return _pendiente(srv, entrada.correo, "entrar")
    return _con_sesion(respuesta, srv, u).model_dump(mode="json")


@router.post("/salir", status_code=204)
def salir(request: Request, srv: ServicioDep, respuesta: Response) -> None:
    srv.cuentas.cerrar_sesion(request.cookies.get(COOKIE_SESION))
    respuesta.delete_cookie(COOKIE_SESION, path="/", samesite="lax", httponly=True)


@router.get("/yo", response_model=UsuarioPublico)
def yo(usuario: UsuarioDep) -> UsuarioPublico:
    """La cuenta con sesión; 401 si no hay."""
    return publico(usuario)


@router.post("/recuperar", status_code=202)
def recuperar(entrada: _ConCorreo, srv: ServicioDep) -> dict:
    """Manda un código para elegir otra contraseña. Responde igual exista o no la cuenta."""
    try:
        srv.cuentas.recuperar(entrada.correo)
    except ErrorCorreo as e:
        raise _error(e) from e
    return _pendiente(srv, entrada.correo, "restablecer")


@router.post("/restablecer", response_model=UsuarioPublico)
def restablecer(entrada: EntradaRestablecer, srv: ServicioDep, respuesta: Response) -> UsuarioPublico:
    """Código y contraseña nueva: cierra las demás sesiones y abre una."""
    try:
        u = srv.cuentas.restablecer(entrada.correo, entrada.codigo, entrada.contrasena)
    except ErrorCuenta as e:
        raise _error(e) from e
    return _con_sesion(respuesta, srv, u)
