"""Separación en requisitos candidatos: marcas, verbos de obligación, descartados y advertencias."""
import pytest

from app.documentos import leer, separar_paginas, separar_texto
from app.documentos.patrones import (
    detectar_marca,
    dividir_oraciones,
    empieza_con_verbo,
    tiene_obligacion,
)
from tests.documentos.muestras import (
    DESCARTADOS_SRS,
    ENCABEZADO,
    REQUISITOS_SRS,
    pdf_srs,
)


@pytest.mark.parametrize("renglon, marca, tipo, resto", [
    ("RF-01: El sistema debe x.", "RF-01", "id", "El sistema debe x."),
    ("RF01 El sistema debe x.", "RF01", "id", "El sistema debe x."),
    ("RNF-3 El sistema debe x.", "RNF-3", "id", "El sistema debe x."),
    ("R1. El sistema debe x.", "R1", "id", "El sistema debe x."),
    ("REQ-12 El sistema debe x.", "REQ-12", "id", "El sistema debe x."),
    ("[RF-02] El sistema debe x.", "RF-02", "id", "El sistema debe x."),
    ("RF-01.2 – El sistema debe x.", "RF-01.2", "id", "El sistema debe x."),
    ("3.2.1 El sistema debe x.", "3.2.1", "jerarquica", "El sistema debe x."),
    ("3.2. Requisitos", "3.2", "jerarquica", "Requisitos"),
    ("1. El sistema debe x.", "1", "numero", "El sistema debe x."),
    ("1) El sistema debe x.", "1", "numero", "El sistema debe x."),
    ("1- El sistema debe x.", "1", "numero", "El sistema debe x."),
    ("1.- El sistema debe x.", "1", "numero", "El sistema debe x."),
    ("a) el sistema debe x.", "a", "letra", "el sistema debe x."),
    ("- El sistema debe x.", "-", "vineta", "El sistema debe x."),
    ("• El sistema debe x.", "•", "vineta", "El sistema debe x."),
    ("* El sistema debe x.", "*", "vineta", "El sistema debe x."),
    ("\uf0b7El sistema debe x.", "•", "vineta", "El sistema debe x."),
    ("•Registrar usuarios.", "•", "vineta", "Registrar usuarios."),
    ("RF-07", "RF-07", "id", ""),
])
def test_detecta_marcas(renglon, marca, tipo, resto):
    assert detectar_marca(renglon) == (marca, tipo, resto)


@pytest.mark.parametrize("renglon", [
    "El sistema debe x.", "2026 es el año fiscal.", "10-15 usuarios a la vez.", "-5 grados como mínimo.",
    "RFC del cliente obligatorio.", "Requisito sin marca.",
])
def test_sin_marca(renglon):
    assert detectar_marca(renglon) == (None, None, renglon)


@pytest.mark.parametrize("oracion", [
    "El sistema debe guardar.", "Los usuarios deben salir.", "El sistema deberá guardar.", "El sistema debera guardar.",
    "Los cajeros deberán cobrar.", "El sistema debería avisar.", "Los reportes deberían salir.",
    "El gerente podrá autorizar.", "Los gerentes podrán autorizar.", "El usuario puede salir.",
    "Los usuarios pueden salir.", "El sistema permitirá exportar.", "Los módulos permitirán exportar.",
    "El sistema tiene que validar.", "El sistema tendrá que validar.", "El sistema ha de validar.",
    "Se requiere un respaldo diario.", "Es necesario cifrar la base.", "Es obligatorio firmar el contrato.",
    "EL SISTEMA DEBERÁ GUARDAR.",
])
def test_verbos_de_obligacion_sin_acentos(oracion):
    assert tiene_obligacion(oracion)


@pytest.mark.parametrize("oracion", [
    "El sistema registra la sesión.", "Este documento describe el módulo.", "Es un deber cívico.",
    "Para que el usuario pueda salir.", "Requisitos funcionales",
])
def test_sin_verbo_de_obligacion(oracion):
    assert not tiene_obligacion(oracion)


