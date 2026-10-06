"""Carga de documentos (PDF con texto extraíble o .txt) y separación en requisitos
candidatos (ADR 0009). Nada de esto procesa requisitos: el humano revisa lo
propuesto y lo confirma con POST /proyectos/{id}/requisitos."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.documentos import (
    DemasiadoGrande,
    Documento,
    Documentos,
    ErrorDocumento,
    ResumenDocumento,
    Separacion,
    TipoNoSoportado,
    separar_texto,
)
from app.orchestration import Servicio

from .proyectos import ProyectoDep, ServicioDep

router = APIRouter(tags=["documentos"])

_CODIGOS = {DemasiadoGrande: 413, TipoNoSoportado: 415}  # el resto (sin texto, ilegible): 422


class EntradaSeparar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=1)


def _documentos(srv: Servicio) -> Documentos:
    return Documentos(srv.repo, srv.deps.settings)


@router.post("/proyectos/{proyecto_id}/documentos", status_code=201, response_model=Documento)
def cargar(p: ProyectoDep, srv: ServicioDep, archivo: Annotated[UploadFile, File()]) -> Documento:
    """Extrae el texto por página, propone requisitos y guarda el documento. No
    encola nada: el humano confirma lo propuesto con POST /proyectos/{id}/requisitos."""
    documentos = _documentos(srv)
    contenido = archivo.file.read(documentos.max_bytes + 1)  # basta un byte de más para saber que excede
    try:
        return documentos.cargar(p.proyecto_id, archivo.filename, contenido, archivo.content_type)
    except ErrorDocumento as e:
        raise HTTPException(_CODIGOS.get(type(e), 422), str(e))


@router.get("/proyectos/{proyecto_id}/documentos", response_model=list[ResumenDocumento])
def listar(p: ProyectoDep, srv: ServicioDep) -> list[ResumenDocumento]:
    return _documentos(srv).listar(p.proyecto_id)


@router.get("/documentos/{documento_id}", response_model=Documento)
def obtener(documento_id: str, srv: ServicioDep) -> Documento:
    documento = _documentos(srv).obtener(documento_id)
    if documento is None:
        raise HTTPException(404, f"No existe el documento {documento_id}")
    return documento


@router.post("/requisitos/separar", response_model=Separacion)
def separar(entrada: EntradaSeparar, srv: ServicioDep) -> Separacion:
    """Separa texto pegado sin guardar nada. Un salto de página (\\f) separa páginas."""
    if len(entrada.texto.encode("utf-8")) > _documentos(srv).max_bytes:
        raise HTTPException(413, "El texto excede el máximo de DOCUMENTO_MAX_MB.")
    return separar_texto(entrada.texto)
