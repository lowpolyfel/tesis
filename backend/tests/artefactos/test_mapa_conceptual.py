"""Mapa conceptual (ADR 0020): los pasos previos en código, la revisión de lo que propone
el Modelador (LLM falso), el respaldo en código y las rutas con su progreso en NDJSON."""
import json

import pytest
from app.agents.modelador import Modelador
from app.api.routes import artefactos, proyectos
from app.artefactos import big_picture_proyecto
from app.artefactos import mapa_conceptual as mc
from app.models import SalidaMapaConceptual
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.artefactos.ayudantes import documentos, lel, sembrar, trazas
from tests.escenarios import montar
from tests.fakes import LLMFalso, como_usuario


@pytest.fixture(scope="module")
def bp():
    return big_picture_proyecto(documentos(), lel(), trazas())


def _frases(mapa):
    et = {c["id"]: c["etiqueta"] for c in mapa["conceptos"]} | {"central": mapa["central"]["etiqueta"]}
    return [(et[p["origen"]], p["enlace"], et[p["destino"]]) for p in mapa["proposiciones"]]


def _eventos(bp, modelador=None):
    return list(mc.generar_mapa(bp, "Control escolar", None, modelador))


def test_clave_une_plurales_y_articulos():
    assert mc.clave("Los Usuarios") == mc.clave("usuario") == "usuario"
    assert mc.clave("los proveedores") == "proveedor"
    assert mc.clave("al cliente") == mc.clave("clientes") == "cliente"


def test_conjugar():
    assert mc.conjugar("consultar") == "consulta"
    assert mc.conjugar("dar de alta") == "da de alta"
    assert mc.conjugar("mostrar") == "muestra"
    assert mc.conjugar("imprimir") == "imprime"


def test_candidatos_sin_repetidos_y_con_el_sistema_como_central(bp):
    conceptos, relaciones = mc.candidatos(bp)
    etiquetas = [c["etiqueta"] for c in conceptos]
    assert len({mc.clave(e) for e in etiquetas}) == len(etiquetas)
    assert "usuarios" not in etiquetas and "usuario" in etiquetas  # «Los Usuarios» y el sujeto del LEL
    assert not any(mc.clave(e) == "sistema" for e in etiquetas)  # el sistema es el central
    assert "dar de alta" not in etiquetas  # un verbo del léxico es un enlace
    assert {(r["origen"], r["destino"]) for r in relaciones}  # sin repetidas en ningún sentido
    pares = [frozenset((r["origen"], r["destino"])) for r in relaciones]
    assert len(pares) == len(set(pares))
    assert [c["peso"] for c in conceptos] == sorted((c["peso"] for c in conceptos), reverse=True)


def test_mapa_en_codigo_se_lee_como_frases(bp):
    eventos = _eventos(bp)
    mapa = eventos[-1]["mapa"]
    assert mapa["generado_por"] == "codigo" and mapa["aviso"] == "Sin Modelador: el mapa se armó en código."
    frases = _frases(mapa)
    assert ("usuario", "consulta", "bitácora") in frases
    assert ("administrador", "da de alta", "cliente") in frases
    assert ("Control escolar", "registra", "periodo de uso del usuario") in frases
    # cada proposición se rastrea a un requisito y no hay conceptos sueltos
    assert all(p["req_ids"] for p in mapa["proposiciones"])
    usados = {x for p in mapa["proposiciones"] for x in (p["origen"], p["destino"])}
    assert {c["id"] for c in mapa["conceptos"]} <= usados
    en_ramas = [i for r in mapa["ramas"] for i in r["conceptos"]]
    assert sorted(en_ramas) == sorted(c["id"] for c in mapa["conceptos"])
    assert mapa["mermaid"].startswith("flowchart TD")
    assert mapa["grafo"]["nodos"] == len(bp["nodos"])
    assert [(e["id"], e["estado"]) for e in eventos if e["tipo"] == "paso"] == [
        ("reunir", "curso"), ("reunir", "ok"), ("conceptos", "curso"), ("conceptos", "ok"),
        ("relaciones", "curso"), ("relaciones", "ok"), ("revision", "curso"), ("revision", "ok")]


