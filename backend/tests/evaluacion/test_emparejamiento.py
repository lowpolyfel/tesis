"""Criterio de emparejamiento de términos contra el ground truth."""
import pytest

from app.evaluacion.emparejamiento import Par, aparece_en, criterio, emparejar, lematizador, palabras, sin_lemas


@pytest.mark.parametrize("a, b, esperado", [
    ("Sesión", "sesion", "exacto"),
    ("la sesión.", "La  Sesión", "exacto"),
    ("su historial", "su", "contencion"),
    ("usuarios", "Todos los usuarios", "contencion"),
    ("dar de alta", "de alta", "contencion"),
    ("su", "usuario", None),  # no por subcadena: palabra por palabra
    ("sesiones", "sesión", None),  # sin analizador no hay lemas
    ("", "sesión", None),
    ("...", "...", None),
])
def test_criterio_sin_analizador(a, b, esperado):
    assert criterio(a, b) == esperado
    assert criterio(b, a) == esperado


def test_criterio_por_lema(analizador):
    lemas = lematizador(analizador)
    assert criterio("sesiones", "sesión", lemas) == "lema"
    assert criterio("su", "sus", lemas) is None  # sin lemas de contenido no hay criterio de lema
    assert criterio("reporte", "usuario", lemas) is None
    assert lematizador(None) is sin_lemas


def test_emparejamiento_uno_a_uno_del_criterio_mas_fuerte_al_mas_debil():
    # «su» también está contenido en «su historial», pero el par exacto se toma primero
    assert emparejar(["su", "su historial"], ["su historial"]) == [Par(1, 0, "exacto")]
    # un término del sistema no se cuenta dos veces aunque contenga a dos del ground truth
    assert emparejar(["todos los usuarios"], ["usuarios", "todos"]) == [Par(0, 0, "contencion")]
    assert emparejar(["sesión", "jalar"], ["jalar", "ahorita", "Sesión"]) == [Par(0, 2, "exacto"), Par(1, 0, "exacto")]
    assert emparejar([], ["x"]) == [] and emparejar(["x"], []) == []


def test_aparece_en_y_palabras():
    assert palabras("¿Jalé los datos?") == ("jale", "los", "datos")
    assert aparece_en("los datos", "El sistema debe jalar los datos.")
    assert not aparece_en("jale", "El sistema debe jalar los datos.")
    assert not aparece_en("", "texto")
