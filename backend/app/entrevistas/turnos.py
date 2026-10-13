"""Lectura de una entrevista: del texto (pegado, .txt o PDF) a sus turnos (ADR 0024).

Una entrevista suele venir transcrita por hablante («Entrevistador: …», «Dra. Ruiz: …»,
a veces con la hora delante). Cada intervención es un **turno** numerado (T1, T2…):
es la unidad que citan los agentes y que la persona ve resaltada en el LEL.

- **Por hablante**: si hay al menos dos etiquetas de hablante que se repiten, cada
  renglón que empieza con una abre un turno y los renglones siguientes se le unen.
  Una etiqueta que aparece una sola vez («Nota: …», «Los pasos son: …») no cuenta
  como hablante: es texto del turno.
- **Por párrafos**: si no, los párrafos (los que reconstruye la limpieza de
  documentos, ADR 0009) son los turnos, sin hablante. Un párrafo muy largo se parte
  por oraciones.

Funciones puras, sin LLM: lo que se ve en la vista previa es lo que reciben los agentes.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from app.documentos.limpieza import reconstruir, renglones_limpios

# Límites técnicos al leer la entrevista (no parámetros del experimento)
MAX_PALABRAS_HABLANTE = 5
MAX_CARACTERES_HABLANTE = 48
MAX_CARACTERES_PARRAFO = 1500  # un párrafo sin hablante más largo se parte por oraciones
OBJETIVO_PARTE = 800

_HORA = r"(?:[\[(]?\d{1,2}:\d{2}(?::\d{2})?[\])]?\s*[-–—]?\s*)?"
_ETIQUETA = re.compile(
    rf"^\s*{_HORA}[*_]*(?P<hablante>[A-ZÁÉÍÓÚÑÜ\[][^:：\n]{{0,{MAX_CARACTERES_HABLANTE}}}?)[*_]*\s*[:：]\s*[*_]*\s*(?P<resto>.*)$")
_ORACION = re.compile(r"(?<=[.!?…])\s+(?=[¿¡«\"A-ZÁÉÍÓÚÑ0-9])")
# Etiquetas que son hablante aunque aparezcan una sola vez
_ROLES = {"entrevistador", "entrevistadora", "entrevistado", "entrevistada", "analista", "cliente", "usuario",
          "usuaria", "moderador", "moderadora", "p", "r", "q", "a", "e", "pregunta", "respuesta"}


@dataclass
class Turno:
    n: int
    hablante: str | None
    texto: str
    pagina: int | None = None

    @property
    def ref(self) -> str:
        return f"T{self.n}"


@dataclass
class EntrevistaLeida:
    turnos: list[Turno]
    modo: str  # "hablantes" | "parrafos"
    hablantes: list[dict] = field(default_factory=list)  # [{nombre, turnos, preguntas, rol_probable}]
    advertencias: list[str] = field(default_factory=list)

    @property
    def caracteres(self) -> int:
        return sum(len(t.texto) for t in self.turnos)

    def a_dict(self) -> dict:
        return {"turnos": [asdict(t) for t in self.turnos], "modo": self.modo, "hablantes": self.hablantes,
                "advertencias": self.advertencias, "caracteres": self.caracteres}


def _etiqueta(renglon: str) -> tuple[str, str] | None:
    """(hablante, resto) si el renglón empieza con una etiqueta de hablante plausible."""
    m = _ETIQUETA.match(renglon)
    if not m:
        return None
    hablante = " ".join(m["hablante"].strip(" []*_").split())
    if not hablante or len(hablante.split()) > MAX_PALABRAS_HABLANTE:
        return None
    titulo = re.search(r"\b(?:Dr|Dra|Lic|Ing|Sr|Sra|Srta|Mtro|Mtra|Prof)\.$", hablante)
    if re.search(r"[.!?…]$", hablante) and not titulo:  # termina como oración: no es una etiqueta
        return None
    if re.search(r"https?$|www$", hablante, re.IGNORECASE):  # «https://…» no es un hablante
        return None
    return hablante, m["resto"].strip()


def _unir(previo: str, siguiente: str) -> str:
    if not previo:
        return siguiente
    if previo.endswith("-") and siguiente[:1].islower():  # palabra cortada al final del renglón
        return previo[:-1] + siguiente
    return f"{previo} {siguiente}"


def _partir(texto: str) -> list[str]:
    """Un párrafo largo en partes de unas OBJETIVO_PARTE letras, por oraciones."""
    if len(texto) <= MAX_CARACTERES_PARRAFO:
        return [texto]
    partes, actual = [], ""
    for oracion in _ORACION.split(texto):
        if actual and len(actual) + len(oracion) > OBJETIVO_PARTE:
            partes.append(actual)
            actual = oracion
        else:
            actual = f"{actual} {oracion}".strip()
    if actual:
        partes.append(actual)
    return partes


def _hablantes(turnos: list[Turno]) -> list[dict]:
    """Cada hablante con sus turnos y cuántos son preguntas; quien más pregunta, si la mayoría de
    sus turnos son preguntas, es probablemente quien entrevista."""
    cuenta = Counter(t.hablante for t in turnos if t.hablante)
    preguntas = Counter(t.hablante for t in turnos if t.hablante and t.texto.rstrip().endswith("?"))
    entrevistador = None
    if preguntas:
        quien, n = preguntas.most_common(1)[0]
        if n >= 2 and n / cuenta[quien] >= 0.5:
            entrevistador = quien
    return [{"nombre": h, "turnos": n, "preguntas": preguntas.get(h, 0),
             "rol_probable": "entrevistador" if h == entrevistador else "entrevistado"}
            for h, n in cuenta.most_common()]


def _por_hablante(renglones: list[tuple[str, int | None]], validas: set[str]) -> list[Turno]:
    turnos: list[Turno] = []
    actual: Turno | None = None
    for renglon, pagina in renglones:
        if not renglon.strip():
            continue
        e = _etiqueta(renglon)
        if e and e[0].lower() in validas:
            actual = Turno(len(turnos) + 1, e[0], e[1], pagina)
            turnos.append(actual)
        elif actual is None:  # texto antes del primer hablante: un turno sin hablante
            actual = Turno(1, None, renglon.strip(), pagina)
            turnos.append(actual)
        else:
            actual.texto = _unir(actual.texto, renglon.strip())
    return [t for t in turnos if t.texto.strip()] if turnos else []


def _renumerar(turnos: list[Turno]) -> list[Turno]:
    for i, t in enumerate(turnos, 1):
        t.n = i
    return turnos


def leer_renglones(renglones: list[tuple[str, int | None]], maquetado: bool = False,
                   advertencias: list[str] | None = None) -> EntrevistaLeida:
    """Renglones (texto, página) → turnos."""
    etiquetas = Counter(e[0].lower() for r, _ in renglones if (e := _etiqueta(r)))
    validas = {h for h, n in etiquetas.items() if n >= 2 or h in _ROLES}
    repetidas = [h for h in validas if etiquetas[h] >= 2]
    avisos = list(advertencias or [])
    if len(validas) >= 2 and repetidas:
        turnos = _renumerar(_por_hablante(renglones, validas))
        sin_hablante = sum(1 for t in turnos if t.hablante is None)
        if sin_hablante:
            avisos.append("El texto antes del primer hablante quedó como un turno sin hablante.")
        return EntrevistaLeida(turnos, "hablantes", _hablantes(turnos), avisos)

    parrafos = reconstruir(renglones, maquetado)
    turnos = [Turno(0, None, parte, p.pagina) for p in parrafos for parte in _partir(" ".join(p.texto.split()))
              if parte.strip()]
    if turnos:
        avisos.append("No se reconocieron hablantes («Nombre: …»): cada párrafo es un turno.")
    return EntrevistaLeida(_renumerar(turnos), "parrafos", [], avisos)


def leer_texto(texto: str) -> EntrevistaLeida:
    """Texto pegado (o .txt): sin páginas."""
    renglones, avisos = renglones_limpios([texto], con_paginas=False)
    return leer_renglones(renglones, maquetado=False, advertencias=avisos)


def leer_paginas(paginas: list[str], con_paginas: bool, maquetado: bool) -> EntrevistaLeida:
    """Las páginas de un documento (PDF o .txt con saltos de página)."""
    renglones, avisos = renglones_limpios(paginas, con_paginas)
    return leer_renglones(renglones, maquetado=maquetado, advertencias=avisos)


def como_texto(turnos: list[dict]) -> str:
    """Los turnos de vuelta a texto («Hablante: …»), separados por un renglón en blanco: al volver
    a leerlo salen los mismos turnos (la persona puede corregir el texto de un PDF antes de enviarlo)."""
    return "\n\n".join(f"{t['hablante']}: {t['texto']}" if t.get("hablante") else t["texto"] for t in turnos)
