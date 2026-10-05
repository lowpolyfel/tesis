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
        "clasificador_v1": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
        "modelador_v1": [MODELADO],
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
        "clasificador_v1": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [{"interpretaciones": [I1],
                                          "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega servidor"}]}],
        "modelador_v1": [MODELADO],
    })
    req = srv.procesar(SESION)
    srv.validar(req, APROBAR)
    t = srv.traza(req)
    assert ruta(t) == ["cargado", "extraido", "interpretado", "en_debate", "consenso", "pendiente_validacion",
                       "validado", "formalizado"]
    assert tipos(t) == ["extraccion", "filtrado", "interpretaciones", "similitud", "objecion", "refinamiento",
                        "consenso", "solicitud_validacion", "validacion", "formalizacion"]
    consenso = next(m for m in t.mensajes if m.tipo == "consenso")
    assert consenso.ronda == 1 and consenso.payload["motivo"] == "una_interpretacion"
    assert repo.listar_lel()[0].via == "consenso"


def test_camino_consenso_por_umbral_tras_refinar(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v1": [clasificacion(I1, I2)],
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
        "clasificador_v1": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v1": [{"interpretacion_elegida": "I2", "justificacion_por_regla": [
            {"regla": r, "argumento": f"argumento {r}"} for r in ("R1", "R2", "R3")]}],
        "modelador_v1": [MODELADO],
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
        "clasificador_v1": [{"resultados": [{"termino": "sistema", "univoco": True},
                                            {"termino": "responder", "univoco": True}]}],
    })
    req = srv.procesar("El sistema debe responder ahorita.")
    t = srv.traza(req)
    filtrado = next(m for m in t.mensajes if m.tipo == "filtrado").payload["terminos"]
    assert {f["termino"]: f["decision_filtro"] for f in filtrado}["ahorita"] == "vaguedad"
    candidatos = llm.llamadas["clasificador_v1"][0].usuario.split("Términos candidatos:")[1].split("LEL")[0]
    assert "sistema" in candidatos and "ahorita" not in candidatos
    assert "critico_v1" not in llm.llamadas
    sim = next(m for m in t.mensajes if m.tipo == "similitud").payload
    assert sim["similitud"] is None and sim["motivo"] == "sin_interpretaciones"
    assert next(m for m in t.mensajes if m.tipo == "solicitud_validacion").payload["vaguedad"] == ["ahorita"]

    srv.validar(req, APROBAR)
    t = srv.traza(req)
    assert ruta(t)[-4:] == ["aceptado_directo", "pendiente_validacion", "validado", "formalizado"]
    formalizacion = next(m for m in t.mensajes if m.tipo == "formalizacion").payload
    assert formalizacion["entradas"] == [] and formalizacion["univocos"] == ["sistema", "responder"]
    assert repo.listar_lel() == []  # los unívocos no entran al LEL (ADR 0007)


# ---------------------------------------------------------------- validación humana

def test_rechazo_termina_sin_formalizar(tmp_path, analizador):
    srv, llm, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v1": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
    })
    req = srv.procesar(SESION)
    srv.validar(req, Validacion(decision="rechazar", comentario="no es lo que pedí"))
    t = srv.traza(req)
    assert t.estado == Estado.RECHAZADO and ruta(t)[-1] == "rechazado"
    assert tipos(t)[-1] == "validacion" and t.mensajes[-1].payload["comentario"] == "no es lo que pedí"
    assert "modelador_v1" not in llm.llamadas and repo.listar_lel() == []


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
    assert "periodo autenticado" in llm.llamadas["modelador_v1"][0].usuario


def test_el_lel_es_memoria_el_termino_no_se_vuelve_a_debatir(tmp_path, analizador):
    guiones = guiones_sesion_cercana()
    guiones["extractor_v1"].append(EXTRACCION_SESION)
    guiones["clasificador_v1"].append({"resultados": [{"termino": "sistema", "univoco": True},
                                                      {"termino": "registrar", "univoco": True}]})
    srv, llm, _ = montar(tmp_path, analizador, guiones)
    srv.validar(srv.procesar(SESION), APROBAR)

    t = srv.traza(srv.procesar(SESION))
    filtrado = next(m for m in t.mensajes if m.tipo == "filtrado").payload["terminos"]
    sesion = next(f for f in filtrado if f["termino"] == "sesión")
    assert sesion["decision_filtro"] == "resuelto_por_lel"
    assert '"sesión"' in llm.llamadas["clasificador_v1"][1].usuario.split("LEL acumulado")[1]  # va como contexto
    assert ruta(t)[-2:] == ["aceptado_directo", "pendiente_validacion"]


def test_validar_fuera_de_turno_o_con_termino_desconocido(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v1": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
        "modelador_v1": [MODELADO],
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
        "clasificador_v1": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
    })
    t = srv.traza(srv.procesar(SESION))
    ext = t.mensajes[0].payload
    assert ext["intentos"] == 2 and ext["intentos_fallidos"][0]["salida_cruda"] == "{roto"


def test_reanuda_despues_de_reiniciar_con_sqlite(tmp_path, analizador):
    guiones = {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v1": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))],
        "modelador_v1": [MODELADO],
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
        "clasificador_v1": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [{"interpretaciones": [I1],
                                          "retiradas": [{"interpretacion_id": "I2", "motivo": "x"}]}],
        "modelador_v1": [MODELADO],
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


def test_los_nodos_del_grafo_son_los_estados_mas_el_humano(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {})
    nodos = set(srv.grafo.get_graph().nodes) - {"__start__", "__end__"}
    assert nodos == {e.value for e in Estado} | {"humano"}
