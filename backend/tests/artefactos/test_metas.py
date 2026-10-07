"""Modelo de metas del proyecto: ids globales, actores normalizados, conteos y
expresiones vagas candidatas a metas blandas (funciones puras, sin LLM)."""
import random

from app.artefactos import artefactos_requisito, formas, metas_proyecto, seleccionar
from app.artefactos.terminos import (
    Comparador,
    nombre_actor,
    separar_accion,
    sin_articulo,
)
from tests.artefactos.ayudantes import (
    documentos,
    formalizado,
    lel,
    meta,
    resumen,
    trazas,
)


def _metas(analizador=None):
    m = metas_proyecto(documentos(), lel(), trazas(), analizador)
    formas.MetasProyecto.model_validate(m)
    return m


def test_ids_globales_y_contribuciones():
    m = _metas()
    assert [x["id"] for x in m["metas"]] == ["R01.M1", "R01.M2", "R02.M1", "R02.M2", "R03.M1", "R03.M2", "R03.M3"]
    assert {x["id"]: x["contribuye_a"] for x in m["metas"]} == {
        "R01.M1": None, "R01.M2": "R01.M1", "R02.M1": None, "R02.M2": "R02.M1",
        "R03.M1": "R03.M3", "R03.M2": "R03.M1", "R03.M3": None}
    r01m2 = m["metas"][1]
    assert r01m2 == {"id": "R01.M2", "req_id": "R01", "enunciado": "Guardar la hora de inicio y de cierre",
                     "tipo": "tarea", "actor": "sistema", "actor_original": "sistema",
                     "simbolos": ["sesión", "hora de inicio"], "contribuye_a": "R01.M1"}


def test_actores_normalizados_sin_spacy():
    m = _metas()
    assert m["actores"] == [
        {"nombre": "administrador", "simbolo_lel": None, "metas": ["R03.M1", "R03.M3"]},
        {"nombre": "sistema", "simbolo_lel": None, "metas": ["R01.M1", "R01.M2"]},
        # sujeto del LEL: aparece aunque ninguna meta lo nombre así
        {"nombre": "usuario", "simbolo_lel": "usuario", "metas": []},
        # sin lemas, «Los Usuarios» no es «usuario»
        {"nombre": "usuarios", "simbolo_lel": None, "metas": ["R02.M1"]},
    ]
    actores = {x["id"]: (x["actor"], x["actor_original"]) for x in m["metas"]}
    assert actores["R01.M1"] == ("sistema", "El sistema")
    assert actores["R03.M3"] == ("administrador", "el administrador")
    assert actores["R02.M1"] == ("usuarios", "Los Usuarios")


def test_actores_con_lemas_se_unen_al_sujeto_del_lel(analizador):
    m = _metas(analizador)
    assert [(a["nombre"], a["simbolo_lel"], a["metas"]) for a in m["actores"]] == [
        ("administrador", None, ["R03.M1", "R03.M3"]),
        ("sistema", None, ["R01.M1", "R01.M2"]),
        ("usuario", "usuario", ["R02.M1"]),
    ]
    assert next(x for x in m["metas"] if x["id"] == "R02.M1")["actor"] == "usuario"


def test_conteos_vaguedad_y_sin_actor():
    m = _metas()
    assert m["por_tipo"] == {"meta": 3, "meta_blanda": 1, "tarea": 2, "recurso": 1}
    assert m["sin_actor"] == ["R02.M2", "R03.M2"]
    assert m["metas_blandas_desde_vaguedad"] == [
        {"texto": "ahorita", "req_id": "R02", "meta_blanda": "R02.M2"},
        {"texto": "rápido", "req_id": "R03", "meta_blanda": None},
    ]


def test_requisitos_fuera_con_su_motivo():
    assert _metas()["requisitos_fuera"] == [
        {"req_id": "R04", "estado": "en_debate", "motivo": "en_proceso", "detalle": None},
        {"req_id": "R05", "estado": "rechazado", "motivo": "rechazado", "detalle": None},
        {"req_id": "R06", "estado": "formalizado", "motivo": "reprocesado", "detalle": "lo vuelve a procesar R07"},
        {"req_id": "R07", "estado": "pendiente_validacion", "motivo": "en_proceso", "detalle": None},
        {"req_id": "R08", "estado": "formalizado", "motivo": "sin_formalizacion",
         "detalle": "formalizado antes del documento por requisito (ADR 0010)"},
        {"req_id": "R09", "estado": None, "motivo": "sin_traza", "detalle": None},
    ]


