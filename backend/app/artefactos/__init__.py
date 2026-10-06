"""Artefactos de salida del proyecto (CONTEXTO §7, ADR 0011): modelo de metas
estratégicas y Big Picture. Se agregan en código, sin LLM, desde lo validado."""
from . import formas  # noqa: F401
from .big_picture import big_picture_proyecto  # noqa: F401
from .exportar import a_mermaid, a_plantuml, texto_mermaid  # noqa: F401
from .metas import artefactos_requisito, metas_proyecto  # noqa: F401
from .seleccion import seleccionar  # noqa: F401
