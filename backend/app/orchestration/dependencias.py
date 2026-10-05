"""Construcción de las piezas que usa el grafo, a partir de la configuración.

Las pruebas arman `Dependencias` con LLMs y embeddings falsos; la aplicación
usa `crear_dependencias()` con Ollama, spaCy y el repositorio real.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.clasificador import Clasificador
from app.agents.critico import Critico, ReglasCritico
from app.agents.extractor import Extractor
from app.agents.modelador import Modelador
from app.config import Settings, get_settings
from app.db.repositorio import Repositorio, crear_repositorio
from app.divergence import EmbeddingsOllama, ProveedorEmbeddings
from app.llm import ClienteLLM, crear_cliente
from app.nlp import Analizador, Catalogos, Filtros


@dataclass
class Dependencias:
    settings: Settings
    repo: Repositorio
    extractor: Extractor
    filtros: Filtros
    clasificador: Clasificador
    critico: Critico
    modelador: Modelador
    embeddings: ProveedorEmbeddings
    extra_config: dict = field(default_factory=dict)  # se copia en la traza

    def config_traza(self) -> dict:
        return {
            **self.settings.resumen(),
            "catalogos": self.filtros.catalogos.versiones(),
            "persistencia": self.repo.descripcion,
            **self.extra_config,
        }


def armar(settings: Settings, repo: Repositorio, analizador: Analizador, *, extractor: ClienteLLM,
          clasificador: ClienteLLM, critico: ClienteLLM, modelador: ClienteLLM,
          embeddings: ProveedorEmbeddings) -> Dependencias:
    """Une clientes, spaCy y catálogos en las piezas del grafo."""
    catalogos = Catalogos.cargar(settings.ruta(settings.catalogos_dir), analizador)
    return Dependencias(
        settings=settings,
        repo=repo,
        extractor=Extractor(extractor),
        filtros=Filtros(catalogos, analizador),
        clasificador=Clasificador(clasificador, settings.significado_max_palabras),
        critico=Critico(critico, ReglasCritico(analizador)),
        modelador=Modelador(modelador),
        embeddings=embeddings,
    )


def crear_dependencias(settings: Settings | None = None) -> Dependencias:
    s = settings or get_settings()
    return armar(
        s,
        crear_repositorio(s),
        Analizador(s.spacy_model),
        extractor=crear_cliente("ollama", s.extractor_model, s),
        clasificador=crear_cliente("ollama", s.clasificador_model, s),
        critico=crear_cliente(s.critico_provider, s.critico_model, s),
        modelador=crear_cliente("ollama", s.modelador_model, s),
        embeddings=EmbeddingsOllama(s.embedding_model, s.ollama_base_url),
    )
