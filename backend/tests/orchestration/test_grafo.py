"""Ruteo del grafo con LLMs y embeddings falsos (sin Ollama ni Mongo).

Los cuatro caminos que pide la fase: aceptado directo, consenso en la ronda 1,
arbitraje tras 2 rondas y vaguedad sin debate; más rechazo, edición humana,
error tras el reintento y reanudación con el checkpointer en SQLite.
"""
import json

import pytest

from app.models import Estado, Interpretacion, Validacion
from app.orchestration import ConflictoDeEstado, checkpointer_sqlite
from tests.escenarios import (
    EXTRACCION_SESION,
    I1,
    I2,
    MODELADO,
    P1_CERCANA,
    SESION,
    clasificacion,
    guiones_sesion_cercana,
    montar,
)
from tests.fakes import interp, r3_todas

def tipos(traza):
    return [m.tipo.value for m in traza.mensajes]


def ruta(traza):
    return [t.estado.value for t in traza.transiciones]


APROBAR = Validacion(decision="aprobar")


# ---------------------------------------------------------------- caminos

def test_camino_aceptado_directo(tmp_path, analizador):
    srv, llm, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
        "modelador_v2": [MODELADO],
    })
    req = srv.procesar(SESION)
    t = srv.traza(req)
    assert t.estado == Estado.PENDIENTE_VALIDACION
    sim = next(m for m in t.mensajes if m.tipo == "similitud")
    assert sim.payload["decision"] == "aceptado_directo"
    assert sim.payload["similitud"] >= 0.75 and sim.payload["umbral"] == 0.75
    assert "critico_v1" not in llm.llamadas

    srv.validar(req, APROBAR)
    t = srv.traza(req)
    assert ruta(t) == ["cargado", "extraido", "interpretado", "aceptado_directo", "pendiente_validacion",
                       "validado", "formalizado"]
    lel = repo.listar_lel()
    assert [(e.simbolo, e.via, e.interpretacion.id) for e in lel] == [("sesión", "aceptado_directo", "I1")]


def test_camino_consenso_en_ronda_1(tmp_path, analizador):
    srv, llm, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [{"interpretaciones": [I1],
                                          "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega servidor"}]}],
        "modelador_v2": [MODELADO],
    })
    req = srv.procesar(SESION)
    srv.validar(req, APROBAR)
    t = srv.traza(req)
    assert ruta(t) == ["cargado", "extraido", "interpretado", "en_debate", "consenso", "pendiente_validacion",
                       "validado", "formalizado"]
    assert tipos(t) == ["extraccion", "filtrado", "interpretaciones", "similitud", "objecion", "refinamiento",
                        "consenso", "solicitud_validacion", "validacion", "formalizacion", "formalizacion"]
    por_termino, por_requisito = [m.payload for m in t.mensajes if m.tipo == "formalizacion"]
    assert por_termino["alcance"] == "termino" and por_termino["entrada_lel"]["simbolo"] == "sesión"
    assert por_requisito["alcance"] == "requisito" and por_requisito["entradas_lel"] == ["sesión"]
    assert por_requisito["resoluciones"][0]["tipo_ambiguedad"] == "lexica" and por_requisito["metas"]
    consenso = next(m for m in t.mensajes if m.tipo == "consenso")
    assert consenso.ronda == 1 and consenso.payload["motivo"] == "una_interpretacion"
    assert repo.listar_lel()[0].via == "consenso"


def test_camino_consenso_por_umbral_tras_refinar(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [{"interpretaciones": [I1, interp("I2", "periodo de uso", P1_CERCANA)]}],
    })
    t = srv.traza(srv.procesar(SESION))
    sims = [m for m in t.mensajes if m.tipo == "similitud"]
    assert [m.ronda for m in sims] == [0, 1]
    assert sims[0].payload["decision"] == "en_debate" and sims[1].payload["decision"] == "consenso"
    assert next(m for m in t.mensajes if m.tipo == "consenso").payload["motivo"] == "umbral"
    assert t.estado == Estado.PENDIENTE_VALIDACION


