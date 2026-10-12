"""El contexto del proyecto como ficha y el triaje de requisitos contra ella (ADR 0022)."""
from .ficha import COLECCION as COLECCION_FICHAS
from .ficha import a_markdown, ficha_al_dia, generar_ficha, huella_contexto
from .triaje import triar

__all__ = ["COLECCION_FICHAS", "a_markdown", "ficha_al_dia", "generar_ficha", "huella_contexto", "triar"]
