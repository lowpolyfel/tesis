"""Reintentos de Gemini ante 503/UNAVAILABLE y 429/RESOURCE_EXHAUSTED, y el modelo de respaldo."""
import json

import httpx
import pytest
from pydantic import BaseModel

import app.llm.proveedores as prov
from app.config import Settings
from app.divergence import EmbeddingsGemini
from app.llm import PromptRenderizado
from app.llm.estructurado import generar
from app.llm.proveedores import (
    ClienteCompatibleOpenAI,
    FalloProveedor,
    crear_cliente_de,
    espera,
    reintentable,
)

PROMPT = PromptRenderizado("p_v1", "sistema", "usuario")
OK = (200, {"choices": [{"message": {"content": '{"ok": true}'}}]})
SATURADO = (503, [{"error": {"code": 503, "message": "The model is overloaded. Please try again later.",
                             "status": "UNAVAILABLE"}}])
CUOTA = (429, {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}})


class Http:
    def __init__(self, *respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.llamadas.append(json)
        estado, cuerpo = self.respuestas.pop(0)
        return httpx.Response(estado, json=cuerpo, request=httpx.Request("POST", url))


@pytest.fixture
def esperas(monkeypatch):
    vistas = []
    monkeypatch.setattr(prov, "_dormir", vistas.append)
    monkeypatch.setattr(prov, "_azar", lambda: 0.5)
    return vistas


def _gemini(**extra):
    return ClienteCompatibleOpenAI("Google Gemini", "gemini-x", "https://g/v1beta/openai", "k", 0.0, 42, 30,
                                   "google:gemini-x", reintentos=5, backoff_base_s=1, backoff_max_s=30,
                                   prefijo="google", **extra)


def test_solo_503_y_429_son_reintentables():
    def r(estado, cuerpo):
        return httpx.Response(estado, json=cuerpo)
    assert reintentable(r(*SATURADO)) and reintentable(r(*CUOTA))
    assert reintentable(r(500, {"error": {"status": "UNAVAILABLE"}}))  # el estado de Google cuenta aunque el código no
    assert not reintentable(r(500, {"error": {"status": "INTERNAL"}}))
    assert not reintentable(r(400, {"error": {"message": "bad"}}))
    assert not reintentable(r(401, {}))


def test_espera_exponencial_con_jitter_y_tope(monkeypatch):
    monkeypatch.setattr(prov, "_azar", lambda: 0.0)
    assert [espera(k, 1, 30) for k in range(6)] == [0.5, 1, 2, 4, 8, 15]  # la mitad fija; el tope corta en 30
    monkeypatch.setattr(prov, "_azar", lambda: 1.0)
    assert [espera(k, 1, 30) for k in range(6)] == [1, 2, 4, 8, 16, 30]
    assert espera(0, 1, 30, retry_after="7") == 7 and espera(0, 1, 30, retry_after="99") == 30


def test_reintenta_un_503_y_sigue_con_el_mismo_modelo(monkeypatch, esperas):
    http = Http(SATURADO, CUOTA, OK)
    monkeypatch.setattr(prov.httpx, "post", http)
    c = _gemini()
    assert c.completar(PROMPT, {}) == '{"ok": true}'
    assert esperas == [0.75, 1.5]  # 1·2^0 y 1·2^1, con jitter a la mitad
    assert [x["model"] for x in http.llamadas] == ["gemini-x"] * 3
    assert c.ultimo_uso() == {"modelo": "google:gemini-x", "respaldo": False, "original": "google:gemini-x",
                              "reintentos": 2}


def test_no_reintenta_otros_errores(monkeypatch, esperas):
    monkeypatch.setattr(prov.httpx, "post", Http((500, {"error": {"message": "boom", "status": "INTERNAL"}})))
    with pytest.raises(FalloProveedor, match="respondió 500: boom") as e:
        _gemini().completar(PROMPT, {})
    assert esperas == [] and "reintento" not in str(e.value)


def test_se_agotan_los_cinco_reintentos_sin_respaldo(monkeypatch, esperas):
    http = Http(*[SATURADO] * 6)
    monkeypatch.setattr(prov.httpx, "post", http)
    with pytest.raises(FalloProveedor) as e:
        _gemini().completar(PROMPT, {})
    assert len(http.llamadas) == 6 and len(esperas) == 5
    # legible: ni la lista JSON cruda ni la clave
    assert str(e.value) == ("Google Gemini respondió 503 tras 5 reintento(s): The model is overloaded. "
                            "Please try again later. (UNAVAILABLE)")


def test_agotados_usa_una_vez_el_modelo_de_respaldo(monkeypatch, esperas):
    http = Http(*[SATURADO] * 6, OK)
    monkeypatch.setattr(prov.httpx, "post", http)
    c = _gemini(respaldo="gemini-ligero")
    assert c.completar(PROMPT, {}) == '{"ok": true}'
    assert [x["model"] for x in http.llamadas] == ["gemini-x"] * 6 + ["gemini-ligero"]
    assert c.ultimo_uso() == {"modelo": "google:gemini-ligero", "respaldo": True, "original": "google:gemini-x",
                              "reintentos": 5}
    # el respaldo se intenta una sola vez
    http = Http(*[SATURADO] * 7)
    monkeypatch.setattr(prov.httpx, "post", http)
    with pytest.raises(FalloProveedor, match="modelo de respaldo gemini-ligero respondió 503"):
        _gemini(respaldo="gemini-ligero").completar(PROMPT, {})
    assert len(http.llamadas) == 7


def test_la_respuesta_estructurada_dice_que_modelo_respondio(monkeypatch, esperas):
    class Salida(BaseModel):
        ok: bool

    monkeypatch.setattr(prov.httpx, "post", Http(*[SATURADO] * 6, OK))
    r = generar(_gemini(respaldo="gemini-ligero"), PROMPT, Salida)
    assert r.valor.ok and r.modelo == "google:gemini-ligero" and r.respaldo == "google:gemini-x" and r.reintentos == 5


def test_el_env_configura_reintentos_y_respaldo_solo_para_google(tmp_path):
    s = Settings(_env_file=None, gemini_reintentos=3, gemini_fallback_model="gemini-ligero",
                 clave_cifrado_path=str(tmp_path / "k"))
    g = crear_cliente_de({"proveedor": "google", "modelo": "gemini-x", "api_key": "k"}, s)
    assert g.reintentos == 3 and g.respaldo == "gemini-ligero"
    # la prueba de modelos y «probar» miden ese modelo: sin respaldo
    assert crear_cliente_de({"proveedor": "google", "modelo": "gemini-x", "api_key": "k"}, s, con_respaldo=False).respaldo is None
    # el respaldo igual al modelo no cuenta
    assert crear_cliente_de({"proveedor": "google", "modelo": "gemini-ligero", "api_key": "k"}, s).respaldo is None
    otro = crear_cliente_de({"proveedor": "groq", "modelo": "x", "api_key": "k"}, s)
    assert otro.reintentos == 0 and otro.respaldo is None
    with pytest.raises(ValueError):
        Settings(_env_file=None, gemini_reintentos=6)  # máximo 5


def test_los_embeddings_de_gemini_tambien_reintentan(esperas):
    respuestas = [SATURADO, (200, {"embeddings": [{"values": [1.0, 0.0]}]})]

    def responder(request):
        estado, cuerpo = respuestas.pop(0)
        return httpx.Response(estado, content=json.dumps(cuerpo))
    e = EmbeddingsGemini("gemini-embedding-001", "k", cliente=httpx.Client(transport=httpx.MockTransport(responder)),
                         reintentos=5)
    assert e.vectorizar(["a"]) == [[1.0, 0.0]] and esperas == [0.75]
