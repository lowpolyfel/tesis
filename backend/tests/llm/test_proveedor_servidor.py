"""Proveedor por omisión del servidor (LLM_PROVEEDOR): todo por API, sin Ollama."""
from app.config import Settings
from app.llm import crear_cliente
from app.llm.cliente import ClienteOllama
from app.llm.perfiles import por_omision
from app.llm.proveedores import ClienteCompatibleOpenAI
from app.preparacion import modelos_del_analisis


def _s(**kw):
    return Settings(_env_file=None, llm_proveedor="google", llm_api_key="clave-servidor", critico_provider="google",
                    extractor_model="gemini-flash", clasificador_model="gemini-flash", modelador_model="gemini-flash",
                    critico_model="gemini-pro", revisor_model="gemini-flash", embedding_proveedor="google",
                    embedding_model="gemini-embedding-001", **kw)


def test_por_omision_sigue_siendo_ollama():
    s = Settings(_env_file=None)
    assert isinstance(crear_cliente(s.llm_proveedor, s.extractor_model, s), ClienteOllama)
    assert {e["proveedor"] for e in por_omision(s).values()} == {"ollama"}


def test_google_usa_el_endpoint_compatible_con_la_clave_del_servidor():
    s = _s()
    c = crear_cliente("google", "gemini-flash", s)
    assert isinstance(c, ClienteCompatibleOpenAI)
    assert c.base_url.startswith("https://generativelanguage.googleapis.com")
    assert c._clave == "clave-servidor"
    assert c.modelo == "google:gemini-flash"


def test_el_critico_prefiere_su_propia_clave():
    s = _s(critico_api_key="clave-critico")
    assert crear_cliente("google", "gemini-pro", s, rol="critico")._clave == "clave-critico"
    assert crear_cliente("google", "gemini-flash", s)._clave == "clave-servidor"


def test_perfil_del_servidor_y_preparacion_dicen_google():
    s = _s()
    assert {e["proveedor"] for e in por_omision(s).values()} == {"google"}
    modelos = modelos_del_analisis(s)
    assert {m["proveedor"] for m in modelos} == {"google"}
    assert any(m["tipo"] == "embeddings" and m["modelo"] == "gemini-embedding-001" for m in modelos)


def test_llm_modelo_pone_el_mismo_modelo_a_todos():
    s = Settings(_env_file=None, llm_modelo="gemini-flash")
    assert {s.extractor_model, s.clasificador_model, s.modelador_model, s.critico_model, s.revisor_model,
            s.comparador_model, s.agente_unico_model} == {"gemini-flash"}
