"""Corpus con ground truth y evaluación empírica contra un solo agente (CONTEXTO §9 y §11, ADR 0014).

Fuera del núcleo: no toca el grafo. Corre el corpus por el sistema y por una
línea base de un solo agente, y compara ambos contra el ground truth, que vive en
un archivo separado y nunca entra a un prompt.
"""
from .agente_unico import PROMPT, AgenteUnico, EntradaLineaBase, SalidaAgenteUnico, linea_base  # noqa: F401
from .corpus import (  # noqa: F401
    ARCHIVO_GROUND_TRUTH,
    ARCHIVO_REQUISITOS,
    Corpus,
    CorpusInvalido,
    CorpusNoEncontrado,
    RequisitoGT,
    cargar_corpus,
    nombres_de_corpus,
)
from .ejecucion import (  # noqa: F401
    SinAgenteUnico,
    correr_linea_base,
    crear,
    detalle_corpus,
    encolar,
    informe,
    listar,
    listar_corpus,
    obtener,
    raiz_corpus,
    reanudar_si_falta,
    recuperar,
    sincronizar,
    solicitar,
)
from .emparejamiento import criterio, emparejar  # noqa: F401
from .metricas import NOTA  # noqa: F401
from .modelos import COLECCION, Etiqueta, Evaluacion  # noqa: F401
