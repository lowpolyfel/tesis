"""Catálogos y filtros deterministas."""
import pytest

from app.models import Categoria, DecisionFiltro, EntradaLEL, Posicion, TerminoExtraido
from app.nlp import Filtros


def _buscar(cat, analizador, texto):
    return [(c.expresion, c.texto) for c in cat.buscar(analizador.doc(texto))]


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("El sistema debe jalar los datos.", ("jalar", "jalar")),
        ("Que el sistema jale los datos.", ("jalar", "jale")),
        ("El sistema jala los datos.", ("jalar", "jala")),
        ("Que cheque el campo.", ("checar", "cheque")),
        ("El sistema debe dar de alta al usuario.", ("dar de alta", "dar de alta")),
        ("El sistema da de alta al usuario.", ("dar de alta", "da de alta")),
        ("Que se dé de alta al usuario.", ("dar de alta", "dé de alta")),
    ],
)
def test_regionales_incluye_formas_y_multipalabra(catalogos, analizador, texto, esperado):
    assert esperado in _buscar(catalogos.regionales, analizador, texto)


@pytest.mark.parametrize(
    "texto, expresion",
    [
        ("Los datos deben llegar ahorita.", "ahorita"),
        ("La respuesta debe ser rápida.", "rápido"),
        ("La respuesta debe ser rapida.", "rápido"),  # sin acento
        ("Debe responder en un tiempo razonable.", "en un tiempo razonable"),
        ("Debe responder pronto.", "pronto"),
    ],
)
def test_vaguedad(catalogos, analizador, texto, expresion):
    assert expresion in [e for e, _ in _buscar(catalogos.vaguedad, analizador, texto)]


def _ext(texto, termino, categoria=Categoria.OBJETO):
    i = texto.index(termino)
    return TerminoExtraido(termino=termino, posicion=Posicion(inicio=i, fin=i + len(termino)), categoria_tentativa=categoria)


def test_caso_jalar_ahorita(catalogos, analizador):
    texto = "El sistema debe jalar los datos del servidor ahorita."
    extraidos = [_ext(texto, "sistema", Categoria.SUJETO), _ext(texto, "jalar", Categoria.VERBO), _ext(texto, "datos")]
    r = {t.termino: t.decision_filtro for t in Filtros(catalogos, analizador).aplicar(texto, extraidos, [])}
    assert r["jalar"] == DecisionFiltro.REGIONAL
    assert r["ahorita"] == DecisionFiltro.VAGUEDAD  # el Extractor no lo devolvió: lo recupera el catálogo
    assert r["sistema"] == DecisionFiltro.CANDIDATO


def test_lel_tiene_precedencia(catalogos, analizador):
    texto = "El sistema debe jalar los datos."
    lel = [EntradaLEL(simbolo="jalar", tipo="verbo", nocion=["consultar datos"], impacto=["se consultan"])]
    r = {t.termino: t.decision_filtro for t in Filtros(catalogos, analizador).aplicar(texto, [_ext(texto, "jalar", Categoria.VERBO)], lel)}
    assert r["jalar"] == DecisionFiltro.RESUELTO_POR_LEL


def test_lel_coincide_por_lema(catalogos, analizador):
    texto = "El sistema debe registrar las sesiones."
    lel = [EntradaLEL(simbolo="sesión", tipo="objeto", nocion=["periodo de uso"], impacto=["se registra"])]
    r = Filtros(catalogos, analizador).aplicar(texto, [_ext(texto, "sesiones")], lel)
    assert r[0].decision_filtro == DecisionFiltro.RESUELTO_POR_LEL


def test_salida_ordenada_por_posicion(catalogos, analizador):
    texto = "Que el sistema jale ahorita los datos."
    r = Filtros(catalogos, analizador).aplicar(texto, [_ext(texto, "datos")], [])
    assert [t.termino for t in r] == ["jale", "ahorita", "datos"]