@pytest.mark.parametrize("texto, esperado", [
    ("Debe guardar.", True), ("Además, deberá avisar.", True), ("Se debe validar el campo.", True),
    ("No podrá borrar.", True), ("El sistema debe guardar.", False), ("Se requiere un respaldo.", False),
])
def test_empieza_con_verbo(texto, esperado):
    assert empieza_con_verbo(texto) is esperado


def test_dividir_oraciones_respeta_abreviaturas_y_numeros():
    assert dividir_oraciones("El sistema debe aceptar p. ej. RFC o CURP. Sr. Pérez lo pidió. 1. Ingresar. "
                             "La versión 2.1 debe salir. ¿Qué pasa? Nada.") == [
        "El sistema debe aceptar p. ej. RFC o CURP.", "Sr. Pérez lo pidió.", "1. Ingresar.",
        "La versión 2.1 debe salir.", "¿Qué pasa?", "Nada."]


def test_documento_de_muestra_completo():
    extraido = leer("srs.pdf", pdf_srs(), 10**7)
    s = separar_paginas(extraido.paginas, extraido.con_paginas, maquetado=True)
    assert [(r.marca, r.pagina, r.texto) for r in s.requisitos_propuestos] == REQUISITOS_SRS
    assert [r.indice for r in s.requisitos_propuestos] == [1, 2, 3, 4, 5]
    assert [(f.texto, f.pagina, f.marca, f.motivo) for f in s.fragmentos_descartados] == DESCARTADOS_SRS
    assert s.total_descartados == len(DESCARTADOS_SRS)
    assert s.advertencias == ["Números de página sueltos quitados en 3 páginas.",
                              f"Encabezado o pie de página quitado (3 de 3 páginas): «{ENCABEZADO}»."]
    rnf = s.requisitos_propuestos[2]
    assert rnf.texto_original.startswith("RNF-3 La aplicación tendrá que responder") and "consul-\nta" in rnf.texto_original
    assert s.requisitos_propuestos[3].advertencias == ["el párrafo continúa en la página 3"]
    assert ENCABEZADO not in " ".join(r.texto_original for r in s.requisitos_propuestos)


def test_parrafo_con_varias_oraciones_se_parte_y_las_demas_se_reportan():
    s = separar_texto("RF-04 El sistema debe jalar los datos del SAT cada noche. Esto ahorra tiempo. "
                      "Además, debe checar que el RFC sea válido.")
    assert [(r.marca, r.texto) for r in s.requisitos_propuestos] == [
        ("RF-04", "El sistema debe jalar los datos del SAT cada noche."),
        ("RF-04", "Además, debe checar que el RFC sea válido.")]
    assert s.requisitos_propuestos[0].advertencias == ["una de 2 oraciones con obligación del mismo párrafo"]
    assert s.requisitos_propuestos[1].advertencias == ["una de 2 oraciones con obligación del mismo párrafo",
                                                       "sin sujeto explícito: empieza con el verbo"]
    assert [(f.texto, f.marca, f.motivo, f.pagina) for f in s.fragmentos_descartados] == [
        ("Esto ahorra tiempo.", "RF-04", "sin_verbo_obligacion", None)]


def test_titulos_y_marcas_sin_texto_se_descartan_con_motivo():
    s = separar_texto("Requisitos de seguridad\nEl sistema deberá cifrar las contraseñas.\n\nRF-09\n\n4.1 Glosario")
    assert [r.texto for r in s.requisitos_propuestos] == ["El sistema deberá cifrar las contraseñas."]
    assert [(f.texto, f.marca, f.motivo) for f in s.fragmentos_descartados] == [
        ("Requisitos de seguridad", None, "titulo"), ("RF-09", "RF-09", "sin_texto"), ("Glosario", "4.1", "titulo")]


