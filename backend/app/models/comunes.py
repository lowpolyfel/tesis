"""Vocabulario cerrado del sistema. Un concepto, un nombre."""
from enum import StrEnum


class Estado(StrEnum):
    """Máquina de estados de un requisito (docs/CONTEXTO_PROYECTO.md §11).

    `error` no es parte del flujo normal: marca un caso en que un agente no
    produjo una salida válida tras el reintento.
    """

    CARGADO = "cargado"
    EXTRAIDO = "extraido"
    INTERPRETADO = "interpretado"
    ACEPTADO_DIRECTO = "aceptado_directo"
    EN_DEBATE = "en_debate"
    CONSENSO = "consenso"
    ARBITRADO = "arbitrado"
    PENDIENTE_VALIDACION = "pendiente_validacion"
    VALIDADO = "validado"
    RECHAZADO = "rechazado"
    FORMALIZADO = "formalizado"
    ERROR = "error"


ESTADOS_TERMINALES = {Estado.RECHAZADO, Estado.FORMALIZADO, Estado.ERROR}


class TipoMensaje(StrEnum):
    """Tipo de cada mensaje del protocolo. Cerrado = controlado (ver ADR 0001)."""

    EXTRACCION = "extraccion"
    FILTRADO = "filtrado"
    INTERPRETACIONES = "interpretaciones"
    SIMILITUD = "similitud"
    OBJECION = "objecion"
    REFINAMIENTO = "refinamiento"
    CONSENSO = "consenso"
    ARBITRAJE = "arbitraje"
    SOLICITUD_VALIDACION = "solicitud_validacion"
    VALIDACION = "validacion"
    FORMALIZACION = "formalizacion"
    ERROR = "error"


class Nodo(StrEnum):
    """Emisores y receptores de mensajes."""

    EXTRACTOR = "extractor"
    FILTROS = "filtros"
    CLASIFICADOR = "clasificador"
    DIVERGENCIA = "divergencia"
    CRITICO = "critico"
    MODELADOR = "modelador"
    HUMANO = "humano"
    SISTEMA = "sistema"


class Categoria(StrEnum):
    """Tipos de símbolo del LEL (Leite)."""

    SUJETO = "sujeto"
    OBJETO = "objeto"
    VERBO = "verbo"
    ESTADO = "estado"


class DecisionFiltro(StrEnum):
    """Qué hicieron los filtros deterministas con cada término (ADR 0003, 0010).

    `regional`, `alcance` y `anafora` siempre pasan al Clasificador, igual que
    `candidato`; se distinguen para saber de dónde salió el candidato.
    """

    RESUELTO_POR_LEL = "resuelto_por_lel"
    VAGUEDAD = "vaguedad"
    REGIONAL = "regional"
    ALCANCE = "alcance"
    ANAFORA = "anafora"
    CANDIDATO = "candidato"


class TipoAmbiguedad(StrEnum):
    """Tipo de ambigüedad que el Clasificador asigna a un término con
    interpretaciones (CONTEXTO §6). La vaguedad no está aquí: no produce
    interpretaciones discretas y la marca el catálogo, sin debate."""

    LEXICA = "lexica"
    ALCANCE = "alcance"
    ANAFORICA = "anaforica"
    SINTACTICA = "sintactica"


# Solo la ambigüedad léxica produce una entrada del LEL: las demás se resuelven
# reescribiendo el requisito (ADR 0010).
TIPOS_QUE_VAN_AL_LEL = {TipoAmbiguedad.LEXICA}


class Regla(StrEnum):
    """Reglas verificables del Crítico, versión v1 provisional (ADR 0004)."""

    R1 = "R1"  # consistencia de vocabulario
    R2 = "R2"  # sin entidades nuevas
    R3 = "R3"  # reduce la ambigüedad


class Via(StrEnum):
    """Cómo quedó resuelto un término con interpretaciones."""

    ACEPTADO_DIRECTO = "aceptado_directo"
    CONSENSO = "consenso"
    ARBITRAJE = "arbitraje"
