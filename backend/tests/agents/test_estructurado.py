"""Salida estructurada: valida, reintenta una vez con el error y falla con traza."""
import pytest

from app.llm import FalloEstructurado, generar
from app.llm.prompts import PromptRenderizado
from app.models import SalidaExtractorLLM
from tests.fakes import LLMFalso

P = PromptRenderizado("extractor_v1", "sistema", "usuario")
VALIDO = {"terminos": [{"termino": "sesión", "categoria_tentativa": "objeto"}]}


def test_valido_al_primer_intento():
    r = generar(LLMFalso({"extractor_v1": [VALIDO]}), P, SalidaExtractorLLM)
    assert r.valor.terminos[0].termino == "sesión"
    assert not r.hubo_reintento


def test_reintenta_una_vez_con_el_error_en_el_prompt():
    llm = LLMFalso({"extractor_v1": ['{"terminos": [{"termino": "sesión"}]}', VALIDO]})
    r = generar(llm, P, SalidaExtractorLLM)
    assert r.hubo_reintento
    assert "categoria_tentativa" in llm.llamadas["extractor_v1"][1].usuario  # el error viaja en el reintento


def test_falla_tras_dos_salidas_invalidas():
    llm = LLMFalso({"extractor_v1": ["no es json", '{"terminos": 3}']})
    with pytest.raises(FalloEstructurado) as e:
        generar(llm, P, SalidaExtractorLLM)
    assert [i.salida_cruda for i in e.value.intentos] == ["no es json", '{"terminos": 3}']
    assert e.value.payload()["prompt_version"] == "extractor_v1"


def test_tolera_bloque_de_codigo():
    r = generar(LLMFalso({"extractor_v1": ['```json\n{"terminos": []}\n```']}), P, SalidaExtractorLLM)
    assert r.valor.terminos == []


def test_verificacion_semantica_cuenta_como_fallo():
    def verificar(s):
        if not s.terminos:
            raise ValueError("faltan términos")

    llm = LLMFalso({"extractor_v1": [{"terminos": []}, VALIDO]})
    assert generar(llm, P, SalidaExtractorLLM, verificar=verificar).hubo_reintento
