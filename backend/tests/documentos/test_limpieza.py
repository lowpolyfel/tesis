"""Limpieza del texto extraído y reconstrucción de párrafos."""
from app.documentos.limpieza import limpiar, normalizar_caracteres

PIE = "Confidencial — uso interno"


def _textos(limpieza):
    return [p.texto for p in limpieza.parrafos]


def test_quita_encabezado_pie_y_numeros_de_pagina():
    paginas = ["ACME SRS v2\nEl sistema debe guardar.\n1", "ACME SRS v2\nEl sistema debe salir.\n- 2 -",
               "ACME SRS v3\nEl sistema debe entrar.\nPág. 3"]
    resultado = limpiar(paginas, con_paginas=True, maquetado=True)
    assert _textos(resultado) == ["El sistema debe guardar.", "El sistema debe salir.", "El sistema debe entrar."]
    assert [p.pagina for p in resultado.parrafos] == [1, 2, 3]
    # «v2» y «v3» son el mismo renglón salvo el número
    assert resultado.advertencias == ["Números de página sueltos quitados en 3 páginas.",
                                      "Encabezado o pie de página quitado (3 de 3 páginas): «ACME SRS v2»."]


def test_repetido_en_al_menos_la_mitad_de_las_paginas():
    paginas = [f"Texto propio {letra} sin verbo.\n{PIE}" if letra in "ab" else f"Texto propio {letra} sin verbo."
               for letra in "abcd"]
    resultado = limpiar(paginas, con_paginas=True, maquetado=True)
    assert PIE not in " ".join(_textos(resultado))
    assert resultado.advertencias == [f"Encabezado o pie de página quitado (2 de 4 páginas): «{PIE}»."]


def test_repetido_en_menos_de_la_mitad_se_conserva():
    paginas = [f"Texto {letra}.\n{PIE}" if letra == "a" else f"Texto {letra}." for letra in "abc"]
    resultado = limpiar(paginas, con_paginas=True, maquetado=True)
    assert any(PIE in t for t in _textos(resultado)) and resultado.advertencias == []


def test_una_sola_pagina_o_sin_paginas_no_busca_encabezados():
    texto = "ACME SRS\nEl sistema debe guardar.\n7"
    assert _textos(limpiar([texto], con_paginas=True, maquetado=True)) == ["ACME SRS", "El sistema debe guardar."]
    # sin páginas reales tampoco se quitan números: quedan como fragmento visible
    assert _textos(limpiar([texto], con_paginas=False, maquetado=False))[-1] == "7"


def test_renglon_con_obligacion_o_marca_sola_no_es_encabezado():
    paginas = ["El sistema debe registrar la sesión.\nUno.", "El sistema debe registrar la sesión.\nDos.",
               "RF-01\nEl sistema debe tres.", "RF-01\nEl sistema debe cuatro."]
    resultado = limpiar(paginas, con_paginas=True, maquetado=False)
    assert resultado.advertencias == []
    assert _textos(resultado)[0] == "El sistema debe registrar la sesión."


def test_reconstruye_parrafo_y_une_palabra_cortada_con_guion():
    pagina = ("El sistema deberá autenti-\ncar al usuario con su contraseña y su\nnúmero de empleado antes de "
              "mostrar\nel menú.\nEl cajero podrá cerrar la caja.")
    parrafos = limpiar([pagina], con_paginas=True, maquetado=True).parrafos
    assert [p.texto for p in parrafos] == [
        "El sistema deberá autenticar al usuario con su contraseña y su número de empleado antes de mostrar el menú.",
        "El cajero podrá cerrar la caja."]
    assert parrafos[0].renglones[0] == "El sistema deberá autenti-"  # el original conserva el corte


def test_guion_ante_mayuscula_no_se_une():
    parrafos = limpiar(["El sistema debe enlazar ACME-\nNorte con la matriz."], con_paginas=False, maquetado=False).parrafos
    assert parrafos[0].texto == "El sistema debe enlazar ACME- Norte con la matriz."


def test_parrafo_que_cruza_de_pagina():
    paginas = ["Encabezado\nEl sistema debe conservar la bitácora de cambios de cada\n1\n\n",
               "\nEncabezado\nempleado durante cinco años.\n2\n"]
    parrafo, = limpiar(paginas, con_paginas=True, maquetado=True).parrafos
    assert parrafo.texto == "El sistema debe conservar la bitácora de cambios de cada empleado durante cinco años."
    assert (parrafo.pagina, parrafo.pagina_fin) == (1, 2)


def test_titulo_corto_cierra_parrafo():
    paginas = [("Requisitos de seguridad\nEl sistema deberá cifrar las contraseñas de los usuarios con un\n"
                "algoritmo reconocido.")]
    for maquetado in (True, False):
        assert _textos(limpiar(paginas, con_paginas=False, maquetado=maquetado)) == [
            "Requisitos de seguridad",
            "El sistema deberá cifrar las contraseñas de los usuarios con un algoritmo reconocido."]


def test_renglon_sin_punto_en_pdf_cierra_si_es_corto_y_sigue_si_esta_lleno():
    pagina = ("El sistema debe exportar el reporte mensual de ventas al formato que\n"
              "elija el gerente\n"
              "Cajeros y supervisores podrán enviar el corte de caja a la oficina\n"
              "SAT Juárez al cerrar el turno.")
    assert _textos(limpiar([pagina], con_paginas=False, maquetado=True)) == [
        "El sistema debe exportar el reporte mensual de ventas al formato que elija el gerente",
        "Cajeros y supervisores podrán enviar el corte de caja a la oficina SAT Juárez al cerrar el turno."]
    # en texto plano no hay ancho de referencia: sin punto final solo cierran un título
    # aislado o un renglón que abre oración («El», «La»…); «Cajeros» no la abre
    assert len(limpiar([pagina], con_paginas=False, maquetado=False).parrafos) == 1


