"""Fixtures compartidas. spaCy y los catálogos se cargan una sola vez por sesión."""
import pytest

from app.config import RAIZ_REPO


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
