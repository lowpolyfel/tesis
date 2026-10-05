"""Repositorio: misma interfaz en JSON y en Mongo; respaldo JSON si Mongo no responde."""
import pytest

from app.config import Settings
from app.db import RepositorioJson, RepositorioMongo, crear_repositorio
from app.models import EntradaLELFormalizada, Estado, Interpretacion, Nodo, TipoMensaje


def _entrada(req_id="R01"):
    return EntradaLELFormalizada(simbolo="sesión", tipo="objeto", nocion=["periodo de uso"], impacto=["se registra"],
                                 req_id=req_id, termino="sesión", via="consenso", fecha="2026-10-05",
                                 interpretacion=Interpretacion(id="I1", significado="periodo de uso",
                                                               parafrasis_del_requisito="..."))


def _mongo():
    mongomock = pytest.importorskip("mongomock")
    return RepositorioMongo(mongomock.MongoClient(tz_aware=True)["tesis_pruebas"])


@pytest.fixture(params=["json", "mongo"])
def repo(request, tmp_path):
    return RepositorioJson(tmp_path) if request.param == "json" else _mongo()


def test_ids_consecutivos_y_traza_inicial(repo):
    a = repo.crear_traza("uno", {"umbral": 0.75})
    b = repo.crear_traza("dos", {})
    assert (a.req_id, b.req_id) == ("R01", "R02")
    t = repo.obtener_traza("R01")
    assert t.texto == "uno" and t.estado == Estado.CARGADO and t.config == {"umbral": 0.75}
    assert [x.estado for x in t.transiciones] == [Estado.CARGADO]
    assert repo.obtener_traza("R99") is None


def test_mensajes_con_secuencia_y_transiciones(repo):
    req = repo.crear_traza("texto", {}).req_id
    m1 = repo.agregar_mensaje(req, ronda=0, emisor=Nodo.EXTRACTOR, receptor=Nodo.FILTROS,
                              tipo=TipoMensaje.EXTRACCION, payload={"terminos": []}, modelo="m", prompt_version="extractor_v1")
    repo.cambiar_estado(req, Estado.EXTRAIDO)
    m2 = repo.agregar_mensaje(req, ronda=1, emisor=Nodo.CRITICO, receptor=Nodo.CLASIFICADOR,
                              tipo=TipoMensaje.OBJECION, payload={"objeciones": [{"regla": "R1"}]})
    assert (m1.secuencia, m2.secuencia) == (1, 2)
    t = repo.obtener_traza(req)
    assert t.estado == Estado.EXTRAIDO
    assert [(x.estado, x.secuencia) for x in t.transiciones] == [(Estado.CARGADO, 0), (Estado.EXTRAIDO, 1)]
    assert [m.model_dump(exclude={"timestamp"}) for m in t.mensajes] == [
        m1.model_dump(exclude={"timestamp"}), m2.model_dump(exclude={"timestamp"})]
    assert t.mensajes[0].timestamp.tzinfo is not None


def test_lel(repo):
    assert repo.listar_lel() == []
    repo.guardar_lel([_entrada("R01")])
    repo.guardar_lel([])
    repo.guardar_lel([_entrada("R02")])
    assert [e.req_id for e in repo.listar_lel()] == ["R01", "R02"]
    assert repo.listar_lel()[0] == _entrada("R01")


def test_mensaje_a_traza_inexistente(repo):
    with pytest.raises(KeyError):
        repo.agregar_mensaje("R07", ronda=0, emisor=Nodo.SISTEMA, receptor=Nodo.SISTEMA, tipo=TipoMensaje.ERROR)


def test_respaldo_json_si_mongo_no_responde(tmp_path):
    s = Settings(_env_file=None, mongo_uri="mongodb://127.0.0.1:1", mongo_timeout_ms=200,
                 resultados_dir=str(tmp_path / "res"))
    repo = crear_repositorio(s)
    assert isinstance(repo, RepositorioJson)
    assert repo.descripcion.startswith("json:") and (tmp_path / "res" / "trazas").is_dir()


def test_json_rechaza_ids_que_no_son_de_requisito(tmp_path):
    repo = RepositorioJson(tmp_path)
    assert repo.obtener_traza("../../etc/passwd") is None