def test_renglon_que_abre_oracion_cierra_el_anterior_sin_punto():
    """Requisitos uno por renglón y sin punto final: antes se pegaban en uno solo."""
    texto = ("El sistema debe guardar los datos del cliente\nEl sistema debe imprimir el ticket\n"
             "La aplicación podrá cancelar ventas\nCada cajero debe cerrar su turno")
    for maquetado in (True, False):
        assert _textos(limpiar([texto], con_paginas=False, maquetado=maquetado)) == [
            "El sistema debe guardar los datos del cliente", "El sistema debe imprimir el ticket",
            "La aplicación podrá cancelar ventas", "Cada cajero debe cerrar su turno"]
    # tras palabra de enlace sigue siendo la misma oración aunque empiece con «La»
    assert _textos(limpiar(["El sistema debe abrir una sucursal en\nLa Paz y otra en Mérida."], con_paginas=False,
                           maquetado=False)) == ["El sistema debe abrir una sucursal en La Paz y otra en Mérida."]


def test_renglon_que_termina_en_punto_cierra_parrafo():
    pagina = "RF-01 El sistema debe registrar la venta.\nEl sistema debe emitir el ticket.\nEl cajero podrá salir."
    for maquetado in (True, False):
        assert [p.marca for p in limpiar([pagina], con_paginas=False, maquetado=maquetado).parrafos] == [
            "RF-01", None, None]


def test_marca_sola_en_su_renglon_y_numero_que_continua_la_oracion():
    texto = "RF-07\nEl sistema debe ser compatible con la versión\n2.1 o superior del navegador.\nRF-08\nRF-09 Fin debe."
    parrafos = limpiar([texto], con_paginas=False, maquetado=False).parrafos
    assert [(p.marca, p.texto) for p in parrafos] == [
        ("RF-07", "El sistema debe ser compatible con la versión 2.1 o superior del navegador."),
        ("RF-08", ""), ("RF-09", "Fin debe.")]


def test_renglon_vacio_siempre_cierra_parrafo():
    assert _textos(limpiar(["El sistema debe\n\nguardar todo"], con_paginas=False, maquetado=False)) == [
        "El sistema debe", "guardar todo"]


def test_normaliza_ligaduras_y_caracteres_invisibles():
    assert normalizar_caracteres("\ufb01rma\u00ad digital\u200b\x07ok\u00a0ya") == "firma digital ok ya"
    assert normalizar_caracteres("\uf0b7 viñeta de Word") == "\uf0b7 viñeta de Word"


def test_encabezado_igual_al_pie_cuenta_paginas_no_renglones():
    resultado = limpiar(["ACME\nEl sistema debe guardar.\nACME", "ACME\nEl sistema debe salir.\nACME"],
                        con_paginas=True, maquetado=True)
    assert resultado.advertencias == ["Encabezado o pie de página quitado (2 de 2 páginas): «ACME»."]
    assert _textos(resultado) == ["El sistema debe guardar.", "El sistema debe salir."]


def test_titulo_con_identificador_arriba_de_cada_pagina_no_es_encabezado():
    """«RF-01 Registro de usuarios» y «RF-02 Registro de usuarios» son iguales salvo dígitos."""
    paginas = ["RF-01 Registro de usuarios\nEl administrador podrá dar de alta usuarios.",
               "RF-02 Registro de usuarios\nEl administrador podrá dar de baja usuarios."]
    resultado = limpiar(paginas, con_paginas=True, maquetado=True)
    assert resultado.advertencias == []
    assert [p.marca for p in resultado.parrafos] == ["RF-01", None, "RF-02", None]


def test_numero_tras_palabra_de_enlace_sigue_la_oracion_y_lista_numerada_no():
    texto = ("El servidor debe responder en un máximo de\n2.5 Segundos según la norma, como lo indica el\n"
             "RF-01 del anexo.\n1. registrar usuarios\n2. borrar usuarios")
    assert [(p.marca, p.texto) for p in limpiar([texto], con_paginas=False, maquetado=False).parrafos] == [
        (None, "El servidor debe responder en un máximo de 2.5 Segundos según la norma, como lo indica el RF-01 del anexo."),
        ("1", "registrar usuarios"), ("2", "borrar usuarios")]


def test_guion_suave_al_final_del_renglon_une_la_palabra():
    """Algunos PDF marcan el corte con U+00AD (byte 0xAD en WinAnsi): se quitaba y quedaba «autenti car»."""
    parrafo, = limpiar(["El sistema deberá autenti­\ncar al usuario con su con­traseña."], con_paginas=False,
                       maquetado=True).parrafos
    assert parrafo.texto == "El sistema deberá autenticar al usuario con su contraseña."


def test_fragmento_original_de_cada_oracion():
    parrafo, = limpiar(["RF-02 Uno debe ir. El sistema deberá autenti-\ncar al usuario. Tres\npuede salir."],
                       con_paginas=False, maquetado=False).parrafos
    assert parrafo.texto == "Uno debe ir. El sistema deberá autenticar al usuario. Tres puede salir."
    assert parrafo.fragmento(0, 12) == ("RF-02 Uno debe ir.", None, None)
    assert parrafo.fragmento(13, 53)[0] == "El sistema deberá autenti-\ncar al usuario."
    assert parrafo.fragmento(54, len(parrafo.texto))[0] == "Tres\npuede salir."
