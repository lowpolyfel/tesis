"""Filtros deterministas antes del Clasificador (ADR 0003).

Precedencia por término:
  1. resuelto_por_lel  — ya está en el LEL con noción validada: no se vuelve a debatir
  2. vaguedad          — está en el catálogo de vaguedad: se marca y no entra a debate
  3. regional          — está en el catálogo regional: siempre pasa como candidato
  4. candidato         — el resto del vocabulario extraído pasa al Clasificador

Los catálogos se buscan en el texto completo, no solo entre los términos que
devolvió el Extractor: si el LLM omite *jalar* o *ahorita*, el catálogo los
recupera igual.

Además, los detectores estructurales (ADR 0010) agregan candidatos de
ambigüedad de alcance (`alcance`) y anafórica (`anafora`), que no son
vocabulario y por eso el Extractor no devuelve. Siempre pasan al Clasificador.
"""
from __future__ import annotations

from app.models import Categoria, DecisionFiltro, EntradaLEL, Posicion, TerminoExtraido, TerminoFiltrado

from .catalogos import Catalogos, Coincidencia
from .detectores import Detectores
from .spacy_es import Analizador, normalizar

_CATEGORIA_POR_POS = {"VERB": Categoria.VERBO, "AUX": Categoria.VERBO, "NOUN": Categoria.OBJETO,
                      "PROPN": Categoria.SUJETO, "ADJ": Categoria.ESTADO, "ADV": Categoria.ESTADO}


def _solapa(a_ini: int, a_fin: int, b_ini: int, b_fin: int) -> bool:
    return a_ini < b_fin and b_ini < a_fin


class Filtros:
    def __init__(self, catalogos: Catalogos, analizador: Analizador):
        self.catalogos = catalogos
        self.analizador = analizador
        self.detectores = Detectores(analizador)

    def _claves_lel(self, lel: list[EntradaLEL]) -> dict[str, str]:
        """Símbolos del LEL por forma normalizada y por secuencia de lemas."""
        claves: dict[str, str] = {}
        for e in lel:
            claves[normalizar(e.simbolo)] = e.simbolo
            claves[self._lemas(e.simbolo)] = e.simbolo
        return claves

    def _lemas(self, texto: str) -> str:
        return " ".join(normalizar(t.lemma_) for t in self.analizador.doc(texto) if not t.is_punct)

    def _en_lel(self, termino: str, claves: dict[str, str]) -> str | None:
        return claves.get(normalizar(termino)) or claves.get(self._lemas(termino))

    def aplicar(self, texto: str, extraidos: list[TerminoExtraido], lel: list[EntradaLEL]) -> list[TerminoFiltrado]:
        doc = self.analizador.doc(texto)
        vaguedad = self.catalogos.vaguedad.buscar(doc)
        regionales = self.catalogos.regionales.buscar(doc)
        claves_lel = self._claves_lel(lel)

        def coincide(t_ini: int, t_fin: int, lista: list[Coincidencia]) -> Coincidencia | None:
            return next((c for c in lista if _solapa(t_ini, t_fin, c.inicio, c.fin)), None)

        salida: list[TerminoFiltrado] = []
        cubiertas: set[tuple[int, int]] = set()

        for t in extraidos:
            ini, fin = t.posicion.inicio, t.posicion.fin
            simbolo = self._en_lel(t.termino, claves_lel)
            vag = coincide(ini, fin, vaguedad)
            reg = coincide(ini, fin, regionales)
            if simbolo:
                salida.append(self._filtrado(t.termino, ini, fin, t.categoria_tentativa, DecisionFiltro.RESUELTO_POR_LEL, f"símbolo del LEL: {simbolo}"))
            elif vag:
                cubiertas.add((vag.inicio, vag.fin))
                salida.append(self._de_catalogo(vag, t.categoria_tentativa, DecisionFiltro.VAGUEDAD, "vaguedad"))
            elif reg:
                cubiertas.add((reg.inicio, reg.fin))
                salida.append(self._de_catalogo(reg, t.categoria_tentativa, DecisionFiltro.REGIONAL, "regionales"))
            else:
                salida.append(self._filtrado(t.termino, ini, fin, t.categoria_tentativa, DecisionFiltro.CANDIDATO, None))

        # Lo que el catálogo encontró y el Extractor no devolvió
        for lista, decision, nombre in ((vaguedad, DecisionFiltro.VAGUEDAD, "vaguedad"), (regionales, DecisionFiltro.REGIONAL, "regionales")):
            for c in lista:
                if (c.inicio, c.fin) in cubiertas or any(_solapa(c.inicio, c.fin, s.posicion.inicio, s.posicion.fin) for s in salida):
                    continue
                categoria = self._categoria_por_pos(doc, c)
                simbolo = self._en_lel(c.expresion, claves_lel)
                if simbolo:
                    salida.append(self._filtrado(c.texto, c.inicio, c.fin, categoria, DecisionFiltro.RESUELTO_POR_LEL, f"símbolo del LEL: {simbolo}"))
                else:
                    salida.append(self._de_catalogo(c, categoria, decision, nombre, extra=" (detectado por catálogo, no por el Extractor)"))

        # Estructuras de alcance y anáfora: no compiten con el vocabulario, se agregan aparte
        tramos = {(s.posicion.inicio, s.posicion.fin) for s in salida}
        for d in self.detectores.buscar(texto):
            if (d.inicio, d.fin) not in tramos:
                decision = DecisionFiltro.ALCANCE if d.tipo == "alcance" else DecisionFiltro.ANAFORA
                salida.append(self._filtrado(d.texto, d.inicio, d.fin, d.categoria, decision, f"{d.patron}: {d.detalle}"))

        return sorted(salida, key=lambda s: (s.posicion.inicio, s.posicion.fin))

    @staticmethod
    def _filtrado(termino, ini, fin, categoria, decision, detalle) -> TerminoFiltrado:
        return TerminoFiltrado(termino=termino, posicion=Posicion(inicio=ini, fin=fin), categoria_tentativa=categoria,
                               decision_filtro=decision, detalle=detalle)

    def _de_catalogo(self, c: Coincidencia, categoria, decision, nombre, extra="") -> TerminoFiltrado:
        return self._filtrado(c.texto, c.inicio, c.fin, categoria, decision, f"catálogo de {nombre}: «{c.expresion}»{extra}")

    @staticmethod
    def _categoria_por_pos(doc, c: Coincidencia) -> Categoria:
        span = doc.char_span(c.inicio, c.fin)
        pos = span.root.pos_ if span is not None else "NOUN"
        return _CATEGORIA_POR_POS.get(pos, Categoria.OBJETO)
