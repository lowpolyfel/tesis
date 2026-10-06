"""Entradas formalizadas del LEL."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.models import EntradaLELFormalizada
from app.orchestration import Servicio

from ..dependencias import obtener_servicio

router = APIRouter(tags=["lel"])


@router.get("/lel", response_model=list[EntradaLELFormalizada])
def lel(srv: Annotated[Servicio, Depends(obtener_servicio)], proyecto_id: str | None = None) -> list[EntradaLELFormalizada]:
    """Entradas formalizadas; con `proyecto_id`, solo las de ese proyecto."""
    return srv.repo.listar_lel(proyecto_id)
