"""Dependencias de FastAPI: el servicio de orquestación y la traza pedida."""
from fastapi import HTTPException, Request

from app.models import Traza
from app.orchestration import Servicio


def obtener_servicio(request: Request) -> Servicio:
    return request.app.state.servicio


def apagando(request: Request) -> bool:
    """El servidor recibió la orden de apagarse (lo marca `main.py`): los SSE abiertos terminan."""
    evento = getattr(request.app.state, "apagando", None)
    return bool(evento and evento.is_set())


def traza_existente(req_id: str, request: Request) -> Traza:
    traza = obtener_servicio(request).traza(req_id)
    if traza is None:
        raise HTTPException(404, f"No existe el requisito {req_id}")
    return traza
