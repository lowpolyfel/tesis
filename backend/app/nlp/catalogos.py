"""Catálogos de términos regionales y de vaguedad, con PhraseMatcher (ADR 0003)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from spacy.matcher import PhraseMatcher
from spacy.tokens import Doc

from .spacy_es import Analizador, normalizar


@dataclass(frozen=True)
class Coincidencia:
    expresion: str  # entrada canónica del catálogo
    texto: str  # cómo aparece en el requisito
    inicio: int  # posición en caracteres
    fin: int
    entrada: dict


class Catalogo:
    """Un catálogo JSON compilado como dos PhraseMatcher:

    - LOWER con las `formas` declaradas (con y sin acento), porque el lematizador
      no reconoce bien las formas regionales;
    - LEMMA con la expresión canónica, que cubre flexiones de frases
      multipalabra (*da de alta*, *dé de alta*).
    """

    def __init__(self, nombre: str, datos: dict, analizador: Analizador):
        self.nombre = nombre
        self.version = datos.get("version")
        self.entradas = datos["terminos"]
        self._por_clave = {}
        nlp = analizador.nlp
        self._formas = PhraseMatcher(nlp.vocab, attr="LOWER")
        self._lemas = PhraseMatcher(nlp.vocab, attr="LEMMA")
        for e in self.entradas:
            clave = e["expresion"]
            self._por_clave[clave] = e
            formas = {f.lower() for f in e.get("formas", [])} | {clave.lower()}
            formas |= {normalizar(f) for f in formas}
            self._formas.add(clave, [nlp.make_doc(f) for f in sorted(formas)])
            if len(clave.split()) > 1:
                self._lemas.add(clave, [nlp(clave)])

    @classmethod
    def desde_archivo(cls, ruta: Path, analizador: Analizador) -> "Catalogo":
        with open(ruta, encoding="utf-8") as f:
            return cls(ruta.stem, json.load(f), analizador)

    def buscar(self, doc: Doc) -> list[Coincidencia]:
        vistos: dict[tuple[int, int], Coincidencia] = {}
        for matcher in (self._formas, self._lemas):
            for match_id, inicio, fin in matcher(doc):
                clave = doc.vocab.strings[match_id]
                span = doc[inicio:fin]
                vistos.setdefault(
                    (span.start_char, span.end_char),
                    Coincidencia(clave, span.text, span.start_char, span.end_char, self._por_clave[clave]),
                )
        # Si dos coincidencias se solapan, gana la más larga
        ordenadas = sorted(vistos.values(), key=lambda c: (c.inicio, -(c.fin - c.inicio)))
        salida: list[Coincidencia] = []
        for c in ordenadas:
            if salida and c.inicio < salida[-1].fin:
                continue
            salida.append(c)
        return salida


@dataclass
class Catalogos:
    regionales: Catalogo
    vaguedad: Catalogo

    @classmethod
    def cargar(cls, directorio: Path, analizador: Analizador) -> "Catalogos":
        return cls(
            regionales=Catalogo.desde_archivo(directorio / "regionales.json", analizador),
            vaguedad=Catalogo.desde_archivo(directorio / "vaguedad.json", analizador),
        )

    def versiones(self) -> dict:
        return {"regionales": self.regionales.version, "vaguedad": self.vaguedad.version}
