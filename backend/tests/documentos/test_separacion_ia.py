"""Separación con IA (ADR 0023): el Revisor reconoce requisitos en cualquier redacción; el
código exige que salgan de sus párrafos, conserva página, marca y original, no pierde
párrafos y, si el Revisor falla, separa por patrones."""
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.revisor import Revisor
from app.api.routes import documentos, proyectos
from app.documentos import separar_texto
from app.documentos.limpieza import limpiar
from app.documentos.separacion_ia import separar_con_ia, tandas
from tests.escenarios import montar
from tests.fakes import LLMFalso, como_usuario

TEXTO = """Introducción
Este documento describe la caja de la ferretería.
1. La caja imprime el ticket al cerrar la venta.
2. Como gerente quiero ver el reporte de ventas del día.
3. Registro de proveedores con su teléfono."""


def parrafos_del_prompt(prompt) -> dict[int, str]:
    return {int(n): t for n, t in re.findall(r"^P(\d+)(?: \[p\. \d+\])? (.+)$", prompt.usuario, re.MULTILINE)}


def reconoce(prompt):
    """Como lo haría el Revisor: lo que no es título ni explicación es requisito."""
    ps = parrafos_del_prompt(prompt)
    reqs, desc = [], []
    for n, t in ps.items():
        if t.startswith(("Introducción", "Este documento")):
            desc.append({"parrafo": n, "motivo": "introducción"})
        else:
            m = re.match(r"(\d+)\s+(.*)", t)
            reqs.append({"parrafos": [n], "texto": m.group(2) if m else t, "marca": m.group(1) if m else None})
    return {"requisitos": reqs, "descartados": desc}


def _revisor(*guiones):
    """Cada guion es una respuesta o una función del prompt; se consumen en orden."""
    pendientes = list(guiones)

    def responder(prompt):
        g = pendientes.pop(0)
        return g(prompt) if callable(g) else g
    return Revisor(LLMFalso({"revisor_separacion_v1": responder}))


def _parrafos(texto=TEXTO):
    return limpiar([texto], False, False).parrafos


def test_reconoce_requisitos_sin_debe_ni_podra():
    por_patrones = separar_texto(TEXTO)
    assert por_patrones.requisitos_propuestos == []  # ninguno dice «debe» ni «podrá»
    revisor = _revisor(reconoce)
    s = separar_con_ia(_parrafos(), revisor, "Ferretería de barrio")
    assert s.metodo == "ia" and s.modelo == "llm-falso"
    assert [(r.indice, r.texto, r.marca) for r in s.requisitos_propuestos] == [
        (1, "La caja imprime el ticket al cerrar la venta.", "1"),
        (2, "Como gerente quiero ver el reporte de ventas del día.", "2"),
        (3, "Registro de proveedores con su teléfono.", "3")]
    assert s.requisitos_propuestos[0].texto_original == "1. La caja imprime el ticket al cerrar la venta."
    assert [(d.texto, d.motivo, d.detalle) for d in s.fragmentos_descartados] == [
        ("Introducción", "no_es_requisito", "introducción"),
        ("Este documento describe la caja de la ferretería.", "no_es_requisito", "introducción")]
    assert "Ferretería de barrio" in revisor.cliente.llamadas["revisor_separacion_v1"][0].usuario


def test_un_requisito_inventado_se_rechaza_y_se_reintenta():
    inventado = {"requisitos": [{"parrafos": [3], "texto": "El sistema deberá emitir facturas electrónicas al SAT."}]}
    revisor = _revisor(inventado, reconoce)
    s = separar_con_ia(_parrafos(), revisor, None)
    assert len(s.requisitos_propuestos) == 3
    reintento = revisor.cliente.llamadas["revisor_separacion_v1"][1].usuario
    assert "usa palabras que no están en sus párrafos" in reintento


def test_un_parrafo_que_no_se_uso_no_se_pierde():
    solo_uno = {"requisitos": [{"parrafos": [3], "texto": "La caja imprime el ticket al cerrar la venta."}]}
    s = separar_con_ia(_parrafos(), _revisor(solo_uno), None)
    assert len(s.requisitos_propuestos) == 1 and s.total_descartados == 4
    assert {d.detalle for d in s.fragmentos_descartados} == {None}


def test_si_el_revisor_falla_quedan_los_patrones():
    texto = "RF-01 El sistema debe registrar la venta.\nLa caja imprime el ticket."
    revisor = _revisor("no es json", "tampoco")
    s = separar_texto(texto, ia=lambda ps: separar_con_ia(ps, revisor, None))
    assert s.metodo == "patrones" and [r.texto for r in s.requisitos_propuestos] == ["El sistema debe registrar la venta."]
    assert s.advertencias[0].startswith("El Revisor no pudo separar el texto (FalloEstructurado)")


def test_tandas_acotadas():
    muchos = "\n\n".join(f"{i}. La caja registra la operación número {i} del día." for i in range(1, 130))
    ts = tandas(_parrafos(muchos))
    assert sum(len(t) for t in ts) == 129 and all(len(t) <= 60 for t in ts) and len(ts) >= 3


# ---------------------------------------------------------------- rutas

@pytest.fixture
def cliente(tmp_path, analizador):
    srv, llm, _ = montar(tmp_path, analizador, {"revisor_separacion_v1": reconoce}, separacion_ia=True)
    p = srv.proyectos.crear("Ferretería", contexto="Caja e inventario de una ferretería.", propietario="U00")
    app = como_usuario(FastAPI())
    app.include_router(documentos.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    return TestClient(app), llm, p.proyecto_id


def test_rutas(cliente):
    c, llm, pid = cliente
    r = c.post("/requisitos/separar", json={"texto": TEXTO, "proyecto_id": pid}).json()
    assert r["metodo"] == "ia" and len(r["requisitos_propuestos"]) == 3
    assert "Caja e inventario de una ferretería." in llm.llamadas["revisor_separacion_v1"][-1].usuario
    r = c.post("/requisitos/separar", json={"texto": TEXTO, "con_ia": False}).json()
    assert r["metodo"] == "patrones" and r["requisitos_propuestos"] == []
    assert c.post("/requisitos/separar", json={"texto": TEXTO, "proyecto_id": "P999"}).status_code == 404
    d = c.post(f"/proyectos/{pid}/documentos", files={"archivo": ("caja.txt", TEXTO.encode(), "text/plain")}).json()
    assert d["metodo"] == "ia" and len(d["requisitos_propuestos"]) == 3


def test_flujo_dice_lo_que_hace(cliente):
    c, _, pid = cliente
    import json
    r = c.post("/requisitos/separar/flujo", json={"texto": TEXTO, "proyecto_id": pid})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    eventos = [json.loads(x) for x in r.text.splitlines()]
    assert eventos[0] == {"tipo": "paso", "id": "limpieza", "estado": "ok", "detalle": "5 párrafos"}
    tandas_ = [e for e in eventos if e["tipo"] == "tanda"]
    assert [(e["i"], e["total"], e["estado"]) for e in tandas_] == [(1, 1, "curso"), (1, 1, "ok")]
    assert tandas_[-1]["encontrados"] == 3 and tandas_[-1]["modelo"] == "llm-falso"
    assert eventos[-1]["tipo"] == "resultado" and len(eventos[-1]["separacion"]["requisitos_propuestos"]) == 3
