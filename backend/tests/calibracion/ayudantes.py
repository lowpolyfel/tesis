"""Trazas y valores hechos a mano, con números conocidos, para las funciones puras."""
from __future__ import annotations

from app.models import Mensaje, Origen, Traza


def valor(req_id: str, termino: str, similitud: float, umbral: float = 0.75, **extra) -> dict:
    """Una fila como la de `extraer_similitudes`, decidida con `umbral` (regla >=)."""
    return {"req_id": req_id, "proyecto_id": "P01", "ciclo": 1, "termino": termino, "similitud": similitud,
            "umbral_usado": umbral, "decision_real": "aceptado_directo" if similitud >= umbral else "en_debate",
            "tipo_ambiguedad": "lexica", "via": None, "estado_requisito": "pendiente_validacion",
            "modelo_embeddings": "embeddings-falsos", **extra}


def clasificacion(*terminos: tuple[str, str | None]) -> tuple:
    """Mensaje `interpretaciones` con el tipo de ambigüedad de cada término (None: traza anterior al tipo)."""
    return "interpretaciones", 0, {"resultados": [{"termino": t, "tipo_ambiguedad": tipo, "interpretaciones": []}
                                                  for t, tipo in terminos]}


def similitud(termino: str | None, valor_: float | None, ronda: int = 0, umbral: float = 0.75,
              decision: str | None = None, modelo: str = "embeddings-falsos") -> tuple:
    if termino is None:  # requisito sin interpretaciones
        return "similitud", 0, {"similitud": None, "umbral": umbral, "motivo": "sin_interpretaciones",
                                "decision": "aceptado_directo"}
    decision = decision or ("aceptado_directo" if valor_ >= umbral else "en_debate")
    return "similitud", ronda, {"termino": termino, "similitud": valor_, "umbral": umbral, "decision": decision,
                                "par_minimo": ["I1", "I2"], "pares": {"I1-I2": valor_}, "modelo_embeddings": modelo}


def traza(req_id: str, *mensajes: tuple, estado: str = "pendiente_validacion", proyecto_id: str = "P01",
          ciclo: int = 1, reproceso_de: str | None = None) -> Traza:
    return Traza(
        req_id=req_id, proyecto_id=proyecto_id, ciclo=ciclo, texto=f"requisito {req_id}", estado=estado, config={},
        origen=Origen(reproceso_de=reproceso_de) if reproceso_de else None,
        mensajes=[Mensaje(req_id=req_id, secuencia=i, ronda=ronda, emisor="sistema", receptor="sistema", tipo=tipo,
                          payload=payload) for i, (tipo, ronda, payload) in enumerate(mensajes, 1)],
    )
