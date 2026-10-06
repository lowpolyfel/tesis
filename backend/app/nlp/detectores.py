"""Detectores deterministas de posible ambigüedad de alcance y anafórica (ADR 0010).

El Extractor separa vocabulario del dominio; los pronombres, posesivos,
cuantificadores y coordinaciones no son vocabulario y no los devuelve. Estos
detectores los buscan con rasgos morfológicos de spaCy para que lleguen al
Clasificador como candidatos. Buscan **cobertura**, no deciden: el Clasificador
puede marcarlos unívocos.

Anáfora
  - posesivo (su, sus) o demostrativo pronominal (este, esta, dicho…) con dos o
    más antecedentes posibles antes de él en la oración.

Alcance
  - cuantificador universal (todos, cada, ambos) + negación en la oración;
  - cuantificador universal + indefinido (cada vendedor … un cliente);
  - partícula de foco (solo, solamente, únicamente): ¿qué restringe?;
  - «y/o»: ¿inclusiva o exclusiva?;
  - coordinación mixta «… y … o …» sin paréntesis: ¿cómo se agrupa?

Limitaciones conocidas: no separa clíticos pegados al verbo («firmarlo»), no
resuelve elipsis y cuenta como antecedente cualquier sustantivo previo de la
oración (incluido «sistema»).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from spacy.tokens import Doc, Span, Token

from app.models import Categoria

from .spacy_es import Analizador

FOCO = {"solo", "sólo", "solamente", "únicamente", "unicamente"}
DEMOSTRATIVOS_ANAFORICOS = {"este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella",
                            "dicho", "dicha", "dichos", "dichas"}


@dataclass(frozen=True)
class Deteccion:
    tipo: Literal["alcance", "anafora"]
    patron: str
    texto: str
    inicio: int
    fin: int
    categoria: Categoria
    detalle: str
    antecedentes: tuple[str, ...] = field(default_factory=tuple)


def _categoria(tok: Token) -> Categoria:
    return Categoria.SUJETO if tok.dep_ in ("nsubj", "nsubj:pass") else Categoria.OBJETO


def _chunk_de(tok: Token, chunks: list[Span]) -> Span | None:
    return next((c for c in chunks if c.start <= tok.i < c.end), None)


def _rasgo(tok: Token, nombre: str) -> list[str]:
    return tok.morph.get(nombre)


class Detectores:
    def __init__(self, analizador: Analizador):
        self.analizador = analizador

    def buscar(self, texto: str) -> list[Deteccion]:
        doc = self.analizador.doc(texto)
        salida: list[Deteccion] = []
        for oracion in doc.sents:
            salida += self._anaforas(doc, oracion)
            salida += self._alcance(doc, oracion)
        vistos, unicas = set(), []
        for d in sorted(salida, key=lambda d: (d.inicio, d.fin)):
            if (d.inicio, d.fin) not in vistos:
                vistos.add((d.inicio, d.fin))
                unicas.append(d)
        return unicas

    # ------------------------------------------------------------ anáfora

    def _antecedentes(self, oracion: Span, anafora: Token, excluir: Span | None) -> list[Token]:
        posibles = []
        for t in oracion:
            if t.i >= anafora.i:
                break
            if t.pos_ in ("NOUN", "PROPN") and not (excluir and excluir.start <= t.i < excluir.end):
                if t.lemma_.lower() not in {p.lemma_.lower() for p in posibles}:
                    posibles.append(t)
        return posibles

    def _anaforas(self, doc: Doc, oracion: Span) -> list[Deteccion]:
        chunks = list(doc.noun_chunks)
        salida = []
        for t in oracion:
            posesivo = "Yes" in _rasgo(t, "Poss") and t.pos_ in ("DET", "PRON")
            demostrativo = t.pos_ == "PRON" and "Dem" in _rasgo(t, "PronType") and t.lower_ in DEMOSTRATIVOS_ANAFORICOS
            if not (posesivo or demostrativo):
                continue
            propio = _chunk_de(t, chunks)
            candidatos = self._antecedentes(oracion, t, propio)
            if demostrativo:  # el demostrativo concuerda en género y número con su antecedente
                genero, numero = _rasgo(t, "Gender"), _rasgo(t, "Number")
                candidatos = [c for c in candidatos
                              if (not genero or not _rasgo(c, "Gender") or _rasgo(c, "Gender") == genero)
                              and (not numero or not _rasgo(c, "Number") or _rasgo(c, "Number") == numero)]
            if len(candidatos) < 2:
                continue
            if posesivo and propio is not None:
                span = propio
            elif posesivo and t.head.pos_ in ("NOUN", "PROPN") and t.head.i > t.i:
                span = doc[t.i:t.head.i + 1]  # «su cuenta» aunque spaCy no lo marque como sintagma
            else:
                span = doc[t.i:t.i + 1]
            nombres = tuple(c.text for c in candidatos)
            salida.append(Deteccion(
                tipo="anafora", patron="posesivo" if posesivo else "demostrativo",
                texto=span.text, inicio=span.start_char, fin=span.end_char,
                categoria=_categoria(span.root),
                detalle=f"«{t.text}» puede referirse a: {', '.join(nombres)}",
                antecedentes=nombres))
        return salida

    # ------------------------------------------------------------ alcance

    def _alcance(self, doc: Doc, oracion: Span) -> list[Deteccion]:
        chunks = list(doc.noun_chunks)
        salida = []
        universales = [t for t in oracion if "Tot" in _rasgo(t, "PronType")]
        negaciones = [t for t in oracion if "Neg" in _rasgo(t, "Polarity")]
        indefinidos = [t for t in oracion if "Ind" in _rasgo(t, "Definite") or t.lower_ in ("algún", "alguna", "algunos", "algunas")]

        for u in universales:
            span = _chunk_de(u, chunks) or doc[u.i:u.i + 1]
            if negaciones:
                n = negaciones[0]
                salida.append(self._det_alcance(span, "universal+negacion", _categoria(span.root),
                                                f"«{u.text}» con la negación «{n.text}»: ¿ninguno o no todos?"))
            otros = [i for i in indefinidos if not (span.start <= i.i < span.end) and i.i > u.i]
            if otros:
                i = otros[0]
                obj = _chunk_de(i, chunks)
                salida.append(self._det_alcance(span, "universal+indefinido", _categoria(span.root),
                                                f"«{span.text}» con «{obj.text if obj else i.text}»: ¿uno para cada uno o uno compartido?"))

        for t in oracion:
            if t.lower_ in FOCO:
                siguiente = next((c for c in chunks if c.start > t.i and c.end - t.i <= 7), None)
                span = doc[t.i:siguiente.end] if siguiente else doc[t.i:min(t.i + 3, oracion.end)]
                salida.append(self._det_alcance(span, "foco", Categoria.ESTADO,
                                                f"«{t.text}»: ¿qué parte del requisito restringe?"))

        texto = oracion.text.lower()
        if "y/o" in texto:
            for t in oracion:
                if t.lower_ == "y" and t.i + 2 < len(doc) and doc[t.i + 1].text == "/" and doc[t.i + 2].lower_ == "o":
                    izq = _chunk_de(doc[t.i - 1], chunks) if t.i > 0 else None
                    der = _chunk_de(doc[t.i + 3], chunks) if t.i + 3 < len(doc) else None
                    ini = izq.start if izq else t.i
                    fin = der.end if der else t.i + 3
                    span = doc[ini:fin]
                    salida.append(self._det_alcance(span, "y/o", _categoria(span.root),
                                                    "«y/o»: ¿ambos, uno de los dos o cualquiera?"))
        else:
            ys = [t for t in oracion if t.pos_ == "CCONJ" and t.lower_ == "y"]
            os_ = [t for t in oracion if t.pos_ == "CCONJ" and t.lower_ in ("o", "u")]
            if ys and os_:
                primero, ultimo = min(ys + os_, key=lambda x: x.i), max(ys + os_, key=lambda x: x.i)
                izq = _chunk_de(doc[primero.i - 1], chunks) if primero.i > 0 else None
                der = _chunk_de(doc[ultimo.i + 1], chunks) if ultimo.i + 1 < len(doc) else None
                ini = izq.start if izq else max(primero.i - 1, oracion.start)
                fin = der.end if der else min(ultimo.i + 2, oracion.end)
                span = doc[ini:fin]
                salida.append(self._det_alcance(span, "coordinacion_mixta", _categoria(span.root),
                                                "«y» y «o» en la misma coordinación: ¿cómo se agrupan?"))
        return salida

    @staticmethod
    def _det_alcance(span: Span, patron: str, categoria: Categoria, detalle: str) -> Deteccion:
        return Deteccion(tipo="alcance", patron=patron, texto=span.text, inicio=span.start_char, fin=span.end_char,
                         categoria=categoria, detalle=detalle)
