"""Separación de un texto en requisitos candidatos (ADR 0009). Función pura, sin LLM.

Cada párrafo se parte en oraciones y solo se proponen las que tienen un verbo de
obligación o capacidad. Lo demás se reporta en `fragmentos_descartados` con su
página y su motivo: el humano ve lo que se dejó fuera antes de confirmar.

Casos especiales:
- Frase introductoria con obligación que termina en dos puntos seguida de una
  lista sin verbos («El sistema deberá permitir:» / «- Registrar usuarios»): cada
  elemento se propone compuesto con la frase.
- Título con identificador y sin verbo («RF-01 Registro de usuarios») seguido de
  un párrafo sin marca: el párrafo hereda la marca.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.nlp import normalizar

from .limpieza import MAX_PALABRAS_TITULO, Parrafo, limpiar
from .modelos import FragmentoDescartado, RequisitoPropuesto, Separacion
from .patrones import (
    TIPOS_DE_LISTA,
    dividir_oraciones,
    empieza_con_verbo,
    tiene_caracteres_raros,
    tiene_letras,
    tiene_obligacion,
)

LARGO_ADVERTENCIA = 400  # caracteres; más largo suele ser más de un requisito
MAX_FRAGMENTOS = 50  # fragmentos descartados que se devuelven; el total siempre se reporta


@dataclass
class _Candidato:
    texto: str
    pagina: int | None
    marca: str | None
    original: str
    advertencias: list[str] = field(default_factory=list)


@dataclass
class _Introduccion:
    candidato: _Candidato
    posicion: int  # en la lista de candidatos
    usos: int = 0


def _es_titulo(oracion: str) -> bool:
    return oracion.rstrip()[-1:] not in ".!?;…" and len(oracion.split()) <= MAX_PALABRAS_TITULO


def _como_continuacion(elemento: str) -> str:
    """«Registrar usuarios;» -> «registrar usuarios» para seguir a la frase introductoria."""
    elemento = re.sub(r"\s+[yeou]$", "", elemento.strip().rstrip(";,. ")).rstrip(";,. ")
    primera = elemento.split(" ", 1)[0]
    if len(primera) > 1 and primera[0].isupper() and primera[1:].islower():
        elemento = elemento[0].lower() + elemento[1:]
    return elemento


def _advertencias_finales(texto: str) -> list[str]:
    salida = []
    if len(texto) > LARGO_ADVERTENCIA:
        salida.append(f"más de {LARGO_ADVERTENCIA} caracteres: puede contener más de un requisito")
    if empieza_con_verbo(texto):
        salida.append("sin sujeto explícito: empieza con el verbo")
    if tiene_caracteres_raros(texto):
        salida.append("contiene caracteres no reconocidos: revisa la extracción")
    return salida


def separar_parrafos(parrafos: list[Parrafo], max_fragmentos: int = MAX_FRAGMENTOS) -> Separacion:
    candidatos: list[_Candidato | None] = []
    descartados: list[FragmentoDescartado] = []
    introduccion: _Introduccion | None = None
    titulo_con_id: Parrafo | None = None

    def cerrar_introduccion() -> None:
        nonlocal introduccion
        if introduccion is not None:
            if introduccion.usos:
                candidatos[introduccion.posicion] = None  # ya va dentro de cada requisito compuesto
            else:
                introduccion.candidato.advertencias.append(
                    "termina en dos puntos: revisa si le seguía una lista que no se reconoció")
        introduccion = None

    for p in parrafos:
        if introduccion is not None and p.tipo_marca not in TIPOS_DE_LISTA:
            cerrar_introduccion()
        if introduccion is not None and tiene_letras(p.texto) and not tiene_obligacion(p.texto):
            introduccion.usos += 1
            frase = introduccion.candidato.texto
            candidatos.append(_Candidato(
                texto=f"{frase.rstrip(' :')} {_como_continuacion(p.texto)}.", pagina=p.pagina, marca=p.marca,
                original=f"{frase}\n{p.original}", advertencias=[f"compuesto con la frase introductoria «{frase}»"]))
            continue
        if not tiene_letras(p.texto):
            descartados.append(FragmentoDescartado(texto=p.original, pagina=p.pagina, marca=p.marca, motivo="sin_texto"))
            titulo_con_id = None
            continue

        oraciones = dividir_oraciones(p.texto)
        con_obligacion = [o for o in oraciones if tiene_obligacion(o)]
        marca, heredada = p.marca, None
        if titulo_con_id is not None and p.marca is None and con_obligacion:
            marca, heredada = titulo_con_id.marca, titulo_con_id.original
        titulo_con_id = p if (p.tipo_marca == "id" and not con_obligacion and len(oraciones) == 1
                              and _es_titulo(oraciones[0])) else None

        for i, oracion in enumerate(oraciones):
            if not tiene_obligacion(oracion):
                descartados.append(FragmentoDescartado(
                    texto=oracion, pagina=p.pagina, marca=p.marca,
                    motivo="titulo" if _es_titulo(oracion) else "sin_verbo_obligacion"))
                continue
            c = _Candidato(texto=oracion, pagina=p.pagina, marca=marca, original=p.original)
            if len(con_obligacion) > 1:
                c.advertencias.append(f"una de {len(con_obligacion)} oraciones con obligación del mismo párrafo")
            if heredada:
                c.advertencias.append(f"marca tomada del título «{heredada}»")
            if p.pagina_fin != p.pagina:
                c.advertencias.append(f"el párrafo continúa en la página {p.pagina_fin}")
            candidatos.append(c)
            if i == len(oraciones) - 1 and oracion.endswith(":"):
                cerrar_introduccion()
                introduccion = _Introduccion(c, len(candidatos) - 1)
    cerrar_introduccion()

    requisitos: list[RequisitoPropuesto] = []
    vistos: dict[str, int] = {}
    for c in candidatos:
        if c is None:
            continue
        indice = len(requisitos) + 1
        advertencias = c.advertencias + _advertencias_finales(c.texto)
        clave = normalizar(c.texto)
        if clave in vistos:
            advertencias.append(f"repetido: igual al requisito {vistos[clave]}")
        vistos.setdefault(clave, indice)
        requisitos.append(RequisitoPropuesto(indice=indice, texto=c.texto, pagina=c.pagina, marca=c.marca,
                                             texto_original=c.original, advertencias=advertencias))
    return Separacion(requisitos_propuestos=requisitos, fragmentos_descartados=descartados[:max_fragmentos],
                      total_descartados=len(descartados))


def separar_paginas(paginas: list[str], con_paginas: bool, maquetado: bool,
                    max_fragmentos: int = MAX_FRAGMENTOS) -> Separacion:
    """Limpieza + separación. Las advertencias de la limpieza van en el resultado."""
    limpieza = limpiar(paginas, con_paginas, maquetado)
    separacion = separar_parrafos(limpieza.parrafos, max_fragmentos)
    separacion.advertencias = limpieza.advertencias + separacion.advertencias
    return separacion


def separar_texto(texto: str, max_fragmentos: int = MAX_FRAGMENTOS) -> Separacion:
    """Texto pegado o archivo .txt: un salto de página (\\f) separa páginas; sin él, no hay páginas."""
    paginas = texto.split("\f")
    return separar_paginas(paginas, con_paginas=len(paginas) > 1, maquetado=False, max_fragmentos=max_fragmentos)
