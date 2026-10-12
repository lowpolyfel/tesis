"""Dependencias de FastAPI: el servicio, la cuenta con sesión y lo que es de esa cuenta.

Toda ruta fuera de `/auth` y `/salud` exige sesión (`usuario_actual`, en `main.py`). Un
proyecto, requisito, documento, comparación o evaluación de otra cuenta responde 404,
igual que uno que no existe: no se revela qué hay en otras cuentas.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.auth import Usuario
from app.models import Traza
from app.orchestration import Servicio

COOKIE_SESION = "dudamel_sesion"


def obtener_servicio(request: Request) -> Servicio:
    return request.app.state.servicio


def usuario_actual(request: Request) -> Usuario:
    u = obtener_servicio(request).cuentas.sesion(request.cookies.get(COOKIE_SESION))
    if u is None:
        raise HTTPException(401, "Inicia sesión para continuar.")
    return u


UsuarioDep = Annotated[Usuario, Depends(usuario_actual)]


def apagando(request: Request) -> bool:
    """El servidor recibió la orden de apagarse (lo marca `main.py`): los SSE abiertos terminan."""
    evento = getattr(request.app.state, "apagando", None)
    return bool(evento and evento.is_set())


def es_suyo(srv: Servicio, usuario: Usuario, proyecto_id: str | None) -> bool:
    p = srv.proyectos.obtener(proyecto_id) if proyecto_id else None
    return p is not None and p.propietario == usuario.usuario_id


def proyectos_de(srv: Servicio, usuario: Usuario) -> set[str]:
    return {p.proyecto_id for p in srv.proyectos.listar(usuario.usuario_id)}


def exigir_suyo(srv: Servicio, usuario: Usuario, proyecto_id: str | None, que: str) -> None:
    if not es_suyo(srv, usuario, proyecto_id):
        raise HTTPException(404, f"No existe {que}")


def traza_existente(req_id: str, request: Request, usuario: UsuarioDep) -> Traza:
    srv = obtener_servicio(request)
    traza = srv.traza(req_id)
    if traza is None or not es_suyo(srv, usuario, traza.proyecto_id):
        raise HTTPException(404, f"No existe el requisito {req_id}")
    return traza


TrazaDep = Annotated[Traza, Depends(traza_existente)]
