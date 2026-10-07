"""Un Ollama que acepta la conexión y nunca responde no debe colgar la cola: las llamadas
fallan con TimeoutError al pasar OLLAMA_TIMEOUT_S y el nodo lo registra en la traza."""
import socket
import threading
import time

import pytest

from app.config import Settings
from app.llm import cargar_prompt, crear_cliente

pytest.importorskip("langchain_ollama")


@pytest.fixture
def ollama_colgado():
    """Socket que acepta conexiones y nunca contesta."""
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen()
    abiertas = []

    def aceptar():
        while True:
            try:
                abiertas.append(servidor.accept())
            except OSError:
                return

    threading.Thread(target=aceptar, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.getsockname()[1]}"
    servidor.close()
    for conexion, _ in abiertas:
        conexion.close()


def _termina(fn, limite=15.0):
    """Corre `fn` en un hilo: sin timeout se quedaría esperando para siempre."""
    salida = {}

    def correr():
        inicio = time.monotonic()
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            salida["error"] = e
        salida["segundos"] = time.monotonic() - inicio

    hilo = threading.Thread(target=correr, daemon=True)
    hilo.start()
    hilo.join(limite)
    assert "segundos" in salida, f"la llamada siguió esperando después de {limite} s"
    return salida


def test_la_generacion_falla_con_timeout(ollama_colgado):
    s = Settings(_env_file=None, ollama_base_url=ollama_colgado, ollama_timeout_s=0.5)
    cliente = crear_cliente("ollama", "qwen2.5:7b", s)
    prompt = cargar_prompt("extractor_v1").renderizar(texto="El sistema debe registrar la sesión.")
    r = _termina(lambda: cliente.completar(prompt, {"type": "object"}))
    assert isinstance(r["error"], TimeoutError) and "OLLAMA_TIMEOUT_S" in str(r["error"])


def test_los_embeddings_fallan_con_timeout(ollama_colgado):
    from app.divergence import EmbeddingsOllama

    emb = EmbeddingsOllama("nomic-embed-text", ollama_colgado, timeout_s=0.5)
    r = _termina(lambda: emb.vectorizar(["sesión"]))
    assert isinstance(r["error"], TimeoutError)


def test_el_timeout_por_omision_es_generoso():
    assert Settings(_env_file=None).ollama_timeout_s >= 60
