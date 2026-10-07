"""Piezas puras de la comparación: citas, matriz, selección de pares, perfiles,
inconsistencias de vocabulario, bases de comparación y contrato del juez."""
import pytest
from pydantic import ValidationError

from app.comparacion import (
    Perfil,
    SalidaComparadorLLM,
    SignificadoValidado,
    analizar_simbolos,
    bases_de_comparacion,
    casi_duplicados,
    cita_literal,
    inconsistencias_vocabulario,
    matriz_similitud,
    perfil,
    seleccionar_pares,
    significados_validados,
)
from app.models import Estado, Origen, Traza
from tests.comparacion.ayudantes import entrada_lel

TEXTO = "La sesión del usuario debe cerrarse a los 15 minutos de inactividad."


@pytest.mark.parametrize("cita, esperado", [
    ("debe cerrarse a los 15 minutos", True),
    ("LA SESION DEL USUARIO", True),  # mayúsculas y acentos no cuentan
    ("«a los 15   minutos de inactividad.»", True),  # comillas, espacios y punto final tampoco
    ("debe cerrarse a los quince minutos", False),
    ("la sesión se cierra a los 15 minutos", False),  # paráfrasis: no es literal
    ("«»", False),
    ("debe cerrar", False),  # palabra cortada: «cerrar» no está, está «cerrarse»
    ("sion del usuario", False),  # empieza a media palabra («sesión»)
    ("5 minutos", False),  # dentro de «15»
    ("inactividad", True),  # al final, antes del punto
])
def test_cita_literal(cita, esperado):
    assert cita_literal(cita, TEXTO) is esperado


def test_matriz_similitud_por_par_y_dimension():
    m = matriz_similitud(["R01", "R02", "R05"], [[1, 0], [0, 1], [1, 1]])
    assert list(m) == ["R01-R02", "R01-R05", "R02-R05"]
    assert m["R01-R02"] == 0.0 and m["R01-R05"] == pytest.approx(0.7071, abs=1e-4)
    with pytest.raises(ValueError):
        matriz_similitud(["R01", "R02"], [[1, 0]])


def test_seleccion_ordena_por_similitud_corta_y_reporta():
    ids = ["R01", "R02", "R03", "R04"]
    matriz = {"R01-R02": 0.9, "R01-R03": 0.5, "R01-R04": 0.1, "R02-R03": 0.7, "R02-R04": 0.2, "R03-R04": 0.65}
    perfiles = {r: Perfil() for r in ids}
    perfiles["R01"] = Perfil(lemas={"factura": "factura"})
    perfiles["R04"] = Perfil(lemas={"factura": "facturas"}, simbolos={"sesion": "sesión"})
    perfiles["R02"] = Perfil(simbolos={"sesion": "sesión"})
    sel = seleccionar_pares(ids, matriz, perfiles, umbral_relacion=0.6, max_pares=3)
    assert [p.clave for p in sel.evaluar] == ["R01-R02", "R02-R03", "R03-R04"]
    assert [(p.clave, p.motivos, p.compartidos) for p in sel.fuera] == [
        ("R02-R04", ("simbolo_lel",), ("sesión",)), ("R01-R04", ("lema",), ("factura",))]
    assert sel.candidatos == 5  # R01-R03 (0.5, sin términos compartidos) no es candidato
    assert casi_duplicados(ids, matriz, 0.9) == [("R01", "R02", 0.9)]


def test_perfil_encuentra_simbolos_por_forma_y_por_lema(analizador):
    p = perfil(analizador, "El sistema da de alta al cliente y guarda su sesión.", ["dar de alta", "sesión", "bitácora"])
    assert set(p.simbolos.values()) == {"dar de alta", "sesión"}
    assert {"sistema", "cliente", "sesion"} <= set(p.lemas)


def test_inconsistencias_desde_el_lel():
    lel = [entrada_lel("P01", "R01", "sesión", ["Periodo de uso del sistema."]),
           entrada_lel("P01", "R02", "Sesion", ["Evento de conexión al sistema."]),
           entrada_lel("P01", "R03", "sesión", ["periodo de uso del sistema"]),  # igual a R01 al normalizar
           entrada_lel("P01", "R04", "bitácora", ["Registro de accesos."]),
           entrada_lel("P01", "R04", "sesión", ["Evento de conexión al sistema."])]  # igual a R02
    hs = inconsistencias_vocabulario(lel, [])
    assert [(h["requisitos"], h["fuente"], h["terminos"]) for h in hs] == [
        (["R01", "R02"], "lel", ["sesión"]), (["R01", "R04"], "lel", ["sesión"]),
        (["R02", "R03"], "lel", ["sesión"]), (["R03", "R04"], "lel", ["sesión"])]
    assert hs[0]["evidencia"] == [{"req_id": "R01", "cita": "Periodo de uso del sistema.", "verificada": True},
                                  {"req_id": "R02", "cita": "Evento de conexión al sistema.", "verificada": True}]


def test_perfil_con_simbolos_ya_analizados(analizador):
    simbolos = ["dar de alta", "sesión", "bitácora"]
    texto = "El sistema da de alta al cliente y guarda su sesión."
    assert perfil(analizador, texto, analizar_simbolos(analizador, simbolos)) == perfil(analizador, texto, simbolos)


