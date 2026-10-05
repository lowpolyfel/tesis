"""Validación de cada contrato: lo que se acepta y lo que se rechaza."""
import pytest
from pydantic import ValidationError

from app.models import (
    EntradaLEL,
    EvaluacionInterpretacion,
    Interpretacion,
    Mensaje,
    Posicion,
    ResultadoRegla,
    ResultadoTermino,
    SalidaArbitraje,
    SalidaClasificador,
    SalidaExtractor,
    SalidaExtractorLLM,
    SalidaModelador,
    SalidaR3LLM,
    SalidaRefinamiento,
    TipoMensaje,
    Validacion,
)

I1 = {"id": "I1", "significado": "periodo de uso continuo", "parafrasis_del_requisito": "El sistema debe registrar el periodo de uso"}
I2 = {"id": "I2", "significado": "evento de conexión", "parafrasis_del_requisito": "El sistema debe registrar el evento de conexión"}


# ---------- Extractor
def test_extractor_llm_valido():
    s = SalidaExtractorLLM.model_validate({"terminos": [{"termino": "sesión", "categoria_tentativa": "objeto"}]})
    assert s.terminos[0].categoria_tentativa == "objeto"


def test_extractor_rechaza_categoria_desconocida():
    with pytest.raises(ValidationError):
        SalidaExtractorLLM.model_validate({"terminos": [{"termino": "sesión", "categoria_tentativa": "adjetivo"}]})


def test_posicion_fin_mayor_que_inicio():
    with pytest.raises(ValidationError):
        Posicion(inicio=5, fin=5)
    assert SalidaExtractor.model_validate(
        {"terminos": [{"termino": "sesión", "posicion": {"inicio": 3, "fin": 9}, "categoria_tentativa": "objeto"}]}
    )


def test_contratos_rechazan_campos_extra():
    with pytest.raises(ValidationError):
        SalidaExtractorLLM.model_validate({"terminos": [], "comentario": "texto libre"})


# ---------- Clasificador
def test_clasificador_dos_interpretaciones():
    s = SalidaClasificador.model_validate({"resultados": [{"termino": "sesión", "interpretaciones": [I1, I2]}]})
    assert not s.resultados[0].univoco


def test_clasificador_univoco_sin_interpretaciones():
    assert ResultadoTermino(termino="sistema", univoco=True).interpretaciones == []
    with pytest.raises(ValidationError):
        ResultadoTermino(termino="sistema", univoco=True, interpretaciones=[I1, I2])


def test_clasificador_no_univoco_exige_dos_o_mas():
    with pytest.raises(ValidationError):
        ResultadoTermino(termino="sesión", interpretaciones=[I1])


def test_clasificador_ids_unicos():
    with pytest.raises(ValidationError):
        ResultadoTermino(termino="sesión", interpretaciones=[I1, {**I2, "id": "I1"}])


def test_significado_limitado_por_configuracion():
    largo = {**I1, "significado": " ".join(["palabra"] * 13)}
    # Sin contexto no hay límite (el límite viene de la configuración)
    assert Interpretacion.model_validate(largo)
    with pytest.raises(ValidationError, match="máximo es 12"):
        Interpretacion.model_validate(largo, context={"significado_max_palabras": 12})
    exacto = {**I1, "significado": " ".join(["palabra"] * 12)}
    assert Interpretacion.model_validate(exacto, context={"significado_max_palabras": 12})


def test_refinamiento_no_retira_y_conserva_a_la_vez():
    with pytest.raises(ValidationError):
        SalidaRefinamiento.model_validate({"interpretaciones": [I1], "retiradas": [{"interpretacion_id": "I1", "motivo": "x"}]})
    with pytest.raises(ValidationError):
        SalidaRefinamiento.model_validate({"interpretaciones": [], "retiradas": []})


# ---------- Crítico
def _regla(r, cumple=True):
    return {"regla": r, "cumple": cumple, "evidencia": "ok"}


def test_evaluacion_exige_las_tres_reglas():
    base = {"interpretacion_id": "I1", "r1_estricta": _regla("R1"), "r2_estricta": _regla("R2")}
    assert EvaluacionInterpretacion.model_validate({**base, "reglas": [_regla("R1"), _regla("R2"), _regla("R3")]})
    with pytest.raises(ValidationError):
        EvaluacionInterpretacion.model_validate({**base, "reglas": [_regla("R1"), _regla("R3")]})


def test_r3_llm_exige_evidencia():
    with pytest.raises(ValidationError):
        SalidaR3LLM.model_validate({"evaluaciones": [{"interpretacion_id": "I1", "cumple": True, "evidencia": ""}]})


def test_arbitraje_justifica_cada_regla():
    j = [{"regla": r, "argumento": "porque"} for r in ("R1", "R2", "R3")]
    assert SalidaArbitraje.model_validate({"interpretacion_elegida": "I1", "justificacion_por_regla": j})
    with pytest.raises(ValidationError):
        SalidaArbitraje.model_validate({"interpretacion_elegida": "I1", "justificacion_por_regla": j[:2]})


# ---------- Modelador
def test_modelador_entrada_lel_completa():
    lel = {"simbolo": "sesión", "tipo": "objeto", "nocion": ["periodo de uso"], "impacto": ["se registra"]}
    assert SalidaModelador.model_validate({"entrada_lel": lel, "metas": {"estado": "stub"}, "big_picture": {"estado": "stub"}})
    with pytest.raises(ValidationError):
        EntradaLEL.model_validate({**lel, "nocion": []})


# ---------- Mensajes
def test_mensaje_tipo_cerrado_incluye_filtrado():
    m = Mensaje(req_id="R01", secuencia=1, ronda=0, emisor="filtros", receptor="clasificador", tipo="filtrado")
    assert m.tipo == TipoMensaje.FILTRADO
    with pytest.raises(ValidationError):
        Mensaje(req_id="R01", secuencia=1, ronda=0, emisor="filtros", receptor="clasificador", tipo="opinion")


def test_mensaje_secuencia_desde_uno():
    with pytest.raises(ValidationError):
        Mensaje(req_id="R01", secuencia=0, ronda=0, emisor="sistema", receptor="sistema", tipo="error")


def test_validacion_decision_cerrada():
    assert Validacion(decision="aprobar", interpretaciones_editadas={"sesión": I2})
    with pytest.raises(ValidationError):
        Validacion(decision="quizá")


def test_resultado_regla_detalle_opcional():
    assert ResultadoRegla(regla="R1", cumple=False, evidencia="nuevos: bitácora").detalle == {}
