"""LEL idempotente por requisito y término, y respaldo JSON compartido por dos procesos."""
import multiprocessing as mp

import pytest

from app.db import RepositorioJson, RepositorioMongo
from app.models import EntradaLELFormalizada, Interpretacion, Nodo, TipoMensaje


def _entrada(req_id="R01", termino="sesión", nocion="periodo de uso", proyecto_id="P01"):
    return EntradaLELFormalizada(simbolo=termino, tipo="objeto", nocion=[nocion], impacto=["se registra"],
                                 proyecto_id=proyecto_id, req_id=req_id, termino=termino, via="consenso",
                                 fecha="2026-10-07", interpretacion=Interpretacion(
                                     id="I1", significado=nocion, parafrasis_del_requisito="..."))


@pytest.fixture(params=["json", "mongo"])
def repo(request, tmp_path):
    if request.param == "json":
        return RepositorioJson(tmp_path)
    mongomock = pytest.importorskip("mongomock")
    return RepositorioMongo(mongomock.MongoClient(tz_aware=True)["tesis_pruebas"])


def test_guardar_lel_reemplaza_la_entrada_del_mismo_requisito_y_termino(repo):
    repo.guardar_lel([_entrada("R01"), _entrada("R01", "pedido")])
    repo.guardar_lel([_entrada("R02")])
    # `formalizado` se reejecuta tras una caída: la misma entrada (quizá con otra noción) no se duplica
    repo.guardar_lel([_entrada("R01", nocion="periodo de uso continuo"), _entrada("R01", "pedido")])
    assert [(e.req_id, e.termino, e.nocion[0]) for e in repo.listar_lel()] == [
        ("R02", "sesión", "periodo de uso"), ("R01", "sesión", "periodo de uso continuo"),
        ("R01", "pedido", "periodo de uso")]


def test_entradas_anteriores_sin_cambio_siguen_siendo_validas(repo):
    anterior = _entrada().model_dump(mode="json")
    del anterior["cambio"]
    assert EntradaLELFormalizada.model_validate(anterior).cambio is None


def _crear_trazas(directorio, n, barrera, salida):
    repo = RepositorioJson(directorio)
    barrera.wait()
    ids, error = [], None
    try:
        for i in range(n):
            req_id = repo.crear_traza(f"texto {i}", {}).req_id
            repo.agregar_mensaje(req_id, ronda=0, emisor=Nodo.SISTEMA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.ERROR)
            ids.append(req_id)
    except Exception as e:  # noqa: BLE001 — se reporta al proceso de la prueba
        error = f"{type(e).__name__}: {e}"
    salida.put((ids, error))


def test_dos_procesos_sobre_la_misma_carpeta_no_repiten_ids(tmp_path):
    """La API y `scripts/casos_aceptacion.py` pueden escribir a la vez en el respaldo JSON."""
    n = 40
    ctx = mp.get_context("spawn")
    barrera, salida = ctx.Barrier(2), ctx.Queue()
    procesos = [ctx.Process(target=_crear_trazas, args=(tmp_path, n, barrera, salida)) for _ in range(2)]
    for p in procesos:
        p.start()
    resultados = [salida.get(timeout=120) for _ in procesos]
    for p in procesos:
        p.join(30)
    assert [e for _, e in resultados] == [None, None]
    ids = [i for lote, _ in resultados for i in lote]
    assert len(ids) == len(set(ids)) == 2 * n
    repo = RepositorioJson(tmp_path)
    assert all(len(repo.obtener_traza(i).mensajes) == 1 for i in ids)
