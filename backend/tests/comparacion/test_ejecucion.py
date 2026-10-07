"""Corrida completa de la comparación con LLM falso por par y embeddings con vectores elegidos."""
import pytest

from app.comparacion import COLECCION, RequisitosInsuficientes, comparar, ejecutar, listar, obtener, preparar, recuperar
from app.models import Estado, Origen
from tests.comparacion.ayudantes import (
    entrada_lel,
    juicio,
    montar_comparacion,
    requisito,
    resolucion,
    validar_a_mano,
)

CIERRE_15 = "La sesión del usuario debe cerrarse a los 15 minutos de inactividad."
SIN_CIERRE = "La sesión del usuario nunca debe cerrarse automáticamente."
REGISTRAR = "El sistema debe registrar la sesión del usuario."
REGISTRAR_2 = "El sistema tiene que registrar la sesión de cada usuario."
CORREOS = "La aplicación enviará correos de aviso."


@pytest.mark.parametrize("cita_b, verificada_b", [
    ("«Nunca debe cerrarse automaticamente.»", True),  # literal salvo mayúsculas, acentos y comillas
    ("la sesión jamás se cierra sola", False),  # paráfrasis: se registra como no verificada, no se descarta
])
def test_contradiccion_con_citas(tmp_path, analizador, cita_b, verificada_b):
    juicios = {("R01", "R02"): juicio("contradiccion", "la sesion del usuario debe cerrarse a los 15 minutos", cita_b,
                                      "A pide cerrar la sesión por inactividad y B prohíbe cerrarla sola.")}
    srv, llm, repo, pid = montar_comparacion(tmp_path, analizador, juicios=juicios,
                                             vectores={CIERRE_15: [1, 0, 0], SIN_CIERRE: [0.8, 0.6, 0]})
    requisito(repo, pid, CIERRE_15)
    requisito(repo, pid, SIN_CIERRE)

    c = comparar(srv, pid)

    assert c.estado == "terminada" and c.error is None and c.terminado is not None
    assert [(r.req_id, r.base) for r in c.requisitos] == [("R01", "original"), ("R02", "original")]
    assert c.matriz_similitud == {"R01-R02": pytest.approx(0.8)}
    assert (c.pares_totales, c.pares_candidatos, c.pares_evaluados, c.pares_fuera_por_limite) == (1, 1, 1, 0)
    assert c.config.model_dump() == {"umbral_relacion": 0.6, "umbral_duplicado": 0.92, "max_pares": 60,
                                     "modelo": "llm-falso", "prompt_version": "comparador_v1",
                                     "modelo_embeddings": "embeddings-falsos"}
    [h] = c.hallazgos
    assert (h.id, h.tipo, h.fuente, h.requisitos) == ("H1", "contradiccion", "llm", ["R01", "R02"])
    assert (h.modelo, h.prompt_version, h.similitud) == ("llm-falso", "comparador_v1", pytest.approx(0.8))
    assert [(e.req_id, e.verificada) for e in h.evidencia] == [("R01", True), ("R02", verificada_b)]
    assert h.evidencia[1].cita == cita_b
    assert {"sesión", "usuario"} <= set(h.terminos)
    [rel] = c.relaciones_por_par
    assert (rel.par, rel.relacion, rel.motivos, rel.error) == ("R01-R02", "contradiccion", ["similitud", "lema"], None)
    [prompt] = llm.llamadas["comparador_v1"]
    assert f"Requisito A (R01):\n«{CIERRE_15}»" in prompt.usuario and f"«{SIN_CIERRE}»" in prompt.usuario
    assert obtener(srv, c.comparacion_id) == c  # lo devuelto es lo guardado


def test_casi_duplicado_y_redundancia(tmp_path, analizador):
    juicios = {("R01", "R02"): juicio("redundancia", "registrar la sesión", "registrar la sesión")}
    srv, llm, repo, pid = montar_comparacion(
        tmp_path, analizador, juicios=juicios,
        vectores={REGISTRAR: [1, 0, 0], REGISTRAR_2: [0.98, 0.199, 0], CORREOS: [0, 0, 1]})
    for texto in (REGISTRAR, REGISTRAR_2, CORREOS):
        requisito(repo, pid, texto)

    c = comparar(srv, pid)

    assert [(h.id, h.tipo, h.fuente, h.requisitos) for h in c.hallazgos] == [
        ("H1", "casi_duplicado", "embeddings", ["R01", "R02"]), ("H2", "redundancia", "llm", ["R01", "R02"])]
    dup = c.hallazgos[0]
    assert dup.similitud == pytest.approx(0.98, abs=1e-3) and dup.modelo == "embeddings-falsos"
    assert [e.cita for e in dup.evidencia] == [REGISTRAR, REGISTRAR_2]
    # CORREOS no se parece ni comparte términos con los otros: no pasa al juez
    assert (c.pares_totales, c.pares_candidatos, c.pares_evaluados) == (3, 1, 1)
    assert len(llm.llamadas["comparador_v1"]) == 1


