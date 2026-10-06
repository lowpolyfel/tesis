"""Símbolos del LEL del proyecto agrupados por forma normalizada (ADR 0011).

Un mismo símbolo puede tener varias entradas (dos requisitos lo resolvieron
antes de que el primero entrara a la memoria, ADR 0015): se agrupan en un solo
símbolo que conserva todas sus nociones e impactos y los requisitos de origen.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import EntradaLELFormalizada
from app.nlp import normalizar

from .terminos import numero_req


def clave(texto: str) -> str:
    """Parte legible del id de un nodo: «dar de alta» → «dar_de_alta»."""
    return "_".join(normalizar(texto).split())


@dataclass
class Simbolo:
    id: str
    simbolo: str  # como se escribió en la primera entrada
    subtipo: str
    entradas: list[EntradaLELFormalizada] = field(default_factory=list)

    @property
    def req_ids(self) -> list[str]:
        return sorted({e.req_id for e in self.entradas}, key=lambda r: (numero_req(r), r))

    @property
    def formas(self) -> list[str]:
        """El símbolo y los términos de los que salió: lo que se busca en los textos."""
        vistas, salida = set(), []
        for t in [self.simbolo, *(e.simbolo for e in self.entradas), *(e.termino for e in self.entradas)]:
            if normalizar(t) not in vistas:
                vistas.add(normalizar(t))
                salida.append(t)
        return salida

    @property
    def textos(self) -> list[str]:
        """Nociones e impactos de todas sus entradas (sin repetir)."""
        return list(dict.fromkeys(x for e in self.entradas for x in [*e.nocion, *e.impacto]))

    @property
    def nocion(self) -> str | None:
        return self.entradas[0].nocion[0] if self.entradas and self.entradas[0].nocion else None


def agrupar_lel(lel: list[EntradaLELFormalizada]) -> list[Simbolo]:
    """Un `Simbolo` por forma normalizada, ordenados por esa forma. La entrada
    del requisito más antiguo decide cómo se escribe y su tipo."""
    grupos: dict[str, Simbolo] = {}
    for e in sorted(lel, key=lambda e: numero_req(e.req_id)):
        k = clave(e.simbolo)
        if k not in grupos:
            grupos[k] = Simbolo(id=f"simbolo:{k}", simbolo=e.simbolo, subtipo=str(e.tipo))
        grupos[k].entradas.append(e)
    return [grupos[k] for k in sorted(grupos)]
