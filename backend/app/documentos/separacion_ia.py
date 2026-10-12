"""Separación de requisitos con IA (ADR 0023).

Los patrones (separacion.py) solo proponen oraciones con «debe», «podrá» o «permitirá»,
y dejan fuera los requisitos que llegan de otra forma: en presente («la caja imprime
el ticket»), en infinitivo, como historia de usuario o como frase nominal. Aquí el
Revisor lee los párrafos ya limpios (la limpieza no cambia) y dice qué requisitos hay
y de qué párrafos salen. El código cuida tres cosas:

- fidelidad: cada requisito debe salir de sus párrafos; si trae palabras que no están
  en ellos, se rechaza y se reintenta (no se aceptan requisitos inventados);
- trazabilidad: la página, la marca y el texto original salen de los párrafos;
- nada se pierde: un párrafo que no usó ningún requisito queda en los descartados.

Si el Revisor falla, quien llama separa con patrones (`separar_paginas(ia=…)`).
"""
from __future__ import annotations

import re

from app.nlp import normalizar

from .limpieza import Parrafo
from .modelos import FragmentoDescartado, Separacion
from .separacion import MAX_FRAGMENTOS, _Candidato, armar_separacion

MAX_CARACTERES_TANDA = 6000
MAX_PARRAFOS_TANDA = 60
MAX_PARRAFOS = 600  # más que esto, la separación con IA serían demasiadas llamadas
FIDELIDAD = 0.8  # proporción de palabras del requisito que debe estar en sus párrafos
_PALABRA = re.compile(r"[a-z0-9ñ]{4,}")


class DemasiadoTexto(ValueError):
    pass


def _palabras(texto: str) -> set[str]:
    return set(_PALABRA.findall(normalizar(texto)))


def _numerado(i: int, p: Parrafo) -> str:
    pagina = f" [p. {p.pagina}]" if p.pagina else ""
    marca = f"{p.marca} " if p.marca else ""
    return f"P{i}{pagina} {marca}{p.texto}"


def tandas(parrafos: list[Parrafo]) -> list[list[int]]:
    """Índices (desde 1) agrupados para que cada llamada lleve un texto acotado."""
    salida, actual, largo = [], [], 0
    for i, p in enumerate(parrafos, 1):
        if actual and (largo + len(p.texto) > MAX_CARACTERES_TANDA or len(actual) >= MAX_PARRAFOS_TANDA):
            salida.append(actual)
            actual, largo = [], 0
        actual.append(i)
        largo += len(p.texto)
    if actual:
        salida.append(actual)
    return salida


def verificador(parrafos: list[Parrafo], indices: list[int]):
    """Para `generar(verificar=…)`: párrafos de esta tanda y requisitos fieles a ellos."""
    validos = set(indices)

    def verificar(salida) -> None:
        for r in salida.requisitos:
            if fuera := sorted(set(r.parrafos) - validos):
                raise ValueError(f"párrafos que no están en el texto: {fuera}")
            fuente = set().union(*(_palabras(parrafos[i - 1].texto) for i in r.parrafos))
            propias = _palabras(r.texto)
            if propias and len(propias & fuente) / len(propias) < FIDELIDAD:
                ajenas = sorted(propias - fuente)[:6]
                raise ValueError(f"el requisito «{r.texto[:80]}» usa palabras que no están en sus párrafos "
                                 f"({', '.join(ajenas)}): cópialo del texto, no lo reescribas")
        for d in salida.descartados:
            if d.parrafo not in validos:
                raise ValueError(f"descartado con un párrafo que no está en el texto: P{d.parrafo}")
    return verificar


def separar_con_ia(parrafos: list[Parrafo], revisor, contexto: str | None,
                   max_fragmentos: int = MAX_FRAGMENTOS) -> Separacion:
    """Lanza la excepción del Revisor (o `DemasiadoTexto`) para que quien llama use los patrones."""
    if len(parrafos) > MAX_PARRAFOS:
        raise DemasiadoTexto(f"{len(parrafos)} párrafos: más de {MAX_PARRAFOS} para separar con IA")
    candidatos: list[tuple[int, _Candidato]] = []
    motivos: dict[int, str] = {}
    usados: set[int] = set()
    modelo = None
    contexto = (contexto or "").strip() or "(el proyecto no tiene contexto general)"
    for tanda in tandas(parrafos):
        texto = "\n".join(_numerado(i, parrafos[i - 1]) for i in tanda)
        r = revisor.separar(contexto, texto, verificar=verificador(parrafos, tanda))
        modelo = r.modelo
        for req in r.valor.requisitos:
            fuente = [parrafos[i - 1] for i in sorted(set(req.parrafos))]
            usados.update(req.parrafos)
            c = _Candidato(texto=" ".join(req.texto.split()), pagina=fuente[0].pagina,
                           marca=req.marca or fuente[0].marca, original="\n".join(p.original for p in fuente))
            if len(fuente) > 1:
                c.advertencias.append(f"compuesto de {len(fuente)} párrafos")
            candidatos.append((min(req.parrafos), c))
        for d in r.valor.descartados:
            motivos.setdefault(d.parrafo, d.motivo)
    candidatos.sort(key=lambda x: x[0])  # estable: en una tanda, el orden que dio el Revisor
    descartados = [FragmentoDescartado(texto=p.texto, pagina=p.pagina, marca=p.marca, motivo="no_es_requisito",
                                       detalle=motivos.get(i)) for i, p in enumerate(parrafos, 1) if i not in usados]
    return armar_separacion([c for _, c in candidatos], descartados, max_fragmentos, metodo="ia", modelo=modelo)
