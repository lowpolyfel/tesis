"""Proyectos: LEL separado por proyecto, carga en lote y recuperación tras reinicio."""
from app.models import PROYECTO_GENERAL, Estado, Validacion
from app.orchestration import checkpointer_sqlite
from tests.escenarios import SESION, guiones_sesion_cercana, montar


def test_existe_el_proyecto_general_y_se_crean_consecutivos(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {})
    assert [p.proyecto_id for p in srv.proyectos.listar()] == [PROYECTO_GENERAL]
    a = srv.proyectos.crear("Banca en línea")
    b = srv.proyectos.crear("Expediente clínico", "hospital")
    assert (a.proyecto_id, b.proyecto_id) == ("P01", "P02")
    assert srv.proyectos.actualizar("P01", descripcion="nueva").descripcion == "nueva"


def test_el_lel_es_memoria_por_proyecto(tmp_path, analizador):
    guiones = guiones_sesion_cercana()
    for clave in guiones:  # dos corridas completas del mismo requisito
        guiones[clave] = guiones[clave] * 2
    srv, llm, repo = montar(tmp_path, analizador, guiones)
    banca, salud = srv.proyectos.crear("Banca"), srv.proyectos.crear("Salud")

    r1 = srv.procesar(SESION, banca.proyecto_id)
    srv.validar(r1, Validacion(decision="aprobar"))
    assert [e.proyecto_id for e in repo.listar_lel()] == ["P01"]

    # en otro proyecto «sesión» no está resuelta: se vuelve a interpretar
    r2 = srv.procesar(SESION, salud.proyecto_id)
    filtrado = next(m for m in srv.traza(r2).mensajes if m.tipo == "filtrado").payload["terminos"]
    assert {f["termino"]: f["decision_filtro"] for f in filtrado}["sesión"] == "candidato"
    assert repo.listar_lel("P02") == [] and len(repo.listar_lel("P01")) == 1
    assert [t["req_id"] for t in srv.trazas("P02")] == [r2] and srv.traza(r2).proyecto_id == "P02"


def test_solicitar_encola_y_la_validacion_va_primero(tmp_path, analizador):
    guiones = guiones_sesion_cercana()
    for clave in guiones:
        guiones[clave] = guiones[clave] * 2
    srv, _, _ = montar(tmp_path, analizador, guiones)
    srv.cola.iniciar()
    r1 = srv.solicitar(SESION)
    assert srv.cola.esperar(10) and srv.traza(r1).estado == Estado.PENDIENTE_VALIDACION
    srv.cola.detener()  # sin trabajador: lo siguiente se queda en la cola
    r2 = srv.solicitar(SESION, srv.proyectos.crear("Otro").proyecto_id)  # otro LEL: «sesión» sigue sin resolver
    srv.solicitar_validacion(r1, Validacion(decision="aprobar"))
    assert [p["clave"] for p in srv.cola.estado()["pendientes"]] == [r1, r2]
    srv.cola.iniciar()
    assert srv.cola.esperar(10)
    assert srv.traza(r1).estado == Estado.FORMALIZADO and srv.traza(r2).estado == Estado.PENDIENTE_VALIDACION
    srv.cola.detener()


def test_recupera_lo_que_quedo_en_cola_al_reiniciar(tmp_path, analizador):
    cp = lambda: checkpointer_sqlite(tmp_path / "cp.sqlite")  # noqa: E731
    srv, _, _ = montar(tmp_path, analizador, guiones_sesion_cercana(), checkpointer=cp())
    pendiente = srv.registrar(SESION)  # registrado pero nunca ejecutado (se "cayó" el servidor)

    srv2, _, _ = montar(tmp_path, analizador, guiones_sesion_cercana(), checkpointer=cp())
    srv2.iniciar()
    assert srv2.cola.esperar(10)
    assert srv2.traza(pendiente).estado == Estado.PENDIENTE_VALIDACION
    assert srv2.recuperar() == []  # lo que espera validación no se vuelve a encolar
    srv2.detener()
