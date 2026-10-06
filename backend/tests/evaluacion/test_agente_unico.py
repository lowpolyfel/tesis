"""Línea base de un solo agente: una llamada, salida estructurada, fallas registradas."""
from string import Template

import pytest
from pydantic import ValidationError

from app.evaluacion.agente_unico import PROMPT, EntradaLineaBase, SalidaAgenteUnico, linea_base
from app.llm import cargar_prompt
from tests.fakes import LLMFalso

TEXTO = "El sistema debe registrar la sesión del usuario."
VALIDA = {"ambiguo": True, "terminos": [{"termino": "sesión", "tipo_ambiguedad": "lexica",
                                         "interpretacion_elegida": "periodo de uso"}]}


def test_una_sola_llamada_con_el_texto_y_el_limite_de_palabras():
    llm = LLMFalso({PROMPT: [VALIDA]})
    e = linea_base(llm, 12, TEXTO)
    assert e.error is None and e.resultado.model_dump(mode="json") == VALIDA
    assert (e.modelo, e.prompt_version, e.intentos) == ("llm-falso", "agente_unico_v1", 1)
    [prompt] = llm.llamadas[PROMPT]
    assert f"«{TEXTO}»" in prompt.usuario
    assert "12 palabras o menos" in prompt.usuario
    assert "La vaguedad no es ambigüedad" in prompt.usuario


def test_la_plantilla_solo_tiene_el_texto_y_el_limite():
    """El ground truth no tiene por dónde entrar: la plantilla no tiene otras variables."""
    p = cargar_prompt(PROMPT)
    variables = set(Template(p.sistema).get_identifiers()) | set(Template(p.usuario).get_identifiers())
    assert variables == {"texto", "max_palabras"}


def test_incoherencia_se_reintenta_con_el_error():
    llm = LLMFalso({PROMPT: [{"ambiguo": True, "terminos": []}, VALIDA]})
    e = linea_base(llm, 12, TEXTO)
    assert e.resultado is not None and e.intentos == 2
    assert "si ambiguo es true, terminos lleva al menos un término" in llm.llamadas[PROMPT][1].usuario


def test_dos_salidas_invalidas_quedan_como_error_con_las_salidas_crudas():
    largo = {"ambiguo": True, "terminos": [{"termino": "sesión", "tipo_ambiguedad": "lexica",
                                            "interpretacion_elegida": "una interpretación de más de tres palabras"}]}
    e = linea_base(LLMFalso({PROMPT: [largo, largo]}), 3, TEXTO)
    assert e.resultado is None and e.error.excepcion == "FalloEstructurado"
    assert e.intentos == 2 and len(e.error.intentos) == 2
    assert "el máximo es 3" in e.error.intentos[0]["error"]


def test_una_excepcion_del_cliente_no_se_propaga():
    class Caido:
        modelo = "caido"

        def completar(self, prompt, esquema):
            raise ConnectionError("Ollama no responde")

    e = linea_base(Caido(), 12, TEXTO)
    assert (e.error.excepcion, e.error.mensaje, e.modelo, e.intentos) == ("ConnectionError", "Ollama no responde",
                                                                          "caido", 0)


def test_contratos():
    with pytest.raises(ValidationError, match="si ambiguo es true"):
        SalidaAgenteUnico.model_validate({"ambiguo": False, "terminos": VALIDA["terminos"]})
    with pytest.raises(ValidationError, match="repetidos"):
        SalidaAgenteUnico.model_validate({"ambiguo": True, "terminos": VALIDA["terminos"] * 2})
    with pytest.raises(ValidationError):  # la vaguedad no es un tipo de ambigüedad
        SalidaAgenteUnico.model_validate({"ambiguo": True, "terminos": [
            {"termino": "rápido", "tipo_ambiguedad": "vaguedad", "interpretacion_elegida": "x"}]})
    with pytest.raises(ValidationError, match="resultado o error"):
        EntradaLineaBase()