def test_corte_por_max_pares_se_reporta(tmp_path, analizador):
    textos = ["El sistema debe registrar la sesión del usuario.", "El sistema debe guardar la bitácora de accesos.",
              "El sistema debe enviar un correo al administrador.", "El sistema debe generar un reporte mensual."]
    vectores = dict(zip(textos, [[1, 0, 0], [0.9, 0.4359, 0], [0.5, 0.866, 0], [0, 0, 1]]))
    srv, llm, repo, pid = montar_comparacion(tmp_path, analizador, vectores=vectores, comparacion_max_pares=2)
    for t in textos:
        requisito(repo, pid, t)

    c = comparar(srv, pid)

    # todos comparten «sistema»: los 6 pares son candidatos y solo los 2 más parecidos van al juez
    assert (c.pares_totales, c.pares_candidatos, c.pares_evaluados, c.pares_fuera_por_limite) == (6, 6, 2, 4)
    assert [r.par for r in c.relaciones_por_par] == ["R01-R02", "R02-R03"]
    assert [(p.par, p.motivos) for p in c.fuera_por_limite] == [
        ("R01-R03", ["lema"]), ("R01-R04", ["lema"]), ("R02-R04", ["lema"]), ("R03-R04", ["lema"])]
    assert len(llm.llamadas["comparador_v1"]) == 2
    assert c.avance.model_dump() == {"hechos": 2, "total": 2}
    assert c.hallazgos == []  # independientes y ningún par sobre el umbral de duplicado


def test_inconsistencia_de_vocabulario_desde_el_lel(tmp_path, analizador):
    textos = ["El sistema debe registrar la sesión del usuario al entrar.",
              "El sistema debe cerrar la sesión del usuario al salir.",
              "El reporte mensual debe contar cada sesión."]
    srv, llm, repo, pid = montar_comparacion(
        tmp_path, analizador, vectores=dict(zip(textos, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])))
    r1 = requisito(repo, pid, textos[0], Estado.FORMALIZADO, reescrito=textos[0],
                   resoluciones=[resolucion("sesión", "periodo de uso")])
    r2 = requisito(repo, pid, textos[1], Estado.FORMALIZADO, reescrito=textos[1],
                   resoluciones=[resolucion("sesión", "evento de conexión")])
    r3 = requisito(repo, pid, textos[2], Estado.FORMALIZADO, reescrito=textos[2],
                   resoluciones=[resolucion("sesión", "periodo de uso")])
    otro = srv.proyectos.crear("Otro dominio").proyecto_id
    repo.guardar_lel([entrada_lel(pid, r1, "sesión", ["Periodo de uso del sistema."]),
                      entrada_lel(pid, r2, "sesión", ["Evento de conexión al sistema."]),
                      entrada_lel(pid, r3, "Sesión", ["Periodo de uso del sistema"]),
                      entrada_lel(otro, "R09", "sesión", ["Algo distinto en otro proyecto."])])

    c = comparar(srv, pid)

    vocab = [h for h in c.hallazgos if h.tipo == "inconsistencia_vocabulario"]
    assert [(h.requisitos, h.fuente, h.terminos) for h in vocab] == [
        (["R01", "R02"], "lel", ["sesión"]), (["R02", "R03"], "lel", ["sesión"])]
    assert "también difiere" in vocab[0].explicacion and vocab[0].similitud == 0.0
    assert [r.base for r in c.requisitos] == ["reescrito"] * 3
    # el símbolo del LEL hace candidatos a los tres pares aunque los vectores sean ortogonales
    assert all("simbolo_lel" in r.motivos and "sesión" in r.compartidos for r in c.relaciones_por_par)
    assert c.pares_evaluados == 3