def test_recortar_respeta_los_limites():
    conceptos = [{"id": f"C{i}", "peso": 20 - i} for i in range(1, 11)]
    relaciones = [{"origen": "C1", "destino": f"C{i}", "peso": 1} for i in range(2, 11)]
    relaciones += [{"origen": "central", "destino": f"C{i}", "peso": 0.5} for i in range(2, 11)]
    quedan, elegidas = mc.recortar(conceptos, relaciones, max_conceptos=6, max_proposiciones=8, max_grado=3)
    assert len(elegidas) <= 8
    grado = {}
    for r in elegidas:
        for x in (r["origen"], r["destino"]):
            grado[x] = grado.get(x, 0) + 1
    assert grado["C1"] == 3 and all(v <= 3 for k, v in grado.items() if k != "central")
    assert {c["id"] for c in quedan} <= {f"C{i}" for i in range(1, 7)}


def _propuesta(conceptos, central="Control escolar", proposiciones=None, ramas=None):
    ids = [c for c, _ in conceptos]
    return {"central": central, "conceptos": [{"id": c, "etiqueta": e} for c, e in conceptos],
            "ramas": ramas or [{"nombre": "Todo", "conceptos": ids}],
            "proposiciones": proposiciones or []}


def _modelador(bp, respuestas):
    """Un Modelador con LLM falso. `respuestas(candidatos) -> list[dict]` usa los ids reales."""
    conceptos, _ = mc.candidatos(bp)
    por_etiqueta = {c["etiqueta"]: c["id"] for c in conceptos}
    llm = LLMFalso({"modelador_mapa_v1": respuestas(por_etiqueta)})
    return Modelador(llm), llm


def test_el_modelador_organiza_y_se_reintenta_si_inventa_un_concepto(bp):
    def respuestas(i):
        buena = _propuesta(
            [(i["usuario"], "Usuario"), (i["bitácora"], "Bitácora"), (i["administrador"], "Administrador"),
             (i["cliente"], "Cliente")],
            proposiciones=[{"origen": i["usuario"], "enlace": "Consulta", "destino": i["bitácora"]},
                           {"origen": i["administrador"], "enlace": "registra", "destino": i["cliente"]},
                           {"origen": i["usuario"], "enlace": "usa", "destino": "central"},
                           # ningún requisito une al usuario con el cliente: se descarta
                           {"origen": i["usuario"], "enlace": "atiende a", "destino": i["cliente"]}],
            ramas=[{"nombre": "Personas", "conceptos": [i["usuario"], i["administrador"]]},
                   {"nombre": "Datos", "conceptos": [i["bitácora"], i["cliente"]]}])
        inventada = _propuesta([("C99", "Inventado")], proposiciones=[{"origen": "C99", "enlace": "x", "destino": "central"}])
        return [inventada, buena]

    modelador, llm = _modelador(bp, respuestas)
    eventos = _eventos(bp, modelador)
    mapa = eventos[-1]["mapa"]
    assert len(llm.llamadas["modelador_mapa_v1"]) == 2  # el primero no pasó la verificación
    assert "C99" in llm.llamadas["modelador_mapa_v1"][1].usuario  # el reintento lleva el error
    assert mapa["generado_por"] == "modelador" and mapa["modelo"] == "llm-falso"
    assert mapa["prompt_version"] == "modelador_mapa_v1" and mapa["aviso"] is None
    assert _frases(mapa) == [("Usuario", "consulta", "Bitácora"), ("Administrador", "registra", "Cliente"),
                             ("Usuario", "usa", "Control escolar")]
    assert [r["nombre"] for r in mapa["ramas"]] == ["Personas", "Datos"]
    modelo = next(e for e in eventos if e["tipo"] == "paso" and e["id"] == "modelador" and e["estado"] == "ok")
    assert "reintento" in modelo["detalle"]
    revision = next(e for e in eventos if e["id"] == "revision" and e["estado"] == "ok")
    assert "1 sin respaldo descartadas" in revision["detalle"]


def test_si_el_modelador_falla_queda_el_mapa_en_codigo(bp):
    modelador, _ = _modelador(bp, lambda i: ["no es json", "tampoco"])
    eventos = _eventos(bp, modelador)
    mapa = eventos[-1]["mapa"]
    assert mapa["generado_por"] == "codigo" and "FalloEstructurado" in mapa["aviso"]
    assert any(e["tipo"] == "paso" and e["estado"] == "aviso" for e in eventos)
    assert mapa["proposiciones"]