def test_el_orden_de_los_enunciados_de_la_nocion_no_cuenta():
    lel = [entrada_lel("P01", "R01", "sesión", ["Periodo de uso.", "Empieza al entrar."]),
           entrada_lel("P01", "R02", "sesión", ["Empieza al entrar.", "periodo de uso"]),
           entrada_lel("P01", "R03", "sesión", ["Periodo de uso."])]
    hs = inconsistencias_vocabulario(lel, [])
    assert [h["requisitos"] for h in hs] == [["R01", "R03"], ["R02", "R03"]]


def test_inconsistencias_por_validacion_y_union_con_el_lel():
    lel = [entrada_lel("P01", "R01", "sesión", ["Periodo de uso."]),
           entrada_lel("P01", "R02", "sesión", ["Evento de conexión."])]
    significados = [SignificadoValidado("R01", "sesión", "periodo de uso"),
                    SignificadoValidado("R02", "Sesión", "evento de conexión"),
                    SignificadoValidado("R01", "jalar", "consultar"),
                    SignificadoValidado("R03", "jalar", "Consultar."),
                    SignificadoValidado("R05", "jalar", "descargar")]
    hs = inconsistencias_vocabulario(lel, significados)
    assert [(h["requisitos"], h["fuente"], h["terminos"]) for h in hs] == [
        (["R01", "R02"], "lel", ["sesión"]), (["R01", "R05"], "validacion", ["jalar"]),
        (["R03", "R05"], "validacion", ["jalar"])]
    # el par R01-R02 sale una sola vez: el hallazgo del LEL menciona también los significados
    assert "El significado validado también difiere" in hs[0]["explicacion"]
    assert "«consultar» en R01 y «descargar» en R05" in hs[1]["explicacion"]


def _traza(req_id, estado, texto="El sistema debe registrar la sesión.", **kw):
    return Traza(req_id=req_id, estado=estado, texto=texto, config={}, **kw)


def test_bases_de_comparacion():
    trazas = [_traza("R01", Estado.FORMALIZADO), _traza("R02", Estado.ERROR), _traza("R03", Estado.RECHAZADO),
              _traza("R04", Estado.PENDIENTE_VALIDACION), _traza("R05", Estado.FORMALIZADO),
              _traza("R06", Estado.CARGADO, origen=Origen(reproceso_de="R05")),
              _traza("R07", Estado.ERROR, origen=Origen(reproceso_de="R04"))]  # el reproceso falló: R04 sigue
    requisitos, excluidos = bases_de_comparacion(trazas, {"R01": {"requisito_reescrito": "Texto reescrito."}})
    assert [(r.req_id, r.base, r.texto) for r in requisitos] == [
        ("R01", "reescrito", "Texto reescrito."), ("R04", "original", "El sistema debe registrar la sesión."),
        ("R06", "original", "El sistema debe registrar la sesión.")]
    assert [(e.req_id, e.motivo, e.detalle) for e in excluidos] == [
        ("R02", "error", None), ("R03", "rechazado", None), ("R05", "reprocesado", "lo vuelve a procesar R06"),
        ("R07", "error", None)]


def test_bases_siguen_la_cadena_de_reprocesos():
    """R02 reprocesa R01 y falla; R03 reprocesa R02: R03 sustituye también a R01 (antes
    entraban R01 y R03, el mismo requisito dos veces)."""
    trazas = [_traza("R01", Estado.FORMALIZADO), _traza("R02", Estado.ERROR, origen=Origen(reproceso_de="R01")),
              _traza("R03", Estado.FORMALIZADO, origen=Origen(reproceso_de="R02"))]
    requisitos, excluidos = bases_de_comparacion(trazas, {})
    assert [r.req_id for r in requisitos] == ["R03"]
    assert [(e.req_id, e.motivo, e.detalle) for e in excluidos] == [
        ("R01", "reprocesado", "lo vuelve a procesar R03"), ("R02", "error", None)]


def test_significados_validados_solo_lexicos():
    formalizado = {"resoluciones": [
        {"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretacion": {"significado": "periodo de uso"}},
        {"termino": "él", "tipo_ambiguedad": "anaforica", "interpretacion": {"significado": "el administrador"}},
        {"termino": "jalar", "tipo_ambiguedad": None, "interpretacion": {"significado": "consultar"}}]}
    s = significados_validados(_traza("R01", Estado.FORMALIZADO), formalizado)
    assert [(x.termino, x.significado) for x in s] == [("sesión", "periodo de uso"), ("jalar", "consultar")]


def test_contrato_del_juez():
    ok = SalidaComparadorLLM.model_validate({"relacion": "redundancia", "explicacion": " Piden lo mismo. ",
                                             "cita_a": "registrar", "cita_b": "guardar"})
    assert ok.explicacion == "Piden lo mismo."
    larga = {"relacion": "contradiccion", "explicacion": " ".join(["palabra"] * 61), "cita_a": "a", "cita_b": "b"}
    with pytest.raises(ValidationError, match="61 palabras"):
        SalidaComparadorLLM.model_validate(larga)
    with pytest.raises(ValidationError):
        SalidaComparadorLLM.model_validate({**larga, "explicacion": "Corta.", "relacion": "conflicto"})
    with pytest.raises(ValidationError):
        SalidaComparadorLLM.model_validate({**larga, "explicacion": "Corta.", "cita_a": "   "})
