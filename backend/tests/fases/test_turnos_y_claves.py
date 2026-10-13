"""Lectura de la entrevista en turnos y claves de los términos (ADR 0024)."""
from app.entrevistas.turnos import como_texto, leer_texto
from app.fases.claves import clave, fragmento
from app.fases.memoria import acuerdos_en_texto


def test_turnos_por_hablante_con_hora_y_titulos():
    l = leer_texto("10:02 Entrevistador: ¿Cómo agendan?\n10:03 Lic. Pérez: Con una libreta,\nque luego se pierde.\n"
                   "Entrevistador: ¿Y luego?\nLic. Pérez: Nota: a veces llaman dos veces.")
    assert l.modo == "hablantes"
    assert [(t.hablante, t.texto) for t in l.turnos] == [
        ("Entrevistador", "¿Cómo agendan?"), ("Lic. Pérez", "Con una libreta, que luego se pierde."),
        ("Entrevistador", "¿Y luego?"), ("Lic. Pérez", "Nota: a veces llaman dos veces.")]
    assert l.hablantes[0]["rol_probable"] == "entrevistador"


def test_sin_hablantes_cada_parrafo_es_un_turno_y_el_largo_se_parte():
    largo = " ".join(["La asistente agenda las citas del día."] * 60)
    l = leer_texto(f"Primer párrafo.\n\n{largo}")
    assert l.modo == "parrafos" and l.turnos[0].texto == "Primer párrafo."
    assert len(l.turnos) > 2 and all(len(t.texto) <= 900 for t in l.turnos)
    assert l.advertencias


def test_el_texto_de_los_turnos_vuelve_a_dar_los_mismos_turnos():
    l = leer_texto("Primer párrafo sin punto\n\nSegundo párrafo: con dos puntos")
    otra = leer_texto(como_texto(l.a_dict()["turnos"]))
    assert [t.texto for t in otra.turnos] == [t.texto for t in l.turnos]


def test_claves_y_fragmentos():
    assert clave("Las Consultas") == clave("consulta") == "consulta"
    assert clave("los doctores") == "doctor" and clave("análisis") == "analisis"
    assert fragmento("a " * 300 + "la consulta médica" + " b" * 300, "consulta", 20).count("…") == 2


def test_acuerdos_en_texto():
    texto = acuerdos_en_texto([
        {"simbolo": "consulta", "significa": "cita médica", "no_significa": ["búsqueda en la base de datos"]},
        {"simbolo": "sistema", "descartado": True}])
    assert texto == ("- «consulta» significa: cita médica. NO significa: búsqueda en la base de datos.\n"
                     "- «sistema»: no es un término del dominio en este proyecto.")
