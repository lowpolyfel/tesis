"""Detectores deterministas de ambigüedad de alcance y anafórica (ADR 0010)."""
import pytest

from app.nlp.detectores import Detectores


@pytest.fixture(scope="module")
def det(analizador):
    return Detectores(analizador)


def patrones(det, texto):
    return [(d.tipo, d.patron, d.texto) for d in det.buscar(texto)]


def test_posesivo_con_dos_antecedentes(det):
    [d] = det.buscar("El administrador debe notificar al usuario cuando su cuenta expire.")
    assert (d.tipo, d.patron, d.texto) == ("anafora", "posesivo", "su cuenta")
    assert d.antecedentes == ("administrador", "usuario")
    assert "administrador" in d.detalle and d.inicio == 50


def test_posesivo_con_un_solo_antecedente_no_se_marca(det):
    assert patrones(det, "El sistema debe guardar sus notas.") == []


def test_demostrativo_concuerda_en_genero_y_numero(det):
    [d] = det.buscar("El sistema debe enviar el reporte al gerente y al auditor y este debe firmarlo.")
    assert d.patron == "demostrativo" and d.texto == "este"
    assert "gerente" in d.antecedentes and "auditor" in d.antecedentes


@pytest.mark.parametrize("texto, patron, tramo", [
    ("Todos los usuarios no deben acceder al módulo de nómina.", "universal+negacion", "Todos los usuarios"),
    ("Cada vendedor debe registrar un cliente nuevo.", "universal+indefinido", "Cada vendedor"),
    ("El sistema solo debe permitir el acceso a los administradores.", "foco", "solo debe permitir el acceso"),
    ("El usuario y/o el administrador podrán exportar los datos.", "y/o", "El usuario y/o el administrador"),
    ("El sistema debe validar el pago y enviar la factura o el recibo.", "coordinacion_mixta",
     "el pago y enviar la factura o el recibo"),
])
def test_patrones_de_alcance(det, texto, patron, tramo):
    assert ("alcance", patron, tramo) in patrones(det, texto)


@pytest.mark.parametrize("texto", [
    "El sistema debe registrar la sesión del usuario.",
    "El sistema debe permitir al administrador eliminar usuarios inactivos.",
    "El sistema debe jalar los datos del servidor ahorita.",
])
def test_requisitos_de_aceptacion_sin_estructuras(det, texto):
    assert det.buscar(texto) == []


def test_los_filtros_agregan_las_estructuras_como_candidatos(analizador, catalogos):
    from app.nlp import Filtros

    texto = "El administrador debe notificar al usuario cuando su cuenta expire."
    salida = Filtros(catalogos, analizador).aplicar(texto, [], [])
    [f] = [x for x in salida if x.decision_filtro == "anafora"]
    assert f.termino == "su cuenta" and texto[f.posicion.inicio:f.posicion.fin] == "su cuenta"
    assert f.detalle.startswith("posesivo:")
