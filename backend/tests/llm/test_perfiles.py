"""Proveedores por cuenta (ADR 0021): clientes HTTP, claves cifradas que nunca salen,
el cliente dinámico de los agentes y las rutas /cuenta/modelos."""
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.llm.proveedores as prov
from app.api.routes import modelos
from app.config import Settings
from app.db.repositorio import RepositorioJson
from app.llm import PromptRenderizado
from app.llm.perfiles import COLECCION, ClienteDinamico, PerfilesLLM, con_perfil
from app.llm.proveedores import (
    ClienteAnthropic,
    ClienteCompatibleOpenAI,
    FalloProveedor,
    crear_cliente_de,
)
from tests.escenarios import montar
from tests.fakes import USUARIO_PRUEBA, LLMFalso, como_usuario

PROMPT = PromptRenderizado("p_v1", "sistema", "usuario")
CLAVE = "AIzaSy-secreta-1234"


@pytest.fixture
def s(tmp_path):
    return Settings(_env_file=None, clave_cifrado_path=str(tmp_path / "clave.key"), resultados_dir=str(tmp_path / "r"))


class Http:
    """Registra los POST y responde en orden."""

    def __init__(self, *respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.llamadas.append({"url": url, "json": json, "headers": headers})
        estado, cuerpo = self.respuestas.pop(0)
        return httpx.Response(estado, json=cuerpo, request=httpx.Request("POST", url))


def test_compatible_openai_manda_el_formato_y_reintenta_sin_response_format(monkeypatch):
    http = Http((400, {"error": {"message": "response_format no soportado"}}),
                (200, {"choices": [{"message": {"content": '{"ok": true}'}}]}))
    monkeypatch.setattr(prov.httpx, "post", http)
    c = ClienteCompatibleOpenAI("Google Gemini", "gemini-2.5-flash", "https://g/v1beta/openai/", CLAVE, 0.0, 42, 30,
                                "google:gemini-2.5-flash")
    assert c.completar(PROMPT, {}) == '{"ok": true}' and c.modelo == "google:gemini-2.5-flash"
    primera, segunda = http.llamadas
    assert primera["url"] == "https://g/v1beta/openai/chat/completions"
    assert primera["headers"] == {"Authorization": f"Bearer {CLAVE}"}
    assert primera["json"]["messages"] == [{"role": "system", "content": "sistema"}, {"role": "user", "content": "usuario"}]
    assert primera["json"]["response_format"] == {"type": "json_object"} and primera["json"]["seed"] == 42
    assert "response_format" not in segunda["json"] and "seed" not in segunda["json"]


def test_clave_rechazada_no_repite_la_clave(monkeypatch):
    monkeypatch.setattr(prov.httpx, "post", Http((401, {"error": {"message": "API key not valid"}})))
    c = ClienteCompatibleOpenAI("Google Gemini", "m", "https://g", CLAVE, 0.0, None, 30, "google:m")
    with pytest.raises(FalloProveedor, match="rechazó la clave") as e:
        c.completar(PROMPT, {})
    assert CLAVE not in str(e.value)


def test_anthropic(monkeypatch):
    http = Http((200, {"content": [{"type": "text", "text": '{"a":'}, {"type": "text", "text": " 1}"}]}))
    monkeypatch.setattr(prov.httpx, "post", http)
    c = ClienteAnthropic("claude-haiku-5-5", "https://api.anthropic.com/v1", CLAVE, 0.0, 30, "anthropic:claude-haiku-5-5")
    assert c.completar(PROMPT, {}) == '{"a": 1}'
    llamada = http.llamadas[0]
    assert llamada["url"] == "https://api.anthropic.com/v1/messages"
    assert llamada["headers"]["x-api-key"] == CLAVE and llamada["json"]["system"] == "sistema"


def test_crear_cliente_por_tipo(s):
    assert crear_cliente_de({"proveedor": "ollama", "modelo": "qwen2.5:7b"}, s).modelo == "qwen2.5:7b"
    assert isinstance(crear_cliente_de({"proveedor": "groq", "modelo": "x", "api_key": "k"}, s), ClienteCompatibleOpenAI)
    with pytest.raises(FalloProveedor, match="Falta la URL"):
        crear_cliente_de({"proveedor": "compatible", "modelo": "x"}, s)


def test_la_clave_se_guarda_cifrada_y_nunca_sale(s):
    repo = RepositorioJson(s.ruta(s.resultados_dir))
    perfiles = PerfilesLLM(repo, s)
    vista = perfiles.guardar("U01", {"clasificador": {"proveedor": "google", "modelo": "gemini-2.5-flash"}},
                             {"google": {"api_key": CLAVE}})
    assert CLAVE not in json.dumps(vista) and vista["proveedores"]["google"] == {
        "base_url": None, "tiene_clave": True, "final": "1234"}
    assert CLAVE not in json.dumps(repo.obtener_doc(COLECCION, "U01"))  # cifrada en la base
    clasificador = next(a for a in vista["agentes"] if a["rol"] == "clasificador")
    assert (clasificador["proveedor"], clasificador["propio"]) == ("google", True)
    assert next(a for a in vista["agentes"] if a["rol"] == "extractor")["propio"] is False
    assert perfiles.resuelto("U01")["clasificador"]["api_key"] == CLAVE

    # "" deja la clave; null la borra; null en un agente vuelve al del servidor
    perfiles.guardar("U01", {}, {"google": {"api_key": ""}})
    assert perfiles.resuelto("U01")["clasificador"]["api_key"] == CLAVE
    perfiles.guardar("U01", {"clasificador": None}, {"google": {"api_key": None}})
    assert perfiles.resuelto("U01") == {} and perfiles.publico("U01")["proveedores"]["google"]["tiene_clave"] is False
    with pytest.raises(ValueError, match="proveedor desconocido"):
        perfiles.guardar("U01", {"critico": {"proveedor": "inventado", "modelo": "x"}}, {})


def test_el_cliente_dinamico_usa_el_perfil_en_curso(s, monkeypatch):
    defecto, propio = LLMFalso({"p_v1": ['"defecto"']}, "qwen2.5:7b"), LLMFalso({"p_v1": ['"propio"']}, "google:g")
    monkeypatch.setattr("app.llm.perfiles.crear_cliente_de", lambda e, _s: propio)
    c = ClienteDinamico("critico", defecto, s)
    assert c.modelo == "qwen2.5:7b"
    with con_perfil({"critico": {"proveedor": "google", "modelo": "g", "api_key": "k"}}):
        assert c.modelo == "google:g" and c.completar(PROMPT, {}) == '"propio"'
    with con_perfil({"extractor": {"proveedor": "google", "modelo": "g"}}):  # otro agente: el de siempre
        assert c.completar(PROMPT, {}) == '"defecto"'


def test_el_analisis_usa_los_proveedores_del_dueno_y_lo_anota(tmp_path, analizador, monkeypatch):
    from tests.escenarios import SESION, guiones_sesion_cercana
    srv, _, _ = montar(tmp_path, analizador, guiones_sesion_cercana(), validacion_humana="si_hay_arbitraje",
                       clave_cifrado_path=str(tmp_path / "k.key"))
    propio = LLMFalso(guiones_sesion_cercana(), "google:gemini-2.5-flash")
    monkeypatch.setattr("app.llm.perfiles.crear_cliente_de", lambda e, _s: propio)
    srv.perfiles.guardar(USUARIO_PRUEBA.usuario_id, {"extractor": {"proveedor": "google", "modelo": "gemini-2.5-flash"}},
                         {"google": {"api_key": CLAVE}})
    t = srv.traza(srv.procesar(SESION))
    assert t.config["modelos"]["extractor"] == "google:gemini-2.5-flash"
    assert len(propio.llamadas["extractor_v1"]) == 1  # el Extractor corrió con el de la cuenta
    assert CLAVE not in json.dumps(t.model_dump(mode="json"))


# ---------------------------------------------------------------- rutas

@pytest.fixture
def cliente(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {}, clave_cifrado_path=str(tmp_path / "k.key"))
    app = como_usuario(FastAPI())
    app.include_router(modelos.router)
    app.state.servicio = srv
    return TestClient(app), srv


def test_rutas_de_la_configuracion(cliente, monkeypatch):
    c, _ = cliente
    r = c.get("/cuenta/modelos").json()
    assert {p["id"] for p in r["catalogo"]} >= {"ollama", "google", "openai", "anthropic", "groq", "openrouter"}
    assert [a["rol"] for a in r["agentes"]] == ["extractor", "clasificador", "critico", "modelador", "revisor"]
    r = c.put("/cuenta/modelos", json={"agentes": {"critico": {"proveedor": "google", "modelo": "gemini-2.5-pro"}},
                                       "proveedores": {"google": {"api_key": CLAVE}}})
    assert r.status_code == 200 and CLAVE not in r.text and r.json()["proveedores"]["google"]["final"] == "1234"
    assert c.put("/cuenta/modelos", json={"agentes": {"nadie": None}}).status_code == 422

    vistas = []
    monkeypatch.setattr(modelos, "crear_cliente_de",
                        lambda e, _s: vistas.append(e) or LLMFalso({"prueba_proveedor": ['{"ok": true}']}))
    r = c.post("/cuenta/modelos/probar", json={"proveedor": "google", "modelo": "gemini-2.5-pro"}).json()
    assert r["ok"] is True and vistas[0]["api_key"] == CLAVE  # sin clave en el formulario: la guardada
    r = c.post("/cuenta/modelos/probar", json={"proveedor": "openai", "modelo": "gpt-4.1-mini"}).json()
    assert r == {"ok": False, "ms": None, "error": "Falta la clave de OpenAI."}
