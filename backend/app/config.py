"""Configuración calibrable del sistema, leída de variables de entorno (.env).

Ningún parámetro calibrable está escrito en el código: todo sale de aquí, y una
copia de los valores usados se guarda en la traza de cada requisito para poder
reconstruir el experimento.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import Field, PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_REPO = Path(__file__).resolve().parents[2]
RAIZ_BACKEND = RAIZ_REPO / "backend"
# pydantic-settings lee los dos y, si una variable está en ambos, gana el último (backend/.env)
ARCHIVOS_ENV = (RAIZ_REPO / ".env", RAIZ_BACKEND / ".env")


def fuente_de(variable: str) -> str:
    """De dónde toma pydantic-settings `variable` (sin distinguir mayúsculas), en su orden
    de prioridad: `variable_de_sistema` (gana a los .env), `env_backend`, `env_raiz` o `default`."""
    nombre = variable.lower()
    if any(k.lower() == nombre for k in os.environ):
        return "variable_de_sistema"
    for ruta, fuente in ((ARCHIVOS_ENV[1], "env_backend"), (ARCHIVOS_ENV[0], "env_raiz")):
        if ruta.is_file() and any(k.lower() == nombre and v is not None
                                  for k, v in dotenv_values(ruta, encoding="utf-8").items()):
            return fuente
    return "default"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ARCHIVOS_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Divergencia y debate
    similarity_threshold: float = Field(0.75, ge=0.0, le=1.0)
    max_debate_rounds: int = Field(2, ge=1)

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    # Tiempo máximo de una llamada a Ollama (generación o embeddings). Generoso: un modelo
    # cargándose en frío tarda; sin límite, un Ollama colgado detiene la cola para siempre.
    ollama_timeout_s: float = Field(300, gt=0)
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

    # Cuándo espera el grafo a una persona (ADR 0017): si_hay_arbitraje | siempre | nunca
    validacion_humana: Literal["si_hay_arbitraje", "siempre", "nunca"] = "si_hay_arbitraje"

    # NLP
    spacy_model: str = "es_core_news_sm"

    # Persistencia
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "tesis"
    mongo_timeout_ms: int = 1500
    # De dónde salió MONGO_URI, fijado al crear la configuración (al arrancar): si después
    # se edita un .env sin reiniciar, /conexion sigue diciendo de dónde salió la URI en uso
    _fuente_mongo_uri: str = PrivateAttr(default="default")
    checkpoint_path: str = "data/checkpoints.sqlite"
    resultados_dir: str = "data/resultados"
    catalogos_dir: str = "data/catalogos"

    # Cuentas: el código de seguridad va por correo (SMTP). Sin SMTP_HOST (desarrollo) no se
    # envía: el backend escribe el código en su registro.
    smtp_host: str | None = None
    smtp_puerto: int = Field(587, ge=1, le=65535)
    smtp_usuario: str | None = None
    smtp_contrasena: str | None = None
    smtp_remitente: str | None = None  # por omisión, SMTP_USUARIO
    smtp_seguridad: Literal["starttls", "ssl", "ninguna"] = "starttls"
    codigo_minutos: int = Field(15, ge=1)  # vigencia del código
    codigo_intentos: int = Field(5, ge=1)  # intentos por código
    codigo_reenvio_s: int = Field(60, ge=0)  # espera mínima para pedir otro
    auth_codigo_al_entrar: bool = False  # true: también pide un código por correo al entrar
    sesion_dias: int = Field(7, ge=1)
    sesion_cookie_segura: bool = False  # true si el backend se sirve por HTTPS

    # API: cada cuánto la sandbox recibe mensajes nuevos por SSE (no afecta resultados)
    sse_intervalo_s: float = Field(0.3, gt=0)
    # Orígenes permitidos para el frontend, separados por coma, y además los que cumplan la
    # expresión (por omisión, cualquier puerto de localhost: `npm run dev` en 5173 o 5174,
    # `npm run preview` en 4173). Vacía, solo cuentan los de la lista.
    cors_origenes: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_origenes_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

    # Documentos (PDF con texto extraíble o texto plano)
    documento_max_mb: float = Field(10, gt=0)

    # Comparación entre requisitos (módulo exploratorio, ADR 0012)
    comparador_model: str = "qwen2.5:7b"
    comparacion_relacion_umbral: float = Field(0.60, ge=0.0, le=1.0)  # similitud mínima para comparar un par con el LLM
    comparacion_duplicado_umbral: float = Field(0.92, ge=0.0, le=1.0)  # similitud desde la que un par se marca casi duplicado
    comparacion_max_pares: int = Field(60, ge=1)

    # Evaluación contra el corpus (ADR 0014): línea base de un solo agente
    agente_unico_model: str = "qwen2.5:7b"
    corpus_dir: str = "data/corpus"

    # Calibración (ADR 0013): rejilla de umbrales para el análisis de sensibilidad
    calibracion_desde: float = Field(0.50, ge=0.0, le=1.0)
    calibracion_hasta: float = Field(0.95, ge=0.0, le=1.0)
    calibracion_paso: float = Field(0.05, gt=0.0, le=0.5)

    def model_post_init(self, contexto) -> None:
        self._fuente_mongo_uri = fuente_de("MONGO_URI")

    @property
    def fuente_mongo_uri(self) -> str:
        return self._fuente_mongo_uri

    @model_validator(mode="after")
    def _rejilla_valida(self) -> "Settings":
        if self.calibracion_desde >= self.calibracion_hasta:
            raise ValueError(f"CALIBRACION_DESDE ({self.calibracion_desde}) debe ser menor que "
                             f"CALIBRACION_HASTA ({self.calibracion_hasta})")
        return self

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
            "validacion_humana": self.validacion_humana,
        }

    def origenes_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
