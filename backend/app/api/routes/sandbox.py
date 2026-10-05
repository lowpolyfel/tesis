"""Página sandbox (desechable) y estado del servidor."""
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse

from app.orchestration import Servicio

from ..dependencias import obtener_servicio

router = APIRouter(tags=["sandbox"])
SANDBOX = Path(__file__).resolve().parents[1] / "static" / "sandbox.html"


@router.get("/", include_in_schema=False)
def raiz() -> RedirectResponse:
    return RedirectResponse("/sandbox")


@router.get("/sandbox", include_in_schema=False)
def sandbox() -> FileResponse:
    return FileResponse(SANDBOX, media_type="text/html")


@router.get("/salud")
def salud(srv: Annotated[Servicio, Depends(obtener_servicio)]) -> dict:
    """Qué persistencia y qué configuración está usando el servidor."""
    s = srv.deps.settings
    return {"estado": "ok", "persistencia": srv.repo.descripcion, "checkpoints": str(s.ruta(s.checkpoint_path)),
            "config": srv.deps.config_traza()}
