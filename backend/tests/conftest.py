"""Fixtures compartidas. spaCy y los catálogos se cargan una sola vez por sesión."""
import pytest

from app.config import RAIZ_REPO
from app.db.proyectos import Proyectos
from tests.fakes import USUARIO_PRUEBA


@pytest.fixture(autouse=True, scope="session")
def _proyectos_de_la_cuenta_de_prueba():
    """Las pruebas crean proyectos con el servicio, sin pasar por la API: quedan a nombre de
    la cuenta de prueba (`como_usuario`), salvo que la prueba indique otro `propietario`.
    De sesión para alcanzar también a los fixtures de módulo que arman proyectos."""
    original = Proyectos.crear

    def crear(self, *args, propietario=None, **kwargs):
        return original(self, *args, propietario=propietario or USUARIO_PRUEBA.usuario_id, **kwargs)

    Proyectos.crear = crear
    yield
    Proyectos.crear = original


@pytest.fixture(scope="session")
def analizador():
    from app.nlp import Analizador

    try:
        return Analizador("es_core_news_sm")
    except RuntimeError as e:
        pytest.skip(str(e))


@pytest.fixture(scope="session")
def catalogos(analizador):
    from app.nlp import Catalogos

    return Catalogos.cargar(RAIZ_REPO / "data" / "catalogos", analizador)
