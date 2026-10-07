"""Separación de un texto en requisitos candidatos (ADR 0009). Función pura, sin LLM.

Cada párrafo se parte en oraciones y solo se proponen las que tienen un verbo de
obligación o capacidad. Lo demás se reporta en `fragmentos_descartados` con su
página y su motivo: el humano ve lo que se dejó fuera antes de confirmar.

Casos especiales:
- Frase introductoria con obligación que termina en dos puntos seguida de una
  lista sin verbos («El sistema deberá permitir:» / «- Registrar usuarios»): cada
  elemento se propone compuesto con la frase y conserva su identificador
  («RF-03 … permitir:» / «a) registrar» -> marca «RF-03.a»).
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
    empieza_con_verbo,
    posiciones_de_oraciones,
    tiene_caracteres_raros,
    tiene_letras,
    tiene_obligacion,
)

LARGO_ADVERTENCIA = 400  # caracteres; más largo suele ser más de un requisito
# Lo más largo que acepta la carga (RequisitoNuevo en POST /proyectos/{id}/requisitos);
# una prueba comprueba que coinciden. Lo propuesto no se recorta: el humano lo edita.
MAX_CARACTERES_REQUISITO = 2000
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


def _marca_de_elemento(intro: str | None, elemento: str | None, tipo: str | None) -> str | None:
    """La marca del requisito compuesto: «RF-03» + «a» -> «RF-03.a»; con viñeta, la de la frase."""
    if intro is None:
        return elemento
    if elemento is None or tipo == "vineta":
        return intro
    return f"{intro}.{elemento}"


def _como_continuacion(elemento: str) -> str:
    """«Registrar usuarios;» -> «registrar usuarios» para seguir a la frase introductoria."""
    elemento = re.sub(r"\s+[yeou]$", "", elemento.strip().rstrip(";,. ")).rstrip(";,. ")
    primera = elemento.split(" ", 1)[0]
    if len(primera) > 1 and primera[0].isupper() and primera[1:].islower():
        elemento = elemento[0].lower() + elemento[1:]
    return elemento


def _advertencias_finales(texto: str) -> list[str]:
    salida = []
    if len(texto) > MAX_CARACTERES_REQUISITO:
        salida.append(f"más de {MAX_CARACTERES_REQUISITO} caracteres, lo más que acepta la carga: "
                      "recórtalo o pártelo antes de analizar")
    elif len(texto) > LARGO_ADVERTENCIA:
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
            frase = introduccion.candidato
            candidatos.append(_Candidato(
                texto=f"{frase.texto.rstrip(' :')} {_como_continuacion(p.texto)}.", pagina=p.pagina,
                marca=_marca_de_elemento(frase.marca, p.marca, p.tipo_marca), original=f"{frase.original}\n{p.original}",
                advertencias=[f"compuesto con la frase introductoria «{frase.texto}»"]))
            continue
        if not tiene_letras(p.texto):
            descartados.append(FragmentoDescartado(texto=p.original, pagina=p.pagina, marca=p.marca, motivo="sin_texto"))
            titulo_con_id = None
            continue

        posiciones = posiciones_de_oraciones(p.texto)
        oraciones = [p.texto[a:b] for a, b in posiciones]
        con_obligacion = [o for o in oraciones if tiene_obligacion(o)]
        marca, heredada = p.marca, None
        if titulo_con_id is not None and p.marca is None and con_obligacion:
            marca, heredada = titulo_con_id.marca, titulo_con_id.original
        titulo_con_id = p if (p.tipo_marca == "id" and not con_obligacion and len(oraciones) == 1
                              and _es_titulo(oraciones[0])) else None

        for i, ((a, b), oracion) in enumerate(zip(posiciones, oraciones)):
            # Solo el pedazo del original de esta oración: copiar el párrafo entero en cada
            # una haría crecer el documento con el cuadrado del largo del párrafo.
            original, pagina, pagina_fin = p.fragmento(a, b)
            if not tiene_obligacion(oracion):
                descartados.append(FragmentoDescartado(
                    texto=oracion, pagina=pagina, marca=p.marca,
                    motivo="titulo" if _es_titulo(oracion) else "sin_verbo_obligacion"))
                continue
            c = _Candidato(texto=oracion, pagina=pagina, marca=marca, original=original)
            if len(con_obligacion) > 1:
                c.advertencias.append(f"una de {len(con_obligacion)} oraciones con obligación del mismo párrafo")
            if heredada:
                c.advertencias.append(f"marca tomada del título «{heredada}»")
            if pagina_fin != pagina:
                c.advertencias.append(f"continúa en la página {pagina_fin}")
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
    generales = []
    largos = [r.indice for r in requisitos if len(r.texto) > MAX_CARACTERES_REQUISITO]
    if largos:
        generales.append(f"Requisitos propuestos con más de {MAX_CARACTERES_REQUISITO} caracteres, lo más que "
                         f"acepta la carga (recórtalos o pártelos antes de analizar): "
                         f"{', '.join(map(str, largos[:20]))}{'…' if len(largos) > 20 else ''}.")
    return Separacion(requisitos_propuestos=requisitos, fragmentos_descartados=descartados[:max_fragmentos],
                      total_descartados=len(descartados), advertencias=generales)


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
