"""Errores internos con CORS, orígenes locales, texto con sustitutos UTF-16 sueltos y
SSE que termina cuando el servidor se apaga."""
import json
import signal
import threading

import pytest
from fastapi.testclient import TestClient

from app.api.main import avisar_al_apagar, create_app
from tests.escenarios import SESION, guiones_sesion_cercana, montar

ORIGEN = "http://localhost:5173"


@pytest.fixture
def servicio(tmp_path, analizador):
    guiones = {k: v * 3 for k, v in guiones_sesion_cercana().items()}
    srv, _, _ = montar(tmp_path, analizador, guiones)
    return srv


def test_un_error_interno_sale_como_json_con_cors(servicio):
    def falla(proyecto_id=None):
        raise RuntimeError("traza corrupta")

    servicio.trazas = falla
    c = TestClient(create_app(servicio), raise_server_exceptions=False)
    r = c.get("/trazas", headers={"Origin": ORIGEN})
    assert r.status_code == 500 and r.headers["access-control-allow-origin"] == ORIGEN
    assert "RuntimeError" in r.json()["detail"]
    # la excepción sigue llegando a uvicorn (y a las pruebas) para que quede en el registro
    with pytest.raises(RuntimeError):
        TestClient(create_app(servicio)).get("/trazas")


@pytest.mark.parametrize("origen,admitido", [
    ("http://localhost:5173", True), ("http://localhost:5174", True), ("http://localhost:4173", True),
    ("http://127.0.0.1:5174", True), ("http://otro.ejemplo.com", False), ("http://localhost.ejemplo.com", False),
])
def test_cors_por_omision_admite_cualquier_puerto_local(servicio, origen, admitido):
    c = TestClient(create_app(servicio))
    r = c.options("/proyectos", headers={"Origin": origen, "Access-Control-Request-Method": "GET"})
    assert (r.status_code == 200 and r.headers.get("access-control-allow-origin") == origen) == admitido


def _post_crudo(c, ruta, cuerpo: str):
    return c.post(ruta, content=cuerpo.encode(), headers={"Content-Type": "application/json"})


def test_texto_con_sustitutos_sueltos_se_rechaza_con_422(servicio):
    with TestClient(create_app(servicio)) as c:
        assert _post_crudo(c, "/procesar", '{"texto": "registrar \\ud800 usuarios"}').status_code == 422
        r = _post_crudo(c, "/proyectos", '{"nombre": "x", "descripcion": "d \\ud83d"}')
        assert r.status_code == 422 and json.loads(r.text)["detail"][0]["loc"] == ["body", "descripcion"]

        # un lote con un origen inválido no registra nada
        p = c.post("/proyectos", json={"nombre": "Lote"}).json()["proyecto_id"]
        lote = json.dumps({"requisitos": [
            {"texto": "El sistema debe registrar la venta."},
            {"texto": "El sistema debe emitir el recibo.", "origen": {"archivo": "srs.pdf", "texto_original": "X"}},
        ]}).replace('"X"', '"emitir el recibo \\ud83d"')
        assert _post_crudo(c, f"/proyectos/{p}/requisitos", lote).status_code == 422
        assert c.get(f"/proyectos/{p}/requisitos").json() == []

        # una validación con un comentario inválido se rechaza antes de aceptarla
        c.post("/procesar", json={"texto": SESION})
        servicio.cola.esperar(10)
        req_id = c.get("/trazas").json()[-1]["req_id"]
        assert _post_crudo(c, f"/validar/{req_id}", '{"decision": "aprobar", "comentario": "ok \\ud83d"}').status_code == 422
        edicion = '{"decision": "aprobar", "interpretaciones_editadas": {"\\ud800": {"id": "I1", "significado": "a", ' \
                  '"parafrasis_del_requisito": "b"}}}'
        assert _post_crudo(c, f"/validar/{req_id}", edicion).status_code == 422
        assert c.get(f"/traza/{req_id}").json()["estado"] == "pendiente_validacion"
        assert c.post(f"/validar/{req_id}", json={"decision": "aprobar", "comentario": "ok 😀"}).status_code == 202
        servicio.cola.esperar(10)
        t = c.get(f"/traza/{req_id}").json()
        assert t["estado"] == "formalizado"
        assert next(m for m in t["mensajes"] if m["tipo"] == "validacion")["payload"]["comentario"] == "ok 😀"


def test_el_sse_de_un_requisito_en_pausa_termina_al_apagar(servicio):
    req_id = servicio.procesar(SESION)  # queda en pendiente_validacion, sin estado terminal
    app = create_app(servicio)
    app.state.apagando.set()
    salida = {}
    # en un hilo: sin la corrección, el stream no termina nunca
    hilo = threading.Thread(target=lambda: salida.update(r=TestClient(app).get(f"/eventos/{req_id}")), daemon=True)
    hilo.start()
    hilo.join(10)
    assert "r" in salida, "el SSE siguió abierto con el servidor apagándose"
    texto = salida["r"].text
    assert "event: estado" in texto and "pendiente_validacion" in texto and "event: fin" not in texto


def test_avisar_al_apagar_se_encadena_a_la_senal_de_uvicorn():
    recibidas = []
    anterior = signal.signal(signal.SIGTERM, lambda s, marco: recibidas.append(s))  # hace de uvicorn
    try:
        apagando = threading.Event()
        restaurar = avisar_al_apagar(apagando)
        signal.raise_signal(signal.SIGTERM)
        assert apagando.is_set() and recibidas == [signal.SIGTERM]
        restaurar()
        apagando.clear()
        signal.raise_signal(signal.SIGTERM)
        assert not apagando.is_set() and len(recibidas) == 2
    finally:
        signal.signal(signal.SIGTERM, anterior)
