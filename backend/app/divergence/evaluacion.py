"""Une embeddings y similitud para un conjunto de interpretaciones de un término."""
from __future__ import annotations

from dataclasses import dataclass

from app.models import Estado, Interpretacion

from .embeddings import ProveedorEmbeddings
from .similitud import decidir, similitud_minima_entre_pares


@dataclass(frozen=True)
class ResultadoDivergencia:
    termino: str
    similitud: float
    umbral: float
    decision: Estado
    par_minimo: tuple[str, str]
    pares: dict[str, float]
    modelo_embeddings: str

    def payload(self) -> dict:
        return {
            "termino": self.termino,
            "similitud": self.similitud,
            "umbral": self.umbral,
            "decision": self.decision.value,
            "par_minimo": list(self.par_minimo),
            "pares": self.pares,
            "modelo_embeddings": self.modelo_embeddings,
        }


def evaluar_divergencia(
    termino: str,
    interpretaciones: list[Interpretacion],
    embeddings: ProveedorEmbeddings,
    umbral: float,
) -> ResultadoDivergencia:
    """Compara las `parafrasis_del_requisito` de las interpretaciones de un término."""
    vectores = embeddings.vectorizar([i.parafrasis_del_requisito for i in interpretaciones])
    minima = similitud_minima_entre_pares(vectores)
    ids = [i.id for i in interpretaciones]
    return ResultadoDivergencia(
        termino=termino,
        similitud=minima.valor,
        umbral=umbral,
        decision=decidir(minima.valor, umbral),
        par_minimo=(ids[minima.par[0]], ids[minima.par[1]]),
        pares={f"{ids[i]}-{ids[j]}": v for (i, j), v in minima.pares.items()},
        modelo_embeddings=embeddings.modelo,
    )
