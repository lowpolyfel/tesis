"""Configuración calibrable del sistema, leída de variables de entorno (.env).

Ningún parámetro calibrable está escrito en el código: todo sale de aquí, y una
copia de los valores usados se guarda en la traza de cada requisito para poder
reconstruir el experimento.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_REPO = Path(__file__).resolve().parents[2]
RAIZ_BACKEND = RAIZ_REPO / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(RAIZ_REPO / ".env", RAIZ_BACKEND / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Divergencia y debate
    similarity_threshold: float = Field(0.75, ge=0.0, le=1.0)
    max_debate_rounds: int = Field(2, ge=1)

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    extractor_model: str = "qwen2.5:7b"
    clasificador_model: str = "qwen2.5:7b"
    modelador_model: str = "qwen2.5:7b"
    embedding_model: str = "nomic-embed-text"

    # Crítico
    critico_provider: Literal["ollama", "anthropic", "openai"] = "ollama"
    critico_model: str = "qwen2.5:7b"
    critico_api_key: str | None = None

    # Reproducibilidad
    llm_temperature: float = 0.0
    llm_seed: int | None = 42

    # Reglas del Crítico (v1, provisionales)
    significado_max_palabras: int = Field(12, ge=1)

    # NLP
    spacy_model: str = "es_core_news_sm"

    # Persistencia
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "tesis"
    mongo_timeout_ms: int = 1500
    checkpoint_path: str = "data/checkpoints.sqlite"
    resultados_dir: str = "data/resultados"
    catalogos_dir: str = "data/catalogos"

    def ruta(self, relativa: str) -> Path:
        """Rutas relativas se resuelven contra la raíz del repositorio."""
        p = Path(relativa)
        return p if p.is_absolute() else RAIZ_REPO / p

    def resumen(self) -> dict:
        """Lo que se copia en cada traza: suficiente para repetir la corrida."""
        return {
            "similarity_threshold": self.similarity_threshold,
            "max_debate_rounds": self.max_debate_rounds,
            "modelos": {
                "extractor": self.extractor_model,
                "clasificador": self.clasificador_model,
                "critico": f"{self.critico_provider}:{self.critico_model}",
                "modelador": self.modelador_model,
                "embeddings": self.embedding_model,
            },
            "llm_temperature": self.llm_temperature,
            "llm_seed": self.llm_seed,
            "significado_max_palabras": self.significado_max_palabras,
            "spacy_model": self.spacy_model,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
