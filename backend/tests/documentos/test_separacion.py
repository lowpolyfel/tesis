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
    assert s.requisitos_propuestos[3].advertencias == ["continúa en la página 3"]
    assert s.requisitos_propuestos[3].texto_original == ("RF-05 El sistema deberá conservar la bitácora de cambios de "
                                                         "cada empleado durante\ncinco años contados a partir de su baja.")
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


@pytest.mark.parametrize("texto, esperado", [
    ("El usuario decide si acepta o no. El sistema debe guardar la decisión.",
     ["El usuario decide si acepta o no.", "El sistema debe guardar la decisión."]),
    ("El límite es de 5. El sistema debe bloquear la cuenta.", ["El límite es de 5.", "El sistema debe bloquear la cuenta."]),
    ("Aplica desde 2026. El sistema debe usar la versión 2.1. Luego debe migrar.",
     ["Aplica desde 2026.", "El sistema debe usar la versión 2.1.", "Luego debe migrar."]),
    ("El expediente No. 5 debe guardarse.", ["El expediente No. 5 debe guardarse."]),
    ("Los pasos son: 1. Ingresar. 2. Validar.", ["Los pasos son: 1. Ingresar.", "2. Validar."]),
])
def test_dividir_oraciones_tras_numero_o_no(texto, esperado):
    """«o no.» y un número al final de la oración la cierran; «No. 5» y la numeración en línea no."""
    assert dividir_oraciones(texto) == esperado


def test_texto_original_es_solo_el_de_la_oracion():
    """Antes cada oración llevaba el párrafo entero: un párrafo de N oraciones crecía como N²."""
    texto = "RF-04 El sistema debe guardar el dato. " * 2000
    s = separar_texto(texto)
    assert len(s.requisitos_propuestos) == 2000
    assert sum(len(r.texto_original) for r in s.requisitos_propuestos) <= len(texto)
    assert s.requisitos_propuestos[0].texto_original == "RF-04 El sistema debe guardar el dato."
    assert s.requisitos_propuestos[1].texto_original == "RF-04 El sistema debe guardar el dato."  # la marca repetida es texto
    assert {r.marca for r in s.requisitos_propuestos} == {"RF-04"}


def test_oracion_conserva_renglones_y_guion_de_corte_en_su_original():
    s = separar_texto("RF-09 Esto es contexto. El sistema deberá autenti-\ncar al usuario con su\ncontraseña. Fin.")
    r, = s.requisitos_propuestos
    assert r.texto == "El sistema deberá autenticar al usuario con su contraseña."
    assert r.texto_original == "El sistema deberá autenti-\ncar al usuario con su\ncontraseña."
    assert [f.texto for f in s.fragmentos_descartados] == ["Esto es contexto.", "Fin."]


def test_pagina_de_cada_oracion_en_parrafo_que_cruza_de_pagina():
    paginas = ["Intro\nEl sistema debe guardar la venta. El cajero podrá\n", "cerrar la caja. El gerente podrá salir."]
    s = separar_paginas(paginas, con_paginas=True, maquetado=False)
    assert [(r.pagina, r.texto, r.advertencias[1:]) for r in s.requisitos_propuestos] == [
        (1, "El sistema debe guardar la venta.", []),
        (1, "El cajero podrá cerrar la caja.", ["continúa en la página 2"]),
        (2, "El gerente podrá salir.", [])]


def test_frase_introductoria_con_identificador_lo_conserva_en_cada_elemento():
    s = separar_texto("RF-03 El sistema deberá permitir:\n- Registrar usuarios\n- Borrar usuarios\n\n"
                      "3.2.1 El cajero podrá:\na) cobrar en efectivo;\nb) cobrar con tarjeta.")
    assert [(r.marca, r.texto) for r in s.requisitos_propuestos] == [
        ("RF-03", "El sistema deberá permitir registrar usuarios."),
        ("RF-03", "El sistema deberá permitir borrar usuarios."),
        ("3.2.1.a", "El cajero podrá cobrar en efectivo."),
        ("3.2.1.b", "El cajero podrá cobrar con tarjeta.")]
    assert s.requisitos_propuestos[0].texto_original == "RF-03 El sistema deberá permitir:\n- Registrar usuarios"


def test_lista_numerada_en_minusculas_tras_frase_introductoria():
    """«1. registrar» / «2. borrar» se pegaban en un solo elemento."""
    s = separar_texto("El sistema deberá permitir:\n1. registrar usuarios,\n2. borrar usuarios, y\n3. consultar el saldo")
    assert [(r.marca, r.texto) for r in s.requisitos_propuestos] == [
        ("1", "El sistema deberá permitir registrar usuarios."), ("2", "El sistema deberá permitir borrar usuarios."),
        ("3", "El sistema deberá permitir consultar el saldo.")]


def test_requisitos_sin_punto_uno_por_renglon():
    s = separar_texto("El sistema debe guardar los datos del cliente\nEl sistema debe imprimir el ticket\n"
                      "El gerente podrá cancelar ventas")
    assert [(r.texto, r.advertencias) for r in s.requisitos_propuestos] == [
        ("El sistema debe guardar los datos del cliente", []), ("El sistema debe imprimir el ticket", []),
        ("El gerente podrá cancelar ventas", [])]


def test_texto_enorme_en_tiempo_lineal():
    """Antes, renglones en minúscula sin punto (un solo párrafo) o muchas abreviaturas costaban tiempo
    cuadrático: 80 KB tardaban 3 s, y los 10 MB permitidos, horas."""
    import time
    inicio = time.perf_counter()
    separar_texto("\n".join(["el sistema guarda datos y algo más"] * 30_000))  # ~1 MB
    separar_texto("Sr. Pérez " * 100_000)  # 1 MB
    assert time.perf_counter() - inicio < 10
