"""Texto de entrada con sustitutos UTF-16 sueltos: se rechaza al validar, no al guardar."""
import json

import pytest
from pydantic import ValidationError

from app.models import Origen, Validacion

SUELTO = json.loads('"emitir el recibo \\ud83d"')  # así llega desde un JSON con un escape suelto


@pytest.mark.parametrize("datos", [
    {"archivo": "srs.pdf", "texto_original": SUELTO},
    {"marca": SUELTO},
])
def test_origen_rechaza_sustitutos_sueltos(datos):
    with pytest.raises(ValidationError, match="sustituto UTF-16 suelto"):
        Origen.model_validate(datos)


def test_validacion_rechaza_sustitutos_en_el_comentario_y_en_los_terminos():
    with pytest.raises(ValidationError, match="sustituto"):
        Validacion.model_validate({"decision": "aprobar", "comentario": SUELTO})
    edicion = {"id": "I1", "significado": "a", "parafrasis_del_requisito": "b"}
    with pytest.raises(ValidationError, match="sustituto"):
        Validacion.model_validate({"decision": "aprobar", "interpretaciones_editadas": {SUELTO: edicion}})


def test_texto_valido_con_emoji_y_acentos_pasa():
    assert Origen(archivo="señal 😀.pdf", pagina=2).archivo == "señal 😀.pdf"
    assert Validacion(decision="rechazar", comentario="no está claro 🤔").comentario == "no está claro 🤔"