def test_verificar_mapa_rechaza_ramas_y_enlaces_invalidos():
    s = SalidaMapaConceptual.model_validate(_propuesta(
        [("C1", "a")], ramas=[{"nombre": "R", "conceptos": ["C2"]}],
        proposiciones=[{"origen": "C1", "enlace": "x", "destino": "central"}]))
    with pytest.raises(ValueError, match="no elegiste"):
        mc.verificar_mapa(s, {"C1", "C2"})
    s = SalidaMapaConceptual.model_validate(_propuesta(
        [("C1", "a")], proposiciones=[{"origen": "C1", "enlace": "uno dos tres cuatro cinco seis", "destino": "central"}]))
    with pytest.raises(ValueError, match="enlace demasiado largo"):
        mc.verificar_mapa(s, {"C1"})


# ---------------------------------------------------------------- rutas

@pytest.fixture
def entorno(tmp_path, analizador):
    llamadas = []

    def mapa(prompt):
        llamadas.append(prompt)
        return "no es json"  # el Modelador falla: el mapa queda en código

    srv, _, repo = montar(tmp_path, analizador, {"modelador_mapa_v1": mapa})
    p = srv.proyectos.crear("Control escolar")
    sembrar(repo, p.proyecto_id)
    vacio = srv.proyectos.crear("Sin formalizados")
    app = como_usuario(FastAPI())
    app.include_router(artefactos.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    return TestClient(app), srv, p.proyecto_id, vacio.proyecto_id, llamadas


def _generar(cliente, pid, **cuerpo):
    r = cliente.post(f"/proyectos/{pid}/mapa-conceptual", json=cuerpo)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(x) for x in r.text.splitlines()]


def test_rutas_generan_guardan_y_reutilizan(entorno):
    cliente, srv, pid, _, llamadas = entorno
    assert cliente.get(f"/proyectos/{pid}/mapa-conceptual").json() == {"mapa": None, "requisitos": 3}

    eventos = _generar(cliente, pid)
    assert eventos[0] == {"tipo": "paso", "id": "reunir", "texto": "Reuniendo lo validado", "estado": "curso",
                          "detalle": None}
    mapa = eventos[-1]["mapa"]
    assert eventos[-1]["tipo"] == "mapa" and mapa["central"]["etiqueta"] == "Control escolar" and mapa["creado"]
    assert len(llamadas) == 2  # el intento y su reintento

    # guardado: no se vuelve a llamar al Modelador mientras lo validado no cambie
    assert cliente.get(f"/proyectos/{pid}/mapa-conceptual").json()["mapa"] == mapa
    assert _generar(cliente, pid) == [{"tipo": "mapa", "mapa": mapa}]
    assert len(llamadas) == 2
    assert len(_generar(cliente, pid, nuevo=True)) > 1 and len(llamadas) == 4

    # otra selección es otro mapa
    solo = _generar(cliente, pid, req_ids=["R02"])[-1]["mapa"]
    assert solo["requisitos"] == ["R02"]
    assert cliente.get(f"/proyectos/{pid}/mapa-conceptual?req_ids=R02").json()["mapa"] == solo

    # si cambia lo validado, el guardado ya no sirve
    srv.repo.borrar_doc("formalizados", "R03")
    assert cliente.get(f"/proyectos/{pid}/mapa-conceptual").json()["mapa"] is None

    # al borrar el proyecto se borran sus mapas
    srv.borrar_proyecto(pid)
    assert srv.repo.listar_docs(mc.COLECCION, proyecto_id=pid) == []


def test_sin_requisitos_listos_y_proyecto_ajeno(entorno):
    cliente, _, _, vacio, _ = entorno
    assert _generar(cliente, vacio) == [
        {"tipo": "error", "mensaje": "El mapa se arma con los requisitos listos. Todavía no hay ninguno."}]
    assert cliente.post("/proyectos/P999/mapa-conceptual", json={}).status_code == 404
    assert cliente.post(f"/proyectos/{vacio}/mapa-conceptual", json={"otra": 1}).status_code == 422