def test_inconsistencia_por_validacion_sin_lel(tmp_path, analizador):
    textos = ["El sistema debe jalar los datos del servidor.", "El módulo debe jalar las facturas.",
              "El administrador revisa el reporte y él lo firma.", "El usuario envía la solicitud y él la cancela.",
              "El sistema debe jalar los pedidos."]
    srv, llm, repo, pid = montar_comparacion(
        tmp_path, analizador, vectores=dict(zip(textos, [[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [0, 1, 1]])))
    ids = [requisito(repo, pid, t, e) for t, e in zip(textos, [Estado.VALIDADO, Estado.VALIDADO, Estado.VALIDADO,
                                                            Estado.VALIDADO, Estado.RECHAZADO])]
    validar_a_mano(repo, ids[0], "jalar", "consultar")
    validar_a_mano(repo, ids[1], "jalar", "descargar")
    validar_a_mano(repo, ids[2], "él", "el administrador", tipo="anaforica")  # referentes propios de cada requisito
    validar_a_mano(repo, ids[3], "él", "el usuario", tipo="anaforica")
    validar_a_mano(repo, ids[4], "jalar", "procesar", decision="rechazar")

    c = comparar(srv, pid)

    vocab = [h for h in c.hallazgos if h.tipo == "inconsistencia_vocabulario"]
    assert [(h.requisitos, h.fuente, h.terminos) for h in vocab] == [(["R01", "R02"], "validacion", ["jalar"])]
    assert [e.cita for e in vocab[0].evidencia] == ["consultar", "descargar"]
    assert [(e.req_id, e.motivo) for e in c.excluidos] == [("R05", "rechazado")]


def test_falla_del_llm_en_un_par_no_tumba_la_comparacion(tmp_path, analizador):
    textos = ["El sistema debe registrar la sesión del usuario.", "El sistema debe cerrar la sesión del usuario.",
              "El sistema debe borrar la sesión del usuario."]
    larga = juicio("redundancia", "registrar", "borrar", " ".join(["palabra"] * 61))
    respuestas_r02_r03 = [larga, juicio("contradiccion", "cerrar la sesión", "borrar la sesión")]

    def caida(prompt):
        raise ConnectionError("Ollama no responde")

    juicios = {("R01", "R02"): "esto no es JSON", ("R01", "R03"): caida,
               ("R02", "R03"): lambda prompt: respuestas_r02_r03.pop(0)}
    srv, llm, repo, pid = montar_comparacion(
        tmp_path, analizador, juicios=juicios,
        vectores=dict(zip(textos, [[1, 0, 0], [0.9, 0.4359, 0], [0.6, 0, 0.8]])))
    for t in textos:
        requisito(repo, pid, t)

    c = comparar(srv, pid)

    assert c.estado == "terminada" and c.pares_evaluados == 3 and c.pares_con_error == 2
    por_par = {r.par: r for r in c.relaciones_por_par}
    assert por_par["R01-R02"].relacion is None and por_par["R01-R02"].error.excepcion == "FalloEstructurado"
    assert len(por_par["R01-R02"].error.intentos) == 2  # el reintento también falló; quedan las dos salidas
    assert por_par["R01-R03"].error.model_dump() == {"excepcion": "ConnectionError", "mensaje": "Ollama no responde",
                                                     "intentos": []}
    # la explicación de 61 palabras no validó; el reintento sí
    assert por_par["R02-R03"].relacion == "contradiccion" and por_par["R02-R03"].error is None
    assert [(h.tipo, h.requisitos) for h in c.hallazgos] == [("contradiccion", ["R02", "R03"])]


def test_falla_de_embeddings_deja_la_comparacion_en_error(tmp_path, analizador):
    class EmbeddingsCaidos:
        modelo = "caidos"

        def vectorizar(self, textos):
            raise ConnectionError("sin servidor de embeddings")

    srv, llm, repo, pid = montar_comparacion(tmp_path, analizador)
    r1 = requisito(repo, pid, "El sistema debe jalar los datos.", Estado.VALIDADO)
    r2 = requisito(repo, pid, "El módulo debe jalar las facturas.", Estado.VALIDADO)
    validar_a_mano(repo, r1, "jalar", "consultar")
    validar_a_mano(repo, r2, "jalar", "descargar")
    srv.deps.embeddings = EmbeddingsCaidos()

    c = comparar(srv, pid)

    assert c.estado == "error" and c.error.model_dump() == {"excepcion": "ConnectionError",
                                                            "mensaje": "sin servidor de embeddings"}
    # lo determinista que ya se calculó se conserva
    assert [h.tipo for h in c.hallazgos] == ["inconsistencia_vocabulario"] and c.hallazgos[0].similitud is None
    assert obtener(srv, c.comparacion_id).estado == "error"


def test_menos_de_dos_requisitos_comparables(tmp_path, analizador):
    srv, llm, repo, pid = montar_comparacion(tmp_path, analizador)
    with pytest.raises(KeyError):
        preparar(srv, "P99")
    requisito(repo, pid, REGISTRAR)
    requisito(repo, pid, REGISTRAR_2, Estado.ERROR)
    with pytest.raises(RequisitosInsuficientes, match="1 requisito"):
        preparar(srv, pid)
    assert repo.listar_docs(COLECCION) == []


def test_ejecutar_de_nuevo_reinicia_y_listar_resume(tmp_path, analizador):
    srv, llm, repo, pid = montar_comparacion(tmp_path, analizador, vectores={REGISTRAR: [1, 0, 0],
                                                                             REGISTRAR_2: [0.98, 0.199, 0]})
    requisito(repo, pid, REGISTRAR)
    requisito(repo, pid, REGISTRAR_2)
    c1 = comparar(srv, pid)
    c2 = ejecutar(srv, preparar(srv, pid).comparacion_id)
    otra = ejecutar(srv, c1.comparacion_id)  # se corre desde el principio: no acumula
    assert (c1.comparacion_id, c2.comparacion_id) == ("C01", "C02")
    assert len(otra.hallazgos) == len(c1.hallazgos) == 1 and len(otra.relaciones_por_par) == 1
    assert otra.creado == c1.creado
    resumenes = listar(srv, pid)
    assert [r.comparacion_id for r in resumenes] == ["C02", "C01"]
    assert resumenes[0].hallazgos_por_tipo == {"contradiccion": 0, "casi_duplicado": 1, "redundancia": 0,
                                      "inconsistencia_vocabulario": 0}
    assert listar(srv, "P00") == []


def test_recuperar_reencola_las_pendientes(tmp_path, analizador):
    srv, llm, repo, pid = montar_comparacion(tmp_path, analizador, vectores={REGISTRAR: [1, 0, 0],
                                                                             REGISTRAR_2: [0, 1, 0]})
    requisito(repo, pid, REGISTRAR)
    requisito(repo, pid, REGISTRAR_2)
    pendiente = preparar(srv, pid)
    terminada = comparar(srv, pid)
    assert recuperar(srv) == [pendiente.comparacion_id]
    srv.cola.iniciar()
    try:
        assert srv.cola.esperar(10)
    finally:
        srv.cola.detener()
    assert obtener(srv, pendiente.comparacion_id).estado == "terminada"
    assert obtener(srv, terminada.comparacion_id).estado == "terminada"


def test_lel_de_un_requisito_reprocesado_se_reporta_sin_similitud(tmp_path, analizador):
    """El requisito reprocesado no se compara, pero su entrada sigue en la memoria del LEL:
    la inconsistencia es real y se reporta, sin similitud porque no está en la matriz."""
    textos = ["El sistema debe registrar la sesión.", "El sistema debe registrar la sesión del usuario.",
              "El sistema debe cerrar la sesión."]
    srv, llm, repo, pid = montar_comparacion(
        tmp_path, analizador, vectores=dict(zip(textos, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])))
    viejo = requisito(repo, pid, textos[0], Estado.FORMALIZADO, reescrito=textos[0])
    nuevo = requisito(repo, pid, textos[1], origen=Origen(reproceso_de=viejo))
    otro = requisito(repo, pid, textos[2], Estado.FORMALIZADO, reescrito=textos[2])
    repo.guardar_lel([entrada_lel(pid, viejo, "sesión", ["Periodo de uso."]),
                      entrada_lel(pid, otro, "sesión", ["Evento de conexión."])])

    c = comparar(srv, pid)

    assert [r.req_id for r in c.requisitos] == [nuevo, otro]
    assert [(e.req_id, e.motivo) for e in c.excluidos] == [(viejo, "reprocesado")]
    vocab = [h for h in c.hallazgos if h.tipo == "inconsistencia_vocabulario"]
    assert [(h.requisitos, h.similitud) for h in vocab] == [([viejo, otro], None)]
    assert list(c.matriz_similitud) == [f"{nuevo}-{otro}"]


