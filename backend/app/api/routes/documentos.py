"""Carga de documentos (PDF con texto extraíble o .txt) y separación en requisitos
candidatos (ADR 0009). Nada de esto procesa requisitos: el humano revisa lo
propuesto y lo confirma con POST /proyectos/{id}/requisitos."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.contexto import COLECCION_FICHAS, ficha_al_dia
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
from app.documentos.separacion_ia import separar_con_ia
from app.llm.perfiles import con_perfil
from app.orchestration import Servicio

from ..dependencias import UsuarioDep, es_suyo, exigir_suyo
from .proyectos import ProyectoDep, ServicioDep

router = APIRouter(tags=["documentos"])

_CODIGOS = {DemasiadoGrande: 413, TipoNoSoportado: 415}  # el resto (sin texto, ilegible): 422


class EntradaSeparar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=1)
    # con el proyecto, el Revisor lee su contexto y usa los modelos de su dueño (ADR 0023)
    proyecto_id: str | None = Field(None, max_length=40)
    con_ia: bool = True  # false: solo patrones («debe», «podrá»…)


def _documentos(srv: Servicio) -> Documentos:
    return Documentos(srv.repo, srv.deps.settings)


def _ia(srv: Servicio, perfil: dict, proyecto=None):
    """La separación con el Revisor (ADR 0023), con el contexto del proyecto: su ficha si está
    al día, si no el texto del contexto. None si está apagada."""
    if not srv.deps.settings.separacion_ia:
        return None
    contexto = None
    if proyecto is not None:
        doc = srv.repo.obtener_doc(COLECCION_FICHAS, proyecto.proyecto_id)
        contexto = doc["markdown"] if ficha_al_dia(doc, proyecto.nombre, proyecto.contexto) else proyecto.contexto

    def ia(parrafos):
        with con_perfil(perfil):
            return separar_con_ia(parrafos, srv.deps.revisor, contexto)
    return ia


@router.post("/proyectos/{proyecto_id}/documentos", status_code=201, response_model=Documento)
def cargar(p: ProyectoDep, srv: ServicioDep, archivo: Annotated[UploadFile, File()], con_ia: bool = True) -> Documento:
    """Extrae el texto por página, propone requisitos y guarda el documento. No
    encola nada: el humano confirma lo propuesto con POST /proyectos/{id}/requisitos.
    Los requisitos los reconoce el Revisor (`?con_ia=false`: solo patrones; ADR 0023)."""
    documentos = _documentos(srv)
    contenido = archivo.file.read(documentos.max_bytes + 1)  # basta un byte de más para saber que excede
    try:
        return documentos.cargar(p.proyecto_id, archivo.filename, contenido, archivo.content_type,
                                 ia=_ia(srv, srv.perfil(p.proyecto_id), p) if con_ia else None)
    except ErrorDocumento as e:
        raise HTTPException(_CODIGOS.get(type(e), 422), str(e))


@router.get("/proyectos/{proyecto_id}/documentos", response_model=list[ResumenDocumento])
def listar(p: ProyectoDep, srv: ServicioDep) -> list[ResumenDocumento]:
    return _documentos(srv).listar(p.proyecto_id)


@router.get("/documentos/{documento_id}", response_model=Documento)
def obtener(documento_id: str, srv: ServicioDep, usuario: UsuarioDep) -> Documento:
    documento = _documentos(srv).obtener(documento_id)
    if documento is None or not es_suyo(srv, usuario, documento.proyecto_id):
        raise HTTPException(404, f"No existe el documento {documento_id}")
    return documento


@router.post("/requisitos/separar", response_model=Separacion)
def separar(entrada: EntradaSeparar, srv: ServicioDep, usuario: UsuarioDep) -> Separacion:
    """Separa texto pegado sin guardar nada. Un salto de página (\\f) separa páginas. Los
    requisitos los reconoce el Revisor en cualquier redacción; si falla, patrones (ADR 0023)."""
    if len(entrada.texto.encode("utf-8")) > _documentos(srv).max_bytes:
        raise HTTPException(413, "El texto excede el máximo de DOCUMENTO_MAX_MB.")
    proyecto = None
    if entrada.proyecto_id:
        exigir_suyo(srv, usuario, entrada.proyecto_id, f"el proyecto {entrada.proyecto_id}")
        proyecto = srv.proyectos.obtener(entrada.proyecto_id)
    perfil = srv.perfil(entrada.proyecto_id) if proyecto else srv.perfiles.resuelto(usuario.usuario_id)
    return separar_texto(entrada.texto, ia=_ia(srv, perfil, proyecto) if entrada.con_ia else None)
