"""El proyecto de dos ciclos se arma una vez por módulo: recorrerlo cuesta varias corridas del grafo."""
import pytest

from tests.analisis.caminos import montar_proyecto


@pytest.fixture(scope="module")
def proyecto(tmp_path_factory, analizador):
    return montar_proyecto(tmp_path_factory.mktemp("proyecto"), analizador)
