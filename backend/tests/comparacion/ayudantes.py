"""Proyecto de prueba para la comparación: trazas armadas a mano en el repositorio
(sin correr el grafo), juez LLM falso por par y embeddings con vectores elegidos."""
from __future__ import annotations

import re
from typing import Callable

from app.models import EntradaLELFormalizada, Estado, Interpretacion, Nodo, Origen, TipoMensaje
from tests.escenarios import montar
from tests.fakes import EmbeddingsFalsos, interp

INDEPENDIENTE = {"relacion": "independiente", "explicacion": "A y B tratan temas distintos.",
                 "cita_a": "El sistema", "cita_b": "El sistema"}


def juicio(relacion: str, cita_a: str, cita_b: str, explicacion: str = "Explicación breve del juicio.") -> dict:
    return {"relacion": relacion, "explicacion": explicacion, "cita_a": cita_a, "cita_b": cita_b}


def par_del_prompt(prompt) -> tuple[str, str]:
    a = re.search(r"Requisito A \((R\d+)\)", prompt.usuario).group(1)
    b = re.search(r"Requisito B \((R\d+)\)", prompt.usuario).group(1)
    return a, b


def juez_por_par(juicios: dict[tuple[str, str], dict | str | Callable], defecto: dict = INDEPENDIENTE):
    """Guion de `comparador_v1`: responde según el par (A, B) que aparece en el prompt."""

    def responder(prompt):
        j = juicios.get(par_del_prompt(prompt), defecto)
        return j(prompt) if callable(j) else j

    return responder


def montar_comparacion(tmp_path, analizador, *, juicios=None, vectores=None, **ajustes):
    srv, llm, repo = montar(tmp_path, analizador, {"comparador_v1": juez_por_par(juicios or {})}, **ajustes)
    srv.deps.embeddings = EmbeddingsFalsos(vectores or {})
    proyecto = srv.proyectos.crear("Comparación de prueba")
    return srv, llm, repo, proyecto.proyecto_id


def requisito(repo, proyecto_id: str, texto: str, estado: Estado = Estado.CARGADO, *, reescrito: str | None = None,
              resoluciones: list[dict] | None = None, origen: Origen | None = None) -> str:
    t = repo.crear_traza(texto, {}, proyecto_id=proyecto_id, origen=origen)
    if estado != Estado.CARGADO:
        repo.cambiar_estado(t.req_id, estado)
    if reescrito is not None or resoluciones is not None:
        repo.guardar_doc("formalizados", t.req_id, {
            "req_id": t.req_id, "proyecto_id": proyecto_id, "requisito_original": texto,
            "requisito_reescrito": reescrito or texto, "resoluciones": resoluciones or [], "metas": [],
            "entradas_lel": [], "univocos": [], "vaguedad": [], "fecha": "2026-10-06",
            "modelo": "llm-falso", "prompt_version": "modelador_requisito_v1"})
    return t.req_id


def resolucion(termino: str, significado: str, tipo: str = "lexica") -> dict:
    return {"termino": termino, "tipo_ambiguedad": tipo, "interpretacion": interp("I1", significado, f"... {significado} ..."),
            "via": "aceptado_directo", "cambio": "ninguno"}


def entrada_lel(proyecto_id: str, req_id: str, simbolo: str, nocion: list[str], termino: str | None = None):
    return EntradaLELFormalizada(
        simbolo=simbolo, tipo="objeto", nocion=nocion, impacto=["Se registra."], proyecto_id=proyecto_id,
        req_id=req_id, termino=termino or simbolo, via="aceptado_directo",
        interpretacion=Interpretacion.model_validate(interp("I1", nocion[0][:40], "paráfrasis")), fecha="2026-10-06")


def validar_a_mano(repo, req_id: str, termino: str, significado: str, tipo: str | None = "lexica",
                   decision: str = "aprobar") -> None:
    """Mensajes de solicitud y validación como los emite el grafo (sin documento formalizado)."""
    repo.agregar_mensaje(req_id, ronda=0, emisor=Nodo.SISTEMA, receptor=Nodo.HUMANO,
                         tipo=TipoMensaje.SOLICITUD_VALIDACION,
                         payload={"terminos": [{"termino": termino, "tipo_ambiguedad": tipo}]})
    repo.agregar_mensaje(req_id, ronda=0, emisor=Nodo.HUMANO, receptor=Nodo.MODELADOR, tipo=TipoMensaje.VALIDACION,
                         payload={"decision": decision, "comentario": None, "terminos": [
                             {"termino": termino, "propuesta": "I1", "final": interp("I1", significado, "paráfrasis"),
                              "cambio": "ninguno"}]})