def test_un_reproceso_fallido_no_saca_al_original():
    docs = [formalizado("R01", "El sistema debe imprimir.", [meta("M1", "Imprimir el reporte")])]
    dentro, fuera = seleccionar(docs, [resumen("R01", "formalizado"), resumen("R02", "error", "R01")])
    assert [d["req_id"] for d in dentro] == ["R01"]
    assert fuera == [{"req_id": "R02", "estado": "error", "motivo": "error", "detalle": None}]


def test_sin_trazas_entran_todos_los_documentos():
    m = metas_proyecto(documentos(), lel())
    assert sorted({x["req_id"] for x in m["metas"]}) == ["R01", "R02", "R03", "R06", "R09"]
    assert m["requisitos_fuera"] == []


def test_proyecto_vacio():
    m = metas_proyecto([], [], [])
    assert m == {"metas": [], "actores": [], "por_tipo": {"meta": 0, "meta_blanda": 0, "tarea": 0, "recurso": 0},
                 "metas_blandas_desde_vaguedad": [], "sin_actor": [], "requisitos_fuera": []}
    formas.MetasProyecto.model_validate(m)


def test_no_depende_del_orden_de_entrada():
    docs, entradas, resumenes = documentos(), lel(), trazas()
    random.Random(7).shuffle(docs)
    random.Random(7).shuffle(entradas)
    random.Random(7).shuffle(resumenes)
    assert metas_proyecto(docs, entradas, resumenes) == _metas()


def test_contribuye_a_invalido_no_se_inventa():
    d = formalizado("R01", "x", [meta("M1", "Registrar x", contribuye_a="M9"), meta("M2", "Leer y", contribuye_a="M2")])
    assert [x["contribuye_a"] for x in metas_proyecto([d], [])["metas"]] == [None, None]


def test_artefactos_de_un_requisito():
    a = artefactos_requisito("R02", "P01", "formalizado", documentos()[1], lel())
    formas.ArtefactosRequisito.model_validate(a)
    assert a["formalizado"] == documentos()[1]
    assert [e["simbolo"] for e in a["entradas_lel"]] == ["usuario", "bitácora"]
    assert [(x["id"], x["actor"]) for x in a["metas"]] == [("R02.M1", "usuarios"), ("R02.M2", None)]
    sin = artefactos_requisito("R04", "P01", "en_debate", None, lel())
    assert (sin["formalizado"], sin["entradas_lel"], sin["metas"]) == (None, [], [])


def test_utilidades_de_texto(analizador):
    assert sin_articulo("  Los   usuarios ") == "usuarios"
    assert [nombre_actor(x) for x in ("El Usuario", "SAT", "la Secretaría de Salud", "sistema")] == [
        "usuario", "SAT", "secretaría de Salud", "sistema"]
    assert separar_accion("Registrar el periodo de uso.") == ("registrar", "el periodo de uso")
    assert separar_accion("Darse de alta") == ("darse", "de alta")
    assert separar_accion("Que el cliente quede registrado") == (None, "Que el cliente quede registrado")
    # la puntuación pegada al verbo no le quita la forma de infinitivo
    assert separar_accion("Registrar, guardar y enviar el reporte") == ("registrar", "guardar y enviar el reporte")
    assert separar_accion("Registrar: la sesión.") == ("registrar", "la sesión")
    plano, lemas = Comparador(), Comparador(analizador)
    assert plano.aparece("sesión", "El sistema registra la SESION.") and not plano.aparece("sesión", "sesiones")
    assert lemas.aparece("sesión", "Cierra las sesiones abiertas.")
    assert lemas.aparece("dar de alta", "El administrador da de alta al cliente.")
    assert not plano.aparece("dar de alta", "El administrador da de alta al cliente.")
    assert not plano.aparece("alta", "altamente") and not plano.aparece("", "algo")
    assert lemas.mismo("usuarios", "usuario") and not plano.mismo("usuarios", "usuario")


