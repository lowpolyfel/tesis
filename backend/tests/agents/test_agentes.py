"""Cada agente con un LLM falso: contratos, verificaciones y lo que calcula el código."""
import pytest

from app.agents.clasificador import Clasificador
from app.agents.critico import Critico, ReglasCritico
from app.agents.extractor import Extractor
from app.agents.modelador import Modelador
from app.llm import FalloEstructurado
from app.models import Interpretacion, Objecion, TerminoCandidato
from tests.fakes import LLMFalso, interp, r3_todas

TEXTO = "El sistema debe registrar la sesión del usuario."


def test_extractor_calcula_posiciones_y_descarta_lo_inexistente():
    llm = LLMFalso({"extractor_v1": [{"terminos": [
        {"termino": "Sesion", "categoria_tentativa": "objeto"},  # sin acento ni mayúscula: se ubica igual
        {"termino": "sistema", "categoria_tentativa": "sujeto"},
        {"termino": "bitácora", "categoria_tentativa": "objeto"},  # no está en el texto
    ]}]})
    r = Extractor(llm).extraer(TEXTO)
    assert [(t.termino, t.posicion.inicio) for t in r.salida.terminos] == [("sistema", 3), ("sesión", 29)]
    assert r.descartados == ["bitácora"]


CANDIDATOS = [TerminoCandidato(termino="sesión", categoria_tentativa="objeto", origen="extractor"),
              TerminoCandidato(termino="sistema", categoria_tentativa="sujeto", origen="extractor")]


def test_clasificador_exige_un_resultado_por_candidato():
    incompleto = {"resultados": [{"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretaciones": [interp("I1", "a", "p1"), interp("I2", "b", "p2")]}]}
    completo = {"resultados": [*incompleto["resultados"], {"termino": "sistema", "univoco": True}]}
    r = Clasificador(LLMFalso({"clasificador_v2": [incompleto, completo]}), 12).clasificar(TEXTO, CANDIDATOS, [])
    assert r.hubo_reintento and len(r.valor.resultados) == 2


def test_clasificador_aplica_limite_de_palabras_del_significado():
    largo = " ".join(["palabra"] * 13)
    salida = {"resultados": [{"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretaciones": [interp("I1", largo, "p1"), interp("I2", "b", "p2")]},
                             {"termino": "sistema", "univoco": True}]}
    with pytest.raises(FalloEstructurado, match="máximo es 12"):
        Clasificador(LLMFalso({"clasificador_v2": [salida, salida]}), 12).clasificar(TEXTO, CANDIDATOS, [])


def test_refinamiento_no_puede_inventar_interpretaciones():
    actuales = [Interpretacion(**interp("I1", "a", "p1")), Interpretacion(**interp("I2", "b", "p2"))]
    inventa = {"interpretaciones": [interp("I3", "c", "p3")], "retiradas": [{"interpretacion_id": "I1", "motivo": "x"}, {"interpretacion_id": "I2", "motivo": "y"}]}
    bien = {"interpretaciones": [interp("I1", "a", "p1 refinada")], "retiradas": [{"interpretacion_id": "I2", "motivo": "objeción R2"}]}
    r = Clasificador(LLMFalso({"clasificador_refinamiento_v1": [inventa, bien]}), 12).refinar(TEXTO, "sesión", actuales, [])
    assert r.hubo_reintento and [i.id for i in r.valor.interpretaciones] == ["I1"]


def test_critico_combina_reglas_de_codigo_con_r3_del_llm(analizador):
    interps = [Interpretacion(**interp("I1", "periodo de uso", "El sistema debe registrar el periodo de uso del usuario.")),
               Interpretacion(**interp("I2", "evento de conexión", "El sistema debe registrar en el servidor la conexión del usuario."))]
    critico = Critico(LLMFalso({"critico_v1": r3_todas(True)}), ReglasCritico(analizador))
    r = critico.evaluar(TEXTO, "sesión", interps, [])
    por_id = {e.interpretacion_id: e for e in r.valor.evaluaciones}
    assert [x.regla for x in por_id["I1"].reglas] == ["R1", "R2", "R3"]
    assert all(x.cumple for x in por_id["I1"].reglas)
    assert not por_id["I1"].r1_estricta.cumple  # «periodo» solo viene del significado
    assert {(o.interpretacion_id, o.regla) for o in r.valor.objeciones} >= {("I2", "R2")}  # «servidor»
    # el guion falso no cita la paráfrasis: se registra, pero no cambia la decisión de R3
    assert por_id["I1"].reglas[2].detalle == {"evidencia_es_cita_de_la_parafrasis": False}


def test_arbitraje_debe_elegir_una_existente(analizador):
    j = [{"regla": r, "argumento": "x"} for r in ("R1", "R2", "R3")]
    llm = LLMFalso({"critico_arbitraje_v1": [{"interpretacion_elegida": "I9", "justificacion_por_regla": j},
                                             {"interpretacion_elegida": "I2", "justificacion_por_regla": j}]})
    interps = [Interpretacion(**interp("I1", "a", "p1")), Interpretacion(**interp("I2", "b", "p2"))]
    r = Critico(llm, ReglasCritico(analizador)).arbitrar(TEXTO, "sesión", interps, [], [])
    assert r.hubo_reintento and r.valor.interpretacion_elegida == "I2"


def test_modelador_entrada_lel():
    llm = LLMFalso({"modelador_v1": [{"entrada_lel": {"simbolo": "sesión", "tipo": "objeto", "nocion": ["periodo de uso"], "impacto": ["se registra"]}}]})
    r = Modelador(llm).modelar(TEXTO, "sesión", Interpretacion(**interp("I1", "periodo de uso", "p1")))
    assert r.valor.entrada_lel.simbolo == "sesión"


def test_modelador_requisito_reescrito_y_metas_con_reintento():
    mala = {"requisito_reescrito": "x", "metas": [{"id": "M1", "enunciado": "a", "tipo": "tarea", "contribuye_a": "M9"}]}
    buena = {"requisito_reescrito": "El sistema debe registrar el periodo de uso del usuario.", "metas": [
        {"id": "M1", "enunciado": "Registrar el periodo de uso", "tipo": "meta", "actor": "sistema", "simbolos": ["sesión"]},
        {"id": "M2", "enunciado": "Responder rápido", "tipo": "meta_blanda", "contribuye_a": "M1"}]}
    llm = LLMFalso({"modelador_requisito_v1": [mala, buena]})
    resol = [{"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretacion": interp("I1", "periodo de uso", "p1")}]
    r = Modelador(llm).modelar_requisito(TEXTO, resol, ["rápido"], ["sesión"])
    assert r.hubo_reintento and "contribuye_a" in r.intentos[0].error
    assert [m.tipo for m in r.valor.metas] == ["meta", "meta_blanda"]
    usuario = llm.llamadas["modelador_requisito_v1"][0].usuario
    assert "periodo de uso" in usuario and "rápido" in usuario and "sesión" in usuario


def test_objecion_contrato():
    assert Objecion(interpretacion_id="I1", regla="R3", texto="ambiguo").regla == "R3"