def test_camino_arbitraje_tras_2_rondas(tmp_path, analizador):
    sin_cambios = {"interpretaciones": [I1, I2]}
    srv, llm, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v2": [{"interpretacion_elegida": "I2", "justificacion_por_regla": [
            {"regla": r, "argumento": f"argumento {r}"} for r in ("R1", "R2", "R3")]}],
        "modelador_v2": [MODELADO],
    })
    req = srv.procesar(SESION)
    t = srv.traza(req)
    assert ruta(t) == ["cargado", "extraido", "interpretado", "en_debate", "en_debate", "arbitrado",
                       "pendiente_validacion"]
    assert len(llm.llamadas["critico_v1"]) == 2 and len(llm.llamadas["clasificador_refinamiento_v1"]) == 2
    arb = next(m for m in t.mensajes if m.tipo == "arbitraje")
    assert arb.ronda == 2 and arb.payload["interpretacion_elegida"] == "I2"
    assert [j["regla"] for j in arb.payload["justificacion_por_regla"]] == ["R1", "R2", "R3"]
    solicitud = next(m for m in t.mensajes if m.tipo == "solicitud_validacion").payload
    assert solicitud["terminos"][0]["propuesta"]["id"] == "I2" and solicitud["terminos"][0]["rondas"] == 2

    srv.validar(req, APROBAR)
    assert repo.listar_lel()[0].via == "arbitraje"
    assert repo.listar_lel()[0].interpretacion.id == "I2"


def test_camino_vaguedad_sin_debate(tmp_path, analizador):
    srv, llm, repo = montar(tmp_path, analizador, {
        "extractor_v1": [{"terminos": [{"termino": "sistema", "categoria_tentativa": "sujeto"},
                                       {"termino": "responder", "categoria_tentativa": "verbo"},
                                       {"termino": "ahorita", "categoria_tentativa": "estado"}]}],
        "clasificador_v3": [{"resultados": [{"termino": "sistema", "univoco": True},
                                            {"termino": "responder", "univoco": True}]}],
    })
    req = srv.procesar("El sistema debe responder ahorita.")
    t = srv.traza(req)
    filtrado = next(m for m in t.mensajes if m.tipo == "filtrado").payload["terminos"]
    assert {f["termino"]: f["decision_filtro"] for f in filtrado}["ahorita"] == "vaguedad"
    candidatos = llm.llamadas["clasificador_v3"][0].usuario.split("Términos candidatos:")[1].split("LEL")[0]
    assert "sistema" in candidatos and "ahorita" not in candidatos
    assert "critico_v1" not in llm.llamadas
    sim = next(m for m in t.mensajes if m.tipo == "similitud").payload
    assert sim["similitud"] is None and sim["motivo"] == "sin_interpretaciones"
    assert next(m for m in t.mensajes if m.tipo == "solicitud_validacion").payload["vaguedad"] == ["ahorita"]

    srv.validar(req, APROBAR)
    t = srv.traza(req)
    assert ruta(t)[-4:] == ["aceptado_directo", "pendiente_validacion", "validado", "formalizado"]
    formalizacion = next(m for m in t.mensajes if m.tipo == "formalizacion").payload
    assert formalizacion["entradas_lel"] == [] and formalizacion["univocos"] == ["sistema", "responder"]
    assert formalizacion["vaguedad"] == ["ahorita"] and formalizacion["requisito_reescrito"]
    assert repo.listar_lel() == []  # los unívocos no entran al LEL (ADR 0007)


# ---------------------------------------------------------------- validación humana

def test_rechazo_termina_sin_formalizar(tmp_path, analizador):
    srv, llm, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
    })
    req = srv.procesar(SESION)
    srv.validar(req, Validacion(decision="rechazar", comentario="no es lo que pedí"))
    t = srv.traza(req)
    assert t.estado == Estado.RECHAZADO and ruta(t)[-1] == "rechazado"
    assert tipos(t)[-1] == "validacion" and t.mensajes[-1].payload["comentario"] == "no es lo que pedí"
    assert "modelador_v2" not in llm.llamadas and repo.listar_lel() == []


def test_el_humano_elige_otra_interpretacion(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, guiones_sesion_cercana())
    req = srv.procesar(SESION)
    srv.validar(req, Validacion(decision="aprobar", interpretaciones_editadas={
        "sesión": Interpretacion(**interp("I2", "periodo de uso", P1_CERCANA))}))
    val = next(m for m in srv.traza(req).mensajes if m.tipo == "validacion").payload["terminos"][0]
    assert val["cambio"] == "eleccion" and val["final"]["id"] == "I2"
    assert repo.listar_lel()[0].interpretacion.id == "I2" and not repo.listar_lel()[0].editada_por_humano


