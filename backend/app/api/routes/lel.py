"""Entradas formalizadas del LEL."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.models import EntradaLELFormalizada
from app.orchestration import Servicio

from ..dependencias import UsuarioDep, exigir_suyo, obtener_servicio, proyectos_de

router = APIRouter(tags=["lel"])


@router.get("/lel", response_model=list[EntradaLELFormalizada])
def lel(srv: Annotated[Servicio, Depends(obtener_servicio)], usuario: UsuarioDep,
        proyecto_id: str | None = None) -> list[EntradaLELFormalizada]:
    """Entradas formalizadas de los proyectos de la cuenta; con `proyecto_id`, solo las de ese."""
    if proyecto_id is not None:
        exigir_suyo(srv, usuario, proyecto_id, f"el proyecto {proyecto_id}")
        return srv.repo.listar_lel(proyecto_id)
    suyos = proyectos_de(srv, usuario)
    return [e for e in srv.repo.listar_lel() if e.proyecto_id in suyos]