def test_documento_mal_formado_no_rompe_los_ids():
    d = formalizado("R01", "x", [meta("M1", "Registrar x", simbolos=["sesión", " ", "sesión"]),
                                 meta("M1", "Repetida"), {"enunciado": "sin id", "tipo": "meta"}])
    m = metas_proyecto([d], [])
    assert [(x["id"], x["enunciado"], x["simbolos"]) for x in m["metas"]] == [("R01.M1", "Registrar x", ["sesión"])]


def test_reproceso_en_cadena_pasa_por_la_version_que_fallo():
    # R02 vuelve a procesar R01 y falla; R03 vuelve a procesar R02 y llega: R01 ya no es vigente
    docs = [formalizado(r, "El sistema debe imprimir.", [meta("M1", "Imprimir el reporte")]) for r in ("R01", "R03")]
    resumenes = [resumen("R01", "formalizado"), resumen("R02", "error", "R01"), resumen("R03", "formalizado", "R02")]
    dentro, fuera = seleccionar(docs, resumenes)
    assert [d["req_id"] for d in dentro] == ["R03"]
    assert fuera == [
        {"req_id": "R01", "estado": "formalizado", "motivo": "reprocesado", "detalle": "lo vuelve a procesar R03"},
        {"req_id": "R02", "estado": "error", "motivo": "error", "detalle": None},
    ]
    assert [x["id"] for x in metas_proyecto(docs, [], resumenes)["metas"]] == ["R03.M1"]


def test_reproceso_en_cadena_nombra_la_version_mas_nueva():
    docs = [formalizado(r, "x", [meta("M1", "Imprimir el reporte")]) for r in ("R01", "R02")]
    resumenes = [resumen("R01", "formalizado"), resumen("R02", "formalizado", "R01"),
                 resumen("R03", "pendiente_validacion", "R02")]
    dentro, fuera = seleccionar(docs, resumenes)
    assert dentro == []
    assert [(f["req_id"], f["motivo"], f["detalle"]) for f in fuera] == [
        ("R01", "reprocesado", "lo vuelve a procesar R03"), ("R02", "reprocesado", "lo vuelve a procesar R03"),
        ("R03", "en_proceso", None)]


def test_reproceso_a_si_mismo_o_circular_no_deja_fuera_a_todos():
    docs = [formalizado(r, "x", [meta("M1", "Imprimir el reporte")]) for r in ("R01", "R03")]
    dentro, fuera = seleccionar(docs[:1], [resumen("R01", "formalizado", "R01")])
    assert ([d["req_id"] for d in dentro], fuera) == (["R01"], [])
    # solo una versión más nueva sustituye a otra: R03 queda y R01 sale
    dentro, fuera = seleccionar(docs, [resumen("R01", "formalizado", "R03"), resumen("R03", "formalizado", "R01")])
    assert [d["req_id"] for d in dentro] == ["R03"]
    assert [(f["req_id"], f["motivo"]) for f in fuera] == [("R01", "reprocesado")]


def test_actores_con_la_misma_clave_son_un_solo_grupo():
    # «—» no tiene palabras que comparar y «el el sistema» no es «sistema»: sin unirlos por
    # clave habría dos nodos con el mismo id
    from tests.artefactos.ayudantes import entrada

    docs = [formalizado("R01", "x", [meta("M1", "Imprimir el reporte", actor="—"), meta("M2", "Guardar", actor="—"),
                                     meta("M3", "Leer", actor="el el sistema")]),
            formalizado("R02", "x", [meta("M1", "Leer el reporte", actor="—")])]
    sujeto = [entrada("El sistema", "sujeto", ["El software."], ["Registra."], "R01")]
    m = metas_proyecto(docs, sujeto)
    assert [(a["nombre"], a["simbolo_lel"], a["metas"]) for a in m["actores"]] == [
        ("El sistema", "El sistema", ["R01.M3"]), ("—", None, ["R01.M1", "R01.M2", "R02.M1"])]