def test_fragmentos_descartados_se_limitan_pero_el_total_se_reporta():
    texto = "\n".join(f"Oración informativa número {n} del documento." for n in range(60))
    s = separar_texto(texto + "\nEl sistema debe guardar.")
    assert len(s.fragmentos_descartados) == 50 and s.total_descartados == 60
    assert s.fragmentos_descartados[0].texto == "Oración informativa número 0 del documento."
    assert len(s.requisitos_propuestos) == 1
    assert separar_texto(texto, max_fragmentos=5).total_descartados == 60


def test_advertencia_de_requisito_largo():
    largo = "El sistema debe registrar " + ", ".join(f"el dato {n}" for n in range(60)) + "."
    r, = separar_texto(largo).requisitos_propuestos
    assert len(r.texto) > 400 and "más de 400 caracteres: puede contener más de un requisito" in r.advertencias


def test_frase_introductoria_con_lista_compone_cada_elemento():
    s = separar_texto("El sistema deberá permitir:\n- Registrar incidencias;\n- Generar el recibo timbrado, y\n"
                      "- El gerente podrá cancelar recibos.\nTexto después de la lista.")
    assert [(r.marca, r.texto) for r in s.requisitos_propuestos] == [
        ("-", "El sistema deberá permitir registrar incidencias."),
        ("-", "El sistema deberá permitir generar el recibo timbrado."),
        ("-", "El gerente podrá cancelar recibos.")]
    primero = s.requisitos_propuestos[0]
    assert primero.texto_original == "El sistema deberá permitir:\n- Registrar incidencias;"
    assert primero.advertencias == ["compuesto con la frase introductoria «El sistema deberá permitir:»"]
    assert [f.texto for f in s.fragmentos_descartados] == ["Texto después de la lista."]


def test_frase_introductoria_sin_lista_se_propone_con_advertencia():
    s = separar_texto("El sistema deberá validar lo siguiente:\n\nNotas finales del documento.")
    r, = s.requisitos_propuestos
    assert r.texto == "El sistema deberá validar lo siguiente:"
    assert r.advertencias == ["termina en dos puntos: revisa si le seguía una lista que no se reconoció"]


def test_titulo_con_identificador_pasa_su_marca_al_parrafo_siguiente():
    s = separar_texto("RF-01 Registro de usuarios\nEl administrador podrá dar de alta usuarios.\n"
                      "El sistema debe enviar un correo.")
    assert [(r.marca, r.texto) for r in s.requisitos_propuestos] == [
        ("RF-01", "El administrador podrá dar de alta usuarios."), (None, "El sistema debe enviar un correo.")]
    assert s.requisitos_propuestos[0].advertencias == ["marca tomada del título «RF-01 Registro de usuarios»"]
    assert [(f.texto, f.marca, f.motivo) for f in s.fragmentos_descartados] == [
        ("Registro de usuarios", "RF-01", "titulo")]


def test_repetidos_y_caracteres_no_reconocidos_se_advierten():
    s = separar_texto("El sistema debe guardar.\nEL SISTEMA DEBE GUARDAR.\nEl sistema debe gu\ufffdrdar.")
    assert [r.advertencias for r in s.requisitos_propuestos] == [
        [], ["repetido: igual al requisito 1"], ["contiene caracteres no reconocidos: revisa la extracción"]]


def test_texto_con_saltos_de_pagina_reporta_pagina():
    s = separar_texto("El sistema debe guardar.\fSin verbo aquí.\fEl sistema debe salir.")
    assert [(r.pagina, r.texto) for r in s.requisitos_propuestos] == [(1, "El sistema debe guardar."),
                                                                      (3, "El sistema debe salir.")]
    assert [(f.pagina, f.motivo) for f in s.fragmentos_descartados] == [(2, "sin_verbo_obligacion")]


def test_texto_sin_requisitos():
    s = separar_texto("Introducción\nEste documento describe el sistema.")
    assert s.requisitos_propuestos == [] and s.total_descartados == 2
