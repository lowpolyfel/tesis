"""«Volver a procesar» retoma desde la etapa que falló, con la salida guardada de la anterior."""
import pytest

from app.entrevistas.almacen import COLECCION_ETAPAS
from app.entrevistas.turnos import leer_texto
from app.fases.lexico import Lexico
from app.llm.proveedores import FalloProveedor
from tests.fases.escenario import ENTREVISTA, montar

SATURADO = "Google Gemini respondió 503 tras 5 reintento(s): The model is overloaded. (UNAVAILABLE)"


@pytest.fixture
def escenario(tmp_path, analizador):
    return montar(tmp_path, analizador)


def _falla_una_vez(llm, prompt):
    """El guion `prompt` responde 503 la primera vez y bien después."""
    original = llm.guiones[prompt]
    veces = {"n": 0}

    def guion(p):
        veces["n"] += 1
        if veces["n"] == 1:
            raise FalloProveedor(SATURADO)
        return original(p)
    llm.guiones[prompt] = guion


def _reprocesar(srv, eid, **kw):
    srv.cola.iniciar()
    try:
        doc = srv.entrevistas.reprocesar(eid, **kw)
        srv.cola.esperar(10)
    finally:
        srv.cola.detener()
    return doc


def _llamadas(llm):
    return {k: len(v) for k, v in llm.llamadas.items()}


def test_si_falla_el_modelador_se_retoma_ahi_sin_repetir_lo_anterior(escenario):
    srv, llm, p = escenario
    _falla_una_vez(llm, "modelador_lexico_v1")
    eid = srv.entrevistas.procesar(p.proyecto_id, "Dra. Ruiz", leer_texto(ENTREVISTA))
    doc = srv.entrevistas.almacen.obtener(eid)
    assert doc["estado"] == "error" and "503" in doc["error"]

    etapas = srv.repo.obtener_doc(COLECCION_ETAPAS, eid)
    assert etapas["en_curso"] == "modelada" and etapas["fallo"]["nodo"] == "modelada"
    assert etapas["orden"][:4] == ["cargada", "leida", "extraida", "interpretada"]
    assert etapas["salidas"]["interpretada"]["estado"]["terminos"]  # la salida de cada etapa, completa
    assert srv.entrevistas.punto_de_retomar(doc) == {"nodo": "modelada", "desde": "arbitrada",
                                                      "estado": etapas["salidas"]["arbitrada"]["estado"]}

    antes = _llamadas(llm)
    nuevo = _reprocesar(srv, eid)
    assert nuevo["corrida"] == 2 and nuevo["retomada"] == {"desde": "modelada", "despues_de": "arbitrada", "corrida": 2}
    doc = srv.entrevistas.almacen.obtener(eid)
    assert doc["estado"] == "lista", doc.get("error")
    despues = _llamadas(llm)
    # nadie más que el Modelador volvió a trabajar: lo de antes salió de la etapa guardada
    assert {k: despues[k] - antes.get(k, 0) for k in despues if despues[k] != antes.get(k, 0)} == {"modelador_lexico_v1": 1}
    entradas = Lexico(srv.repo).listar(p.proyecto_id)
    assert len(entradas) == 7 and {e["corrida"] for e in entradas} == {f"{eid}#2"}
    # la bitácora sigue la historia: lo que salió bien antes, sin el error, y lo nuevo
    tipos = [m["tipo"] for m in srv.entrevistas.almacen.bitacora(eid)["mensajes"]]
    assert tipos[0] == "ficha" and "error" not in tipos and tipos[-1] == "formalizacion"
    assert [m["secuencia"] for m in srv.entrevistas.almacen.bitacora(eid)["mensajes"]] == list(range(1, len(tipos) + 1))
    # qué modelo respondió, por agente y corrida
    assert {(u["corrida"], u["rol"]) for u in doc["modelos_usados"]} >= {(f"{eid}#1", "revisor"), (f"{eid}#2", "modelador")}


def test_si_falla_el_clasificador_se_retoma_en_la_interpretacion(escenario):
    srv, llm, p = escenario
    _falla_una_vez(llm, "clasificador_intencion_v1")
    eid = srv.entrevistas.procesar(p.proyecto_id, "Dra. Ruiz", leer_texto(ENTREVISTA))
    assert srv.entrevistas.almacen.obtener(eid)["estado"] == "error"
    antes = _llamadas(llm)
    _reprocesar(srv, eid)
    assert srv.entrevistas.almacen.obtener(eid)["estado"] == "lista"
    despues = _llamadas(llm)
    assert despues["revisor_entrevista_v1"] == antes["revisor_entrevista_v1"]  # la ficha no se vuelve a pedir
    assert despues["extractor_entrevista_v1"] == antes["extractor_entrevista_v1"]
    assert despues["clasificador_intencion_v1"] > antes["clasificador_intencion_v1"]