def test_la_config_registra_los_modelos_con_que_corrio(tmp_path, analizador):
    """Una comparación encolada antes de un reinicio puede correr con otros modelos:
    los umbrales son los de la solicitud, los modelos los de la corrida."""
    from tests.fakes import EmbeddingsFalsos

    srv, llm, repo, pid = montar_comparacion(tmp_path, analizador, comparacion_relacion_umbral=0.5)
    requisito(repo, pid, REGISTRAR)
    requisito(repo, pid, REGISTRAR_2)
    pendiente = preparar(srv, pid)
    assert (pendiente.config.modelo_embeddings, pendiente.config.umbral_relacion) == ("embeddings-falsos", 0.5)

    class OtrosEmbeddings(EmbeddingsFalsos):
        modelo = "otros-embeddings"

    srv.deps.embeddings = OtrosEmbeddings({})
    llm.modelo = "otro-llm"
    srv.deps.settings.comparacion_relacion_umbral = 0.9
    c = ejecutar(srv, pendiente.comparacion_id)

    assert (c.config.modelo, c.config.modelo_embeddings, c.config.umbral_relacion) == ("otro-llm", "otros-embeddings", 0.5)
    assert [h.modelo for h in c.hallazgos if h.fuente == "embeddings"] == ["otros-embeddings"]