def test_el_humano_edita_la_interpretacion(tmp_path, analizador):
    srv, llm, repo = montar(tmp_path, analizador, guiones_sesion_cercana())
    req = srv.procesar(SESION)
    editada = Interpretacion(id="I1", significado="periodo autenticado", parafrasis_del_requisito="Otra paráfrasis.")
    srv.validar(req, Validacion(decision="aprobar", interpretaciones_editadas={"sesión": editada}))
    entrada = repo.listar_lel()[0]
    assert entrada.editada_por_humano and entrada.interpretacion.significado == "periodo autenticado"
    assert "periodo autenticado" in llm.llamadas["modelador_v2"][0].usuario


def test_el_lel_es_memoria_el_termino_no_se_vuelve_a_debatir(tmp_path, analizador):
    guiones = guiones_sesion_cercana()
    guiones["extractor_v1"].append(EXTRACCION_SESION)
    guiones["clasificador_v3"].append({"resultados": [{"termino": "sistema", "univoco": True},
                                                      {"termino": "registrar", "univoco": True}]})
    srv, llm, _ = montar(tmp_path, analizador, guiones)
    srv.validar(srv.procesar(SESION), APROBAR)

    t = srv.traza(srv.procesar(SESION))
    filtrado = next(m for m in t.mensajes if m.tipo == "filtrado").payload["terminos"]
    sesion = next(f for f in filtrado if f["termino"] == "sesión")
    assert sesion["decision_filtro"] == "resuelto_por_lel"
    assert '"sesión"' in llm.llamadas["clasificador_v3"][1].usuario.split("LEL acumulado")[1]  # va como contexto
    assert ruta(t)[-2:] == ["aceptado_directo", "pendiente_validacion"]


def test_validar_fuera_de_turno_o_con_termino_desconocido(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
        "modelador_v2": [MODELADO],
    })
    req = srv.procesar(SESION)
    with pytest.raises(ValueError, match="sistema"):
        srv.validar(req, Validacion(decision="aprobar", interpretaciones_editadas={
            "sistema": Interpretacion(**I1)}))
    srv.validar(req, APROBAR)
    with pytest.raises(ConflictoDeEstado):
        srv.validar(req, APROBAR)


# ---------------------------------------------------------------- error y reanudación

def test_salida_invalida_dos_veces_termina_en_error(tmp_path, analizador):
    srv, llm, _ = montar(tmp_path, analizador, {
        "extractor_v1": ["no es json", {"terminos": [{"termino": "sesión", "categoria_tentativa": "otra"}]}],
    })
    t = srv.traza(srv.procesar(SESION))
    assert t.estado == Estado.ERROR and ruta(t) == ["cargado", "error"]
    err = t.mensajes[-1]
    assert err.tipo == "error" and err.emisor == "extractor" and err.prompt_version == "extractor_v1"
    assert [i["salida_cruda"] for i in err.payload["intentos"]][0] == "no es json"
    assert len(llm.llamadas["extractor_v1"]) == 2


def test_reintento_exitoso_queda_en_la_traza(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": ["{roto", EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
    })
    t = srv.traza(srv.procesar(SESION))
    ext = t.mensajes[0].payload
    assert ext["intentos"] == 2 and ext["intentos_fallidos"][0]["salida_cruda"] == "{roto"


def test_reanuda_despues_de_reiniciar_con_sqlite(tmp_path, analizador):
    guiones = {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
        "modelador_v2": [MODELADO],
    }
    srv, _, _ = montar(tmp_path, analizador, guiones, checkpointer=checkpointer_sqlite(tmp_path / "cp.sqlite"))
    req = srv.procesar(SESION)
    # "reinicio": servicio y checkpointer nuevos sobre los mismos archivos
    srv2, _, repo2 = montar(tmp_path, analizador, guiones, checkpointer=checkpointer_sqlite(tmp_path / "cp.sqlite"))
    srv2.validar(req, APROBAR)
    assert srv2.traza(req).estado == Estado.FORMALIZADO and len(repo2.listar_lel()) == 1


# ---------------------------------------------------------------- traza y estructura