def test_artefactos_de_un_requisito_nombran_al_actor_como_el_proyecto(analizador):
    docs = [formalizado("R01", "Los usuarios consultan.", [meta("M1", "Consultar el saldo", actor="Los usuarios")]),
            formalizado("R02", "El usuario paga.", [meta("M1", "Pagar el saldo", actor="El usuario")])]
    resumenes = [resumen("R01", "formalizado"), resumen("R02", "formalizado")]
    proyecto = {x["id"]: x["actor"] for x in metas_proyecto(docs, [], resumenes, analizador)["metas"]}
    assert proyecto == {"R01.M1": "usuarios", "R02.M1": "usuarios"}
    a = artefactos_requisito("R02", "P01", "formalizado", docs[1], [], analizador, docs, resumenes)
    assert [(x["id"], x["actor"], x["actor_original"]) for x in a["metas"]] == [("R02.M1", "usuarios", "El usuario")]
    # sin el proyecto, el requisito solo se ve a sí mismo
    solo = artefactos_requisito("R02", "P01", "formalizado", docs[1], [], analizador)
    assert [x["actor"] for x in solo["metas"]] == ["usuario"]
    # sin spaCy también: «SISTEMA» (escrito como sigla) es el «sistema» de R01
    docs = [formalizado("R01", "x", [meta("M1", "Imprimir", actor="El sistema")]),
            formalizado("R02", "x", [meta("M1", "Guardar", actor="SISTEMA")])]
    a = artefactos_requisito("R02", "P01", "formalizado", docs[1], [], None, docs, resumenes)
    assert [x["actor"] for x in a["metas"]] == ["sistema"]


def test_meta_de_tipo_desconocido_o_sin_enunciado_se_omite():
    from app.artefactos import big_picture_proyecto

    d = formalizado("R01", "x", [meta("M1", "Registrar x"), meta("M2", "Lograr y", "objetivo"),
                                 {"id": "M3", "enunciado": None, "tipo": "meta"}, "no es meta"])
    m = metas_proyecto([d], [])
    formas.MetasProyecto.model_validate(m)
    assert [x["id"] for x in m["metas"]] == ["R01.M1"]
    bp = big_picture_proyecto([d], [], None)
    formas.BigPicture.model_validate(bp)
    assert [n["id"] for n in bp["nodos"]] == ["R01", "R01.M1"]


def test_contribucion_que_cierra_un_ciclo_se_omite():
    # el contrato del Modelador acepta M1→M2→M1; sin cortarlo, ninguna de las dos sería raíz
    # del árbol de metas y la pantalla no las mostraría
    from app.models.contratos import SalidaModeladorRequisito

    ciclo = [meta("M1", "Registrar a", contribuye_a="M2"), meta("M2", "Guardar b", "tarea", contribuye_a="M1")]
    SalidaModeladorRequisito.model_validate({"requisito_reescrito": "x", "metas": ciclo})
    triangulo = [meta("M1", "Registrar a", contribuye_a="M3"), meta("M2", "Guardar b", contribuye_a="M1"),
                 meta("M3", "Leer c", contribuye_a="M2"), meta("M4", "Enviar d", contribuye_a="M2")]
    m = metas_proyecto([formalizado("R01", "x", ciclo), formalizado("R02", "x", triangulo)], [])
    contribuye = {x["id"]: x["contribuye_a"] for x in m["metas"]}
    assert contribuye == {"R01.M1": "R01.M2", "R01.M2": None,
                          "R02.M1": "R02.M3", "R02.M2": "R02.M1", "R02.M3": None, "R02.M4": "R02.M2"}
    for mid in contribuye:  # cada meta llega a una raíz
        vistos = set()
        while mid is not None:
            assert mid not in vistos
            vistos.add(mid)
            mid = contribuye[mid]


def test_versiones_anteriores_de_un_requisito():
    from app.artefactos.seleccion import versiones_anteriores

    resumenes = [resumen("R01", "formalizado"), resumen("R02", "error", "R01"), resumen("R03", "formalizado", "R02"),
                 resumen("R04", "formalizado", "R04"), resumen("R05", "formalizado", "R06"),
                 resumen("R06", "formalizado", "R05")]
    assert versiones_anteriores(resumenes) == {"R02": {"R01"}, "R03": {"R01", "R02"}, "R04": set(), "R05": set(),
                                               "R06": {"R05"}}
    assert versiones_anteriores(None) == {}
