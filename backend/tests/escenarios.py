"""Escenarios compartidos por las pruebas del grafo y de la API: requisito de
«sesión», paráfrasis con vectores conocidos y guiones de LLM falso."""
from langgraph.checkpoint.memory import InMemorySaver

from app.config import Settings
from app.db import RepositorioJson
from app.orchestration import Servicio, armar
from tests.fakes import EmbeddingsFalsos, LLMFalso, interp

SESION = "El sistema debe registrar la sesión del usuario."
P1 = "El sistema debe registrar el periodo de uso del usuario."
P2 = "El sistema debe registrar la conexión del usuario."
P1_CERCANA = "El sistema debe registrar el periodo de uso que tiene el usuario."

# vectores: P1 y P2 ortogonales (similitud 0); P1 y P1_CERCANA casi iguales
VECTORES = {P1: [1.0, 0.0], P2: [0.0, 1.0], P1_CERCANA: [0.99, 0.05]}

EXTRACCION_SESION = {"terminos": [{"termino": "sistema", "categoria_tentativa": "sujeto"},
                                  {"termino": "registrar", "categoria_tentativa": "verbo"},
                                  {"termino": "sesión", "categoria_tentativa": "objeto"}]}


def clasificacion(*interpretaciones):
    return {"resultados": [{"termino": "sistema", "univoco": True},
                           {"termino": "registrar", "univoco": True},
                           {"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretaciones": list(interpretaciones)}]}


I1 = interp("I1", "periodo de uso", P1)
I2 = interp("I2", "evento de conexión", P2)
MODELADO = {"entrada_lel": {"simbolo": "sesión", "tipo": "objeto", "nocion": ["Periodo de uso del sistema."],
                            "impacto": ["Se registra al iniciar y cerrar."]}}


def modelado_requisito(prompt):
    """Guion por omisión del Modelador por requisito: repite el requisito original y una meta."""
    texto = prompt.usuario.split("Requisito original:", 1)[1].split("«", 1)[1].split("»", 1)[0]
    return {"requisito_reescrito": texto, "tipo_requisito": "funcional", "categoria": None, "supuestos": [], "metas": [
        {"id": "M1", "enunciado": "Cumplir el requisito", "tipo": "meta", "actor": None, "simbolos": [],
         "contribuye_a": None}]}


def montar(tmp_path, analizador, guiones, checkpointer=None, **ajustes):
    # Las pruebas del flujo con validación humana fijan `siempre`; las de la validación
    # automática (ADR 0017) lo cambian con `validacion_humana=...`.
    ajustes = {"validacion_humana": "siempre", **ajustes}
    settings = Settings(_env_file=None, similarity_threshold=0.75, max_debate_rounds=2,
                        resultados_dir=str(tmp_path / "resultados"), checkpoint_path=str(tmp_path / "cp.sqlite"),
                        **ajustes)
    guiones = {"modelador_requisito_v2": modelado_requisito, **guiones}
    llm = LLMFalso(guiones)
    repo = RepositorioJson(settings.ruta(settings.resultados_dir))
    deps = armar(settings, repo, analizador, extractor=llm, clasificador=llm, critico=llm, modelador=llm,
                 embeddings=EmbeddingsFalsos(VECTORES), comparador=llm, agente_unico=llm)
    return Servicio(deps, checkpointer or InMemorySaver()), llm, repo


def guiones_sesion_cercana():
    return {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
        "modelador_v2": [MODELADO],
    }