def test_la_traza_se_reconstruye_desde_el_json(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [{"interpretaciones": [I1],
                                          "retiradas": [{"interpretacion_id": "I2", "motivo": "x"}]}],
        "modelador_v2": [MODELADO],
    })
    req = srv.procesar(SESION)
    srv.validar(req, APROBAR)
    crudo = json.loads((tmp_path / "resultados" / "trazas" / f"{req}.json").read_text(encoding="utf-8"))
    assert crudo["req_id"] == req == "R01" and crudo["texto"] == SESION
    assert [m["secuencia"] for m in crudo["mensajes"]] == list(range(1, len(crudo["mensajes"]) + 1))
    assert crudo["config"]["similarity_threshold"] == 0.75 and "catalogos" in crudo["config"]
    for m in crudo["mensajes"]:
        assert set(m) == {"req_id", "secuencia", "ronda", "emisor", "receptor", "tipo", "payload", "modelo",
                          "prompt_version", "timestamp"}
    con_llm = [m for m in crudo["mensajes"] if m["tipo"] in ("extraccion", "interpretaciones", "objecion")]
    assert all(m["modelo"] == "llm-falso" and m["prompt_version"] for m in con_llm)
    # cada transición apunta al último mensaje previo
    assert [t["estado"] for t in crudo["transiciones"]][-1] == "formalizado"
    assert crudo["transiciones"][-1]["secuencia"] == len(crudo["mensajes"])


def test_los_nodos_del_grafo_son_los_estados_mas_las_dos_validaciones(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {})
    nodos = set(srv.grafo.get_graph().nodes) - {"__start__", "__end__"}
    assert nodos == {e.value for e in Estado} | {"humano", "validacion_automatica"}


def test_anafora_se_resuelve_en_el_requisito_y_no_entra_al_lel(tmp_path, analizador):
    texto = "El administrador debe notificar al usuario cuando su cuenta expire."
    pa = "El administrador debe notificar al usuario cuando la cuenta del administrador expire."
    pu = "El administrador debe notificar al usuario cuando la cuenta del usuario expire."
    # pa y pu no tienen vector propio: similitud 1.0 → aceptado directo, se propone I1
    reescrito = {"requisito_reescrito": pa, "tipo_requisito": "funcional", "metas": [
        {"id": "M1", "enunciado": "Notificar la expiración de la cuenta", "tipo": "meta", "actor": "administrador"}]}
    srv, llm, repo = montar(tmp_path, analizador, {
        "extractor_v1": [{"terminos": [{"termino": "administrador", "categoria_tentativa": "sujeto"},
                                       {"termino": "usuario", "categoria_tentativa": "sujeto"}]}],
        "clasificador_v3": [{"resultados": [
            {"termino": "administrador", "univoco": True}, {"termino": "usuario", "univoco": True},
            {"termino": "su cuenta", "tipo_ambiguedad": "anaforica", "interpretaciones": [
                interp("I1", "la cuenta del administrador", pa), interp("I2", "la cuenta del usuario", pu)]}]}],
        "modelador_requisito_v2": [reescrito],
    })
    req = srv.procesar(texto)
    t = srv.traza(req)
    filtrado = next(m for m in t.mensajes if m.tipo == "filtrado").payload["terminos"]
    assert {"termino": "su cuenta", "decision_filtro": "anafora"}.items() <= next(
        f for f in filtrado if f["termino"] == "su cuenta").items()
    candidatos = llm.llamadas["clasificador_v3"][0].usuario.split("Términos candidatos:")[1].split("LEL")[0]
    assert '"origen": "anafora"' in candidatos and "administrador, usuario" in candidatos
    solicitud = next(m for m in t.mensajes if m.tipo == "solicitud_validacion").payload
    assert solicitud["terminos"][0]["tipo_ambiguedad"] == "anaforica"
    assert solicitud["estructuras"][0]["decision_filtro"] == "anafora"

    srv.validar(req, Validacion(decision="aprobar"))
    assert repo.listar_lel() == [] and "modelador_v2" not in llm.llamadas  # la anáfora no es vocabulario
    final = [m.payload for m in srv.traza(req).mensajes if m.tipo == "formalizacion"]
    assert len(final) == 1 and final[0]["requisito_reescrito"] == pa
    assert final[0]["resoluciones"][0]["interpretacion"]["id"] == "I1"
    assert "la cuenta del administrador" in llm.llamadas["modelador_requisito_v2"][0].usuario
    assert final[0]["resoluciones"][0]["tipo_ambiguedad"] == "anaforica"
    assert repo.obtener_doc("formalizados", req)["metas"][0]["actor"] == "administrador"


# ---------------------------------------------------------------- validación solo cuando hace falta (ADR 0017)

def _arbitraje():
    sin_cambios = {"interpretaciones": [I1, I2]}
    return {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v2": [{"interpretacion_elegida": "I2", "justificacion_por_regla": [
            {"regla": r, "argumento": "x"} for r in ("R1", "R2", "R3")]}],
        "modelador_v2": [MODELADO],
    }


