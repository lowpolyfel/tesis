"""Ficha del contexto y triaje de requisitos (ADR 0022): reglas en código, el Revisor con
un LLM falso, la revisión humana obligatoria en el grafo y las rutas."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import contexto, proyectos
from app.contexto import a_markdown, triar
from app.models import Estado, Interpretacion, Validacion
from tests.escenarios import SESION, guiones_sesion_cercana, montar
from tests.fakes import como_usuario, interp

FICHA = {"resumen": "Punto de venta de una ferretería.", "objetivo": "Cobrar y controlar el inventario.",
         "actores": [{"nombre": "Cajero", "rol": "Cobra las ventas."}],
         "conceptos": [{"termino": "existencia", "significado": "Piezas de un producto en el almacén."}],
         "procesos": ["Cobrar una venta"], "reglas": ["No se vende sin existencias."], "fuera_de_alcance": [],
         "vacios": ["No dice si hay ventas a crédito."]}


def veredictos(*vs):
    return {"requisitos": [{"indice": i, "veredicto": v, "motivo": f"motivo {i}",
                            "faltantes": [] if v == "claro" else ["quién"],
                            "preguntas": [] if v == "claro" else ["¿Quién lo hace?"],
                            "terminos_ambiguos": ["rápido"] if v == "ambiguo" else []} for i, v in enumerate(vs, 1)]}


class RevisorFalso:
    def __init__(self, *salidas):
        from app.agents.revisor import Revisor
        from tests.fakes import LLMFalso
        self.llm = LLMFalso({"revisor_triaje_v1": list(salidas), "revisor_ficha_v1": [FICHA]})
        self.revisor = Revisor(self.llm)

    def triar(self, ficha, requisitos):
        return self.revisor.triar(ficha, requisitos)


def test_markdown_de_la_ficha():
    md = a_markdown("Ferretería", FICHA)
    assert md.startswith("# Ferretería\n\nPunto de venta de una ferretería.")
    assert "## Conceptos del dominio\n\n- **existencia**: Piezas de un producto en el almacén." in md
    assert "## Lo que el contexto no dice\n\n- No dice si hay ventas a crédito." in md
    assert "Fuera de alcance" not in md  # las secciones vacías no salen


def test_triaje_con_reglas_y_revisor():
    textos = ["El cajero debe registrar cada venta con sus productos.", "Rápido.",
              "El sistema debe responder rápido al buscar productos."]
    r = RevisorFalso(veredictos("claro", "ambiguo"))
    salida = triar(textos, "# ficha", r)
    assert [x["veredicto"] for x in salida["resultados"]] == ["claro", "incompleto", "ambiguo"]
    assert [x["origen"] for x in salida["resultados"]] == ["revisor", "regla", "revisor"]
    assert salida["resultados"][2]["indice"] == 3 and salida["resultados"][2]["terminos_ambiguos"] == ["rápido"]
    assert salida["modelo"] == "llm-falso" and salida["aviso"] is None
    prompt = r.llm.llamadas["revisor_triaje_v1"][0].usuario
    assert "# ficha" in prompt and "2. El sistema debe responder rápido" in prompt and "Rápido." not in prompt


def test_si_falta_un_requisito_se_reintenta_y_si_falla_no_inventa():
    textos = ["El cajero debe registrar cada venta.", "El gerente debe consultar el reporte."]
    r = RevisorFalso(veredictos("claro"), veredictos("claro", "claro"))
    assert [x["veredicto"] for x in triar(textos, None, r)["resultados"]] == ["claro", "claro"]
    assert "un resultado por requisito" in r.llm.llamadas["revisor_triaje_v1"][1].usuario
    salida = triar(textos, None, RevisorFalso("no es json", "tampoco"))
    assert [x["veredicto"] for x in salida["resultados"]] == [None, None]
    assert "Revisa estos requisitos tú" in salida["aviso"]


def test_un_requisito_ambiguo_espera_a_una_persona_aunque_no_haga_falta(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": [{"terminos": [{"termino": "sistema", "categoria_tentativa": "sujeto"}]}] * 2,
        "clasificador_v3": [{"resultados": [{"termino": "sistema", "univoco": True}]}] * 2,
    }, validacion_humana="nunca")
    claro = srv.registrar(SESION, triaje={"veredicto": "claro"})
    srv.ejecutar(claro)
    assert srv.traza(claro).estado == Estado.FORMALIZADO
    ambiguo = srv.registrar(SESION, triaje={"veredicto": "ambiguo", "motivo": "«registrar» es vago"})
    srv.ejecutar(ambiguo)
    t = srv.traza(ambiguo)
    assert t.estado == Estado.PENDIENTE_VALIDACION and t.config["triaje"]["motivo"] == "«registrar» es vago"
    srv.validar(ambiguo, Validacion(decision="aprobar"))  # sin términos que elegir: la persona lo aprueba
    assert srv.traza(ambiguo).estado == Estado.FORMALIZADO


def test_ambiguo_con_terminos_tambien_espera(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, guiones_sesion_cercana(), validacion_humana="si_hay_arbitraje")
    req = srv.registrar(SESION, triaje={"veredicto": "incompleto", "forzado": True})
    srv.ejecutar(req)
    assert srv.traza(req).estado == Estado.PENDIENTE_VALIDACION
    srv.validar(req, Validacion(decision="aprobar",
                                interpretaciones_editadas={"sesión": Interpretacion(**interp("I1", "periodo", "…"))}))
    assert srv.traza(req).estado == Estado.FORMALIZADO


# ---------------------------------------------------------------- rutas

@pytest.fixture
def entorno(tmp_path, analizador):
    llm_guiones = {"revisor_ficha_v1": [FICHA, FICHA], "revisor_triaje_v1": [veredictos("claro", "incompleto")]}
    srv, llm, _ = montar(tmp_path, analizador, llm_guiones)
    p = srv.proyectos.crear("Ferretería", contexto="Punto de venta de una ferretería de barrio.",
                            propietario="U00")
    sin = srv.proyectos.crear("Sin contexto", propietario="U00")
    app = como_usuario(FastAPI())
    app.include_router(contexto.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    return TestClient(app), srv, llm, p.proyecto_id, sin.proyecto_id


def test_rutas_de_la_ficha_y_el_triaje(entorno):
    c, srv, llm, pid, sin = entorno
    assert c.get(f"/proyectos/{pid}/ficha").json() == {"ficha": None, "al_dia": False, "tiene_contexto": True}

    # el triaje arma la ficha si no está al día y luego compara
    r = c.post(f"/proyectos/{pid}/triaje", json={"requisitos": [
        "El cajero debe registrar cada venta.", "El sistema debe hacer reportes."]}).json()
    assert [x["veredicto"] for x in r["resultados"]] == ["claro", "incompleto"]
    assert r["ficha"]["al_dia"] is True and len(llm.llamadas["revisor_ficha_v1"]) == 1
    assert "Punto de venta de una ferretería." in llm.llamadas["revisor_triaje_v1"][0].usuario

    ficha = c.get(f"/proyectos/{pid}/ficha").json()
    assert ficha["al_dia"] and ficha["ficha"]["markdown"].startswith("# Ferretería")
    # editar el contexto la deja vieja; POST la rehace
    c.patch(f"/proyectos/{pid}", json={"contexto": "Punto de venta e inventario de una ferretería."})
    assert c.get(f"/proyectos/{pid}/ficha").json()["al_dia"] is False
    assert c.post(f"/proyectos/{pid}/ficha").json()["al_dia"] is True
    assert c.post(f"/proyectos/{sin}/ficha").status_code == 422

    # el veredicto viaja con el requisito y queda en su traza
    r = c.post(f"/proyectos/{pid}/requisitos", json={"requisitos": [
        {"texto": "El sistema debe hacer reportes de ventas por día.",
         "triaje": {"veredicto": "incompleto", "motivo": "No dice cuáles", "precisado": True}}]})
    assert r.status_code == 202
    t = srv.repo.obtener_traza(r.json()["req_ids"][0])
    assert t.config["triaje"]["veredicto"] == "incompleto" and t.config["triaje"]["precisado"] is True

