"""Recuperación tras una caída en los puntos delicados del flujo, ciclos sin carreras y la
entrada del LEL que dice qué hizo la persona con la propuesta.

La caída se simula con una excepción que no hereda de `Exception` (los nodos no la
atrapan, igual que no atraparían la muerte del proceso) y un servicio nuevo sobre los
mismos archivos (trazas JSON y checkpoints SQLite).
"""
import threading
import time

import pytest

from app.models import Estado, Interpretacion, Validacion
from app.orchestration import ConflictoDeEstado, checkpointer_sqlite
from tests.escenarios import EXTRACCION_SESION, I1, I2, MODELADO, SESION, clasificacion, guiones_sesion_cercana, montar
from tests.fakes import r3_todas


class Caida(BaseException):
    """El proceso murió aquí."""


def arrancar(tmp_path, analizador, guiones=None):
    return montar(tmp_path, analizador, guiones or guiones_sesion_cercana(),
                  checkpointer=checkpointer_sqlite(tmp_path / "cp.sqlite"))


def caer_en(repo, metodo: str, cuando):
    """Hace que `repo.<metodo>` muera, sin escribir, cuando `cuando(*args)`."""
    original = getattr(repo, metodo)

    def envuelto(*args, **kw):
        if cuando(*args):
            raise Caida(metodo)
        return original(*args, **kw)

    setattr(repo, metodo, envuelto)


def reiniciar(tmp_path, analizador):
    srv, _, repo = arrancar(tmp_path, analizador)
    srv.iniciar()
    assert srv.cola.esperar(10)
    return srv, repo


def tipos(traza):
    return [m.tipo.value for m in traza.mensajes]


def test_una_validacion_aceptada_sobrevive_al_reinicio(tmp_path, analizador):
    srv, _, _ = arrancar(tmp_path, analizador)
    req = srv.procesar(SESION)
    # la API la aceptó (202) y quedó esperando turno; el proceso se reinicia antes de aplicarla
    srv.solicitar_validacion(req, Validacion(decision="aprobar", comentario="de acuerdo"))

    srv2, repo2 = reiniciar(tmp_path, analizador)
    t = srv2.traza(req)
    assert t.estado == Estado.FORMALIZADO
    assert next(m for m in t.mensajes if m.tipo == "validacion").payload["comentario"] == "de acuerdo"
    assert len(repo2.listar_lel()) == 1
    assert srv2.recuperar() == []  # aplicada: ya no se vuelve a encolar
    srv2.detener()


def test_sin_validacion_aceptada_sigue_esperando(tmp_path, analizador):
    srv, _, _ = arrancar(tmp_path, analizador)
    req = srv.procesar(SESION)
    srv2, _ = reiniciar(tmp_path, analizador)
    assert srv2.traza(req).estado == Estado.PENDIENTE_VALIDACION and srv2.recuperar() == []
    srv2.detener()


def test_caida_al_entrar_a_pendiente_validacion_antes_del_checkpoint(tmp_path, analizador):
    srv, _, repo = arrancar(tmp_path, analizador)
    original = repo.cambiar_estado

    def escribir_y_caer(req_id, estado):
        original(req_id, estado)
        if estado == Estado.PENDIENTE_VALIDACION:
            raise Caida("tras cambiar el estado")

    repo.cambiar_estado = escribir_y_caer
    with pytest.raises(Caida):
        srv.procesar(SESION)

    srv2, _ = reiniciar(tmp_path, analizador)
    assert srv2.grafo.get_state({"configurable": {"thread_id": "R01"}}).next == ("humano",)
    srv2.validar("R01", Validacion(decision="aprobar"))  # antes: ConflictoDeEstado para siempre
    assert srv2.traza("R01").estado == Estado.FORMALIZADO
    srv2.detener()


def test_caida_entre_la_validacion_y_validado(tmp_path, analizador):
    srv, _, repo = arrancar(tmp_path, analizador)
    req = srv.procesar(SESION)
    caer_en(repo, "cambiar_estado", lambda req_id, estado: estado == Estado.VALIDADO)
    with pytest.raises(Caida):
        srv.validar(req, Validacion(decision="aprobar", comentario="sí"))
    assert tipos(srv.traza(req))[-1] == "validacion"  # la decisión ya está en la traza

    srv2, repo2 = reiniciar(tmp_path, analizador)
    t = srv2.traza(req)
    assert t.estado == Estado.FORMALIZADO and tipos(t).count("validacion") == 1
    assert len(repo2.listar_lel()) == 1
    with pytest.raises(ConflictoDeEstado):
        srv2.validar(req, Validacion(decision="aprobar"))
    srv2.detener()


def test_caida_en_formalizado_no_duplica_el_lel(tmp_path, analizador):
    srv, _, repo = arrancar(tmp_path, analizador)
    req = srv.procesar(SESION)
    caer_en(repo, "guardar_doc", lambda coleccion, *a: coleccion == "formalizados")  # el LEL ya se guardó
    with pytest.raises(Caida):
        srv.validar(req, Validacion(decision="aprobar"))
    assert len(repo.listar_lel()) == 1

    srv2, repo2 = reiniciar(tmp_path, analizador)
    assert srv2.traza(req).estado == Estado.FORMALIZADO
    assert [(e.simbolo, e.req_id) for e in repo2.listar_lel()] == [("sesión", req)]
    srv2.detener()