def test_desde_cero_vuelve_a_empezar(escenario):
    srv, llm, p = escenario
    _falla_una_vez(llm, "modelador_lexico_v1")
    eid = srv.entrevistas.procesar(p.proyecto_id, "Dra. Ruiz", leer_texto(ENTREVISTA))
    antes = _llamadas(llm)
    nuevo = _reprocesar(srv, eid, desde_cero=True)
    assert nuevo["retomada"] is None
    assert srv.entrevistas.almacen.obtener(eid)["estado"] == "lista"
    assert _llamadas(llm)["revisor_entrevista_v1"] == antes["revisor_entrevista_v1"] + 1


def test_cancelada_al_principio_empieza_de_cero(escenario):
    srv, _, p = escenario
    doc = srv.entrevistas.registrar(p.proyecto_id, "X", leer_texto(ENTREVISTA), {"tipo": "texto"})
    eid = doc["entrevista_id"]
    srv.entrevistas._cancelados.add(eid)
    srv.entrevistas.ejecutar(eid)
    assert srv.entrevistas.punto_de_retomar(srv.entrevistas.almacen.obtener(eid)) is None  # no había nada hecho
    assert _reprocesar(srv, eid)["retomada"] is None
    assert srv.entrevistas.almacen.obtener(eid)["estado"] == "lista"


def test_borrar_la_entrevista_borra_sus_etapas(escenario):
    srv, _, p = escenario
    eid = srv.entrevistas.procesar(p.proyecto_id, "Dra. Ruiz", leer_texto(ENTREVISTA))
    assert srv.repo.obtener_doc(COLECCION_ETAPAS, eid)
    srv.entrevistas.borrar(eid)
    assert srv.repo.obtener_doc(COLECCION_ETAPAS, eid) is None


def test_la_api_dice_desde_donde_se_retoma(tmp_path, analizador):
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from tests.fakes import como_usuario

    srv, llm, p = montar(tmp_path, analizador)
    _falla_una_vez(llm, "modelador_lexico_v1")
    eid = srv.entrevistas.procesar(p.proyecto_id, "Dra. Ruiz", leer_texto(ENTREVISTA))
    with TestClient(como_usuario(create_app(srv))) as c:
        lista = c.get(f"/proyectos/{p.proyecto_id}/entrevistas").json()
        e = next(x for x in lista if x["entrevista_id"] == eid)
        assert e["retomar_desde"] == {"nodo": "modelada", "despues_de": "arbitrada"}
        r = c.post(f"/entrevistas/{eid}/reprocesar")
        assert r.status_code == 202 and r.json()["retomada"]["desde"] == "modelada"


def test_un_fallo_al_generar_una_fase_queda_guardado(tmp_path, analizador):
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from tests.fakes import como_usuario

    srv, llm, p = montar(tmp_path, analizador)
    srv.entrevistas.procesar(p.proyecto_id, "Dra. Ruiz", leer_texto(ENTREVISTA))
    lexico = Lexico(srv.repo)
    for e in lexico.listar(p.proyecto_id):
        lexico.validar(e, "2026-11-04")
    _falla_una_vez(llm, "modelador_mapa_proposito_v1")
    with TestClient(como_usuario(create_app(srv))) as c:
        lineas = c.post(f"/proyectos/{p.proyecto_id}/fases/mapa/generar").text
        assert '"tipo": "error"' in lineas and "503" in lineas
        vista = c.get(f"/proyectos/{p.proyecto_id}/fases/mapa").json()
        assert vista["documento"] is None and "503" in vista["ultimo_fallo"]["mensaje"]
        # volver a generar: el léxico ya estaba guardado, se retoma en el mapa y el fallo se limpia
        assert '"tipo": "resultado"' in c.post(f"/proyectos/{p.proyecto_id}/fases/mapa/generar").text
        vista = c.get(f"/proyectos/{p.proyecto_id}/fases/mapa").json()
        assert vista["documento"] and vista["ultimo_fallo"] is None

