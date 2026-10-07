"""Validaciones de la configuración al arrancar."""
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_rejilla_de_calibracion_invalida_se_rechaza_al_arrancar():
    with pytest.raises(ValidationError, match="CALIBRACION_DESDE"):
        Settings(_env_file=None, calibracion_desde=0.9, calibracion_hasta=0.5)
    with pytest.raises(ValidationError, match="CALIBRACION_DESDE"):
        Settings(_env_file=None, calibracion_desde=0.7, calibracion_hasta=0.7)


def test_rejilla_por_omision_es_valida():
    s = Settings(_env_file=None)
    assert s.calibracion_desde < s.calibracion_hasta