def test_dos_cargas_simultaneas_abren_ciclos_distintos(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, {})
    p = srv.proyectos.crear("Cargas").proyecto_id
    original = repo.listar_trazas

    def lento(proyecto_id=None):
        r = original(proyecto_id)
        time.sleep(0.2)  # ensancha la ventana entre leer el último ciclo y abrir el siguiente
        return r

    repo.listar_trazas = lento
    ciclos = []
    hilos = [threading.Thread(target=lambda t=t: ciclos.append(srv.solicitar_lote([(t, None)], p)[0]))
             for t in ("uno", "dos")]
    hilos.append(threading.Thread(target=lambda: ciclos.append(srv.traza(srv.solicitar("tres", p)).ciclo)))
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(ciclos) == [1, 2, 3]


def test_la_entrada_del_lel_dice_que_hizo_la_persona(tmp_path, analizador):
    sin_cambios = {"interpretaciones": [I1, I2]}
    srv, _, repo = montar(tmp_path, analizador, {
        "extractor_v1": [EXTRACCION_SESION],
        "clasificador_v3": [clasificacion(I1, I2)],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [sin_cambios, sin_cambios],
        "critico_arbitraje_v2": [{"interpretacion_elegida": "I1", "justificacion_por_regla": [
            {"regla": r, "argumento": f"argumento {r}"} for r in ("R1", "R2", "R3")]}],
        "modelador_v2": [MODELADO],
    })
    req = srv.procesar(SESION)
    # el arbitraje propuso I1; la persona elige I2
    srv.validar(req, Validacion(decision="aprobar", interpretaciones_editadas={"sesión": Interpretacion(**I2)}))
    e = repo.listar_lel()[0]
    assert (e.via, e.interpretacion.id, e.cambio, e.editada_por_humano) == ("arbitraje", "I2", "eleccion", False)


@pytest.mark.parametrize("edicion,cambio", [(None, "ninguno"),
                                            (Interpretacion(id="I1", significado="otra", parafrasis_del_requisito="x"),
                                             "edicion")])
def test_cambio_en_el_lel_al_aceptar_o_reescribir(tmp_path, analizador, edicion, cambio):
    srv, _, repo = montar(tmp_path, analizador, guiones_sesion_cercana())
    req = srv.procesar(SESION)
    srv.validar(req, Validacion(decision="aprobar", interpretaciones_editadas={"sesión": edicion} if edicion else {}))
    e = repo.listar_lel()[0]
    assert (e.via, e.cambio, e.editada_por_humano) == ("aceptado_directo", cambio, cambio == "edicion")


def test_una_validacion_de_otra_corrida_no_se_aplica_a_un_requisito_nuevo(tmp_path, analizador):
    """Si se vacían las trazas y los checkpoints, el id R01 se reutiliza: la validación que
    alguien aceptó para el R01 anterior no debe aplicarse sola al nuevo."""
    import shutil

    srv, _, _ = arrancar(tmp_path, analizador)
    req = srv.procesar(SESION)
    srv.solicitar_validacion(req, Validacion(decision="aprobar", comentario="validación de la corrida VIEJA"))
    shutil.rmtree(tmp_path / "resultados" / "trazas")
    (tmp_path / "resultados" / "lel.json").unlink(missing_ok=True)
    (tmp_path / "cp.sqlite").unlink()

    nuevo, _, _ = arrancar(tmp_path, analizador)
    assert nuevo.procesar(SESION) == req  # el mismo id, otra corrida

    srv2, _ = reiniciar(tmp_path, analizador)
    t = srv2.traza(req)
    assert t.estado == Estado.PENDIENTE_VALIDACION and "validacion" not in tipos(t)
    srv2.validar(req, Validacion(decision="aprobar", comentario="la de ahora"))
    assert next(m for m in srv2.traza(req).mensajes if m.tipo == "validacion").payload["comentario"] == "la de ahora"
    srv2.detener()


def test_checkpoint_sin_next_pero_con_tareas_pendientes_se_continua(tmp_path, analizador):
    """El checkpoint se guarda en segundo plano y puede ir detrás del repositorio: tras una
    caída puede quedar sin `next` pero con tareas pendientes. Antes se saltaba y el
    requisito quedaba atascado (POST /validar respondía 409 para siempre)."""
    srv, _, repo = arrancar(tmp_path, analizador)
    req = srv.procesar(SESION)
    caer_en(repo, "cambiar_estado", lambda req_id, estado: estado == Estado.VALIDADO)
    with pytest.raises(Caida):
        srv.validar(req, Validacion(decision="aprobar"))

    srv2, _, _ = arrancar(tmp_path, analizador)
    real = srv2.grafo.get_state

    def rezagado(config, *a, **kw):
        s = real(config, *a, **kw)
        return s._replace(next=()) if s.tasks else s

    srv2.grafo.get_state = rezagado
    assert srv2.recuperar() == [req]
    srv2.grafo.get_state = real
    srv2.cola.iniciar()
    assert srv2.cola.esperar(10)
    t = srv2.traza(req)
    assert t.estado == Estado.FORMALIZADO and tipos(t).count("validacion") == 1
    srv2.detener()
