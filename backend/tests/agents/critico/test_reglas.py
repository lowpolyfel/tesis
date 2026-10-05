"""Reglas R1 y R2 en código (versión relajada decide; estricta solo se registra)."""
import pytest

from app.agents.critico import ReglasCritico
from app.models import EntradaLEL, Interpretacion

TEXTO = "El sistema debe registrar la sesión del usuario."


@pytest.fixture(scope="module")
def reglas(analizador):
    return ReglasCritico(analizador)


def I(significado, parafrasis):
    return Interpretacion(id="I1", significado=significado, parafrasis_del_requisito=parafrasis)


def test_r1_cumple_si_solo_reformula_con_el_requisito(reglas):
    r, estricta = reglas.r1(TEXTO, I("sesión del usuario", "El sistema debe registrar la sesión del usuario."), [])
    assert r.cumple and estricta.cumple


def test_r1_relajada_acepta_vocabulario_del_significado_y_estricta_no(reglas):
    i = I("periodo de uso continuo", "El sistema debe registrar el periodo de uso continuo del usuario.")
    r, estricta = reglas.r1(TEXTO, i, [])
    assert r.cumple
    assert not estricta.cumple
    assert "periodo" in r.detalle["de_ellos_cubiertos_por_significado"]
    assert r.detalle["de_ellos_no_justificados"] == []
    assert "periodo" in estricta.detalle["nuevos_en_significado"]


def test_r1_falla_si_la_parafrasis_agrega_vocabulario_no_justificado(reglas):
    i = I("periodo de uso", "El sistema debe registrar el periodo de uso del usuario en una bitácora cifrada.")
    r, _ = reglas.r1(TEXTO, i, [])
    assert not r.cumple
    assert {"bitácora", "cifrada"} <= set(r.detalle["de_ellos_no_justificados"])
    assert "bitácora" in r.evidencia


def test_r1_el_lel_amplia_el_vocabulario_permitido(reglas):
    i = I("periodo de uso", "El sistema debe registrar el periodo de uso del usuario en la bitácora.")
    lel = [EntradaLEL(simbolo="bitácora", tipo="objeto", nocion=["registro de eventos"], impacto=["se consulta"])]
    sin_lel, _ = reglas.r1(TEXTO, i, [])
    con_lel, estricta = reglas.r1(TEXTO, i, lel)
    assert not sin_lel.cumple
    assert con_lel.cumple
    assert "bitácora" not in estricta.detalle["nuevos_en_parafrasis"]


def test_r2_detecta_sustantivo_nuevo(reglas):
    i = I("evento de conexión", "El sistema debe registrar el evento de conexión del usuario en el servidor.")
    r, estricta = reglas.r2(TEXTO, i, [])
    assert not r.cumple
    assert "servidor" in r.detalle["de_ellos_no_justificados"]
    assert "evento" in r.detalle["de_ellos_cubiertos_por_significado"]
    assert not estricta.cumple


def test_r2_cumple_sin_entidades_nuevas(reglas):
    r, estricta = reglas.r2(TEXTO, I("conexión", "El sistema debe registrar la conexión del usuario."), [])
    assert r.cumple
    assert not estricta.cumple  # «conexión» solo está en el significado


def test_el_lel_cuenta_aunque_spacy_cambie_el_lema_segun_el_contexto(reglas, analizador):
    # Sola, «bitácora» se etiqueta ADJ con lema «bitácoro»; en la oración es NOUN «bitácora».
    assert "bitacoro" in analizador.lemas_contenido("bitácora")
    i = I("periodo de uso", "El sistema debe registrar el periodo de uso del usuario en la bitácora.")
    lel = [EntradaLEL(simbolo="bitácora", tipo="objeto", nocion=["registro de eventos"], impacto=["se consulta"])]
    r2, r2_estricta = reglas.r2(TEXTO, i, lel)
    assert "bitácora" not in r2.detalle["nuevos_en_parafrasis"]
    assert r2.cumple
    assert r2_estricta.detalle["nuevos_en_significado"] == ["periodo"]
