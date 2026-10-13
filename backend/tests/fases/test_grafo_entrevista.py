"""La fase del LEL (ADR 0024): de la entrevista al LEL propuesto, con debate y memoria."""
import pytest

from app.entrevistas.turnos import leer_texto
from app.fases.lexico import Lexico
from app.models import CambiosEntradaLexico
from tests.fases.escenario import ENTREVISTA, montar


@pytest.fixture
def escenario(tmp_path, analizador):
    return montar(tmp_path, analizador)


def procesar(srv, proyecto, texto=ENTREVISTA, titulo="Dra. Ruiz"):
    return srv.entrevistas.procesar(proyecto.proyecto_id, titulo, leer_texto(texto))


def test_la_entrevista_deja_un_lel_propuesto_con_intenciones(escenario):
    srv, llm, p = escenario
    eid = procesar(srv, p)
    doc = srv.entrevistas.almacen.obtener(eid)
    assert doc["estado"] == "lista", doc.get("error")
    assert doc["ficha"]["necesidades"][1]["turnos"] == [5]  # el turno 99 no existe: se quita
    assert doc["vaguedad"] == [{"expresion": "ahorita", "turnos": [3]}]

    entradas = {e["simbolo"]: e for e in Lexico(srv.repo).listar(p.proyecto_id)}
    assert set(entradas) == {"consulta", "paciente", "asistente", "cita", "expediente", "receta", "dar de alta"}
    assert all(e["estado"] == "propuesto" for e in entradas.values())
    assert entradas["paciente"]["tipo"] == "sujeto"
    assert {c["turno"] for c in entradas["consulta"]["citas"]} == {3, 6, 7}  # «consulta» y «consultas»
    assert entradas["dar de alta"]["marcas"]["regional"] and entradas["dar de alta"]["via"] == "aceptado_directo"
    amb = entradas["consulta"]["ambiguedad"]
    assert amb["via"] == "arbitraje" and amb["rondas"] == 2 and amb["elegida"] == "I1"
    assert [a["significado"] for a in amb["alternativas"]] == ["cita médica con un paciente", "búsqueda en la base de datos"]
    assert entradas["receta"]["via"] == "univoco" and entradas["receta"]["ambiguedad"] is None
    assert "teletransportador" not in str(entradas)

    tipos = [m["tipo"] for m in srv.entrevistas.almacen.bitacora(eid)["mensajes"]]
    assert tipos[:4] == ["ficha", "extraccion", "filtrado", "interpretaciones"]
    assert {"similitud", "objecion", "refinamiento", "arbitraje", "formalizacion"} <= set(tipos)
    assert doc["resumen"]["arbitradas"] == 1 and doc["resumen"]["nuevas"] == 7


def test_lo_que_la_persona_corrige_se_aprende_y_se_usa_en_la_siguiente_entrevista(escenario):
    srv, llm, p = escenario
    procesar(srv, p)
    lexico = Lexico(srv.repo)
    por = {e["simbolo"]: e for e in lexico.listar(p.proyecto_id)}
    lexico.corregir(por["consulta"], CambiosEntradaLexico(intencion="Registrar la atención médica de cada paciente"),
                    "2026-10-13")
    lexico.descartar(por["receta"], "2026-10-13", motivo="no es del sistema")
    acuerdos = {a["simbolo"]: a for a in lexico.memoria.listar(p.proyecto_id)}
    assert acuerdos["consulta"]["significa"] == "Registrar la atención médica de cada paciente"
    assert "búsqueda en la base de datos" in acuerdos["consulta"]["no_significa"]
    assert acuerdos["receta"]["descartado"]

    llamadas = len(llm.llamadas["clasificador_intencion_v1"])
    eid2 = procesar(srv, p, "Doctora: Las consultas de los martes son de revisión. La receta va impresa.", "Segunda")
    assert srv.entrevistas.almacen.obtener(eid2)["estado"] == "lista"
    assert len(llm.llamadas["clasificador_intencion_v1"]) == llamadas  # nada nuevo que interpretar
    filtrado = next(m for m in srv.entrevistas.almacen.bitacora(eid2)["mensajes"] if m["tipo"] == "filtrado")
    decisiones = {t["termino"]: t["decision_filtro"] for t in filtrado["payload"]["terminos"]}
    assert decisiones["consultas"] == "resuelto_por_lel" and decisiones["receta"] == "descartado_por_persona"
    consulta = next(e for e in lexico.listar(p.proyecto_id) if e["simbolo"] == "consulta")
    assert eid2 in consulta["entrevistas"] and consulta["estado"] == "corregido"
    assert consulta["intencion"] == "Registrar la atención médica de cada paciente"


def test_cancelar_y_volver_a_procesar(escenario):
    srv, _, p = escenario
    doc = srv.entrevistas.registrar(p.proyecto_id, "X", leer_texto(ENTREVISTA), {"tipo": "texto"})
    eid = doc["entrevista_id"]
    srv.entrevistas._cancelados.add(eid)
    srv.entrevistas.ejecutar(eid)
    assert srv.entrevistas.almacen.obtener(eid)["estado"] == "cancelada"
    assert Lexico(srv.repo).listar(p.proyecto_id) == []
    srv.cola.iniciar()
    try:
        assert srv.entrevistas.reprocesar(eid)["corrida"] == 2
        srv.cola.esperar(10)
    finally:
        srv.cola.detener()
    assert srv.entrevistas.almacen.obtener(eid)["estado"] == "lista"
    assert len(Lexico(srv.repo).listar(p.proyecto_id)) == 7


def test_borrar_la_entrevista_quita_lo_que_solo_ella_proponia(escenario):
    srv, _, p = escenario
    eid = procesar(srv, p)
    lexico = Lexico(srv.repo)
    consulta = next(e for e in lexico.listar(p.proyecto_id) if e["simbolo"] == "consulta")
    lexico.validar(consulta, "2026-10-13")
    assert srv.entrevistas.borrar(eid) == {"borradas": 6, "conservadas": 1}
    quedan = lexico.listar(p.proyecto_id)
    assert [e["simbolo"] for e in quedan] == ["consulta"] and quedan[0]["citas"] == []