def test_sin_arbitraje_se_formaliza_sin_esperar_a_una_persona(tmp_path, analizador):
    srv, llm, repo = montar(tmp_path, analizador, guiones_sesion_cercana(), validacion_humana="si_hay_arbitraje")
    req = srv.procesar(SESION)
    t = srv.traza(req)
    assert ruta(t) == ["cargado", "extraido", "interpretado", "aceptado_directo", "validado", "formalizado"]
    assert "solicitud_validacion" not in tipos(t)
    v = next(m for m in t.mensajes if m.tipo == "validacion")
    assert (v.emisor, v.receptor) == ("sistema", "modelador")
    assert v.payload["automatica"] is True and v.payload["motivo"] == "sin_arbitraje"
    assert v.payload["terminos"][0]["cambio"] == "ninguno" and v.payload["terminos"][0]["final"]["id"] == "I1"
    assert [(e.simbolo, e.cambio) for e in repo.listar_lel()] == [("sesión", "ninguno")]
    doc = repo.obtener_doc("formalizados", req)
    assert (doc["tipo_requisito"], doc["categoria"], doc["supuestos"]) == ("funcional", None, [])
    assert t.config["validacion_humana"] == "si_hay_arbitraje"


def test_sin_terminos_ambiguos_se_formaliza_solo(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [{"terminos": [{"termino": "sistema", "categoria_tentativa": "sujeto"}]}],
        "clasificador_v3": [{"resultados": [{"termino": "sistema", "univoco": True}]}],
    }, validacion_humana="si_hay_arbitraje")
    t = srv.traza(srv.procesar(SESION))
    assert t.estado == Estado.FORMALIZADO
    assert next(m for m in t.mensajes if m.tipo == "validacion").payload["motivo"] == "sin_ambiguedad"


def test_con_arbitraje_espera_a_una_persona(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, _arbitraje(), validacion_humana="si_hay_arbitraje")
    req = srv.procesar(SESION)
    assert ruta(srv.traza(req))[-2:] == ["arbitrado", "pendiente_validacion"]
    srv.validar(req, Validacion(decision="aprobar", interpretaciones_editadas={"sesión": Interpretacion(**I1)}))
    t = srv.traza(req)
    assert t.estado == Estado.FORMALIZADO
    v = next(m for m in t.mensajes if m.tipo == "validacion")
    assert v.emisor == "humano" and "automatica" not in v.payload
    assert repo.listar_lel()[0].interpretacion.id == "I1"


def test_validacion_desactivada_aprueba_incluso_el_arbitraje(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, _arbitraje(), validacion_humana="nunca")
    t = srv.traza(srv.procesar(SESION))
    assert ruta(t)[-3:] == ["arbitrado", "validado", "formalizado"]
    assert next(m for m in t.mensajes if m.tipo == "validacion").payload["motivo"] == "validacion_desactivada"
    assert repo.listar_lel()[0].via == "arbitraje" and repo.listar_lel()[0].interpretacion.id == "I2"


def test_un_proyecto_de_evaluacion_siempre_se_detiene_antes_de_validar(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, guiones_sesion_cercana(), validacion_humana="nunca")
    p = srv.proyectos.crear("Corrida", tipo="evaluacion")
    assert srv.traza(srv.procesar(SESION, p.proyecto_id)).estado == Estado.PENDIENTE_VALIDACION


def test_el_contexto_del_proyecto_llega_a_los_agentes_y_queda_en_la_traza(tmp_path, analizador):
    contexto = "Punto de venta de una ferretería en Ciudad Juárez; lo usan cajeros y el encargado."
    dos_veces = {k: v * 2 for k, v in guiones_sesion_cercana().items()}
    srv, llm, _ = montar(tmp_path, analizador, dos_veces, validacion_humana="si_hay_arbitraje")
    p = srv.proyectos.crear("Ferretería", contexto=contexto)
    req = srv.procesar(SESION, p.proyecto_id)
    # se copia al cargar: cambiarlo después no altera lo que ya se procesó
    srv.proyectos.actualizar(p.proyecto_id, contexto="otro")
    assert srv.traza(req).config["contexto_proyecto"] == contexto
    for version in ("clasificador_v3", "modelador_v2", "modelador_requisito_v2"):
        assert contexto in llm.llamadas[version][0].usuario, version
    sin = srv.procesar(SESION)  # el proyecto General no tiene contexto
    assert srv.traza(sin).config["contexto_proyecto"] is None
    assert "(el proyecto no tiene contexto general)" in llm.llamadas["clasificador_v3"][1].usuario
