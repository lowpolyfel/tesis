"""La comparación sobre trazas reales del grafo: dos requisitos de «sesión» procesados
en paralelo y validados con significados distintos (el segundo editado por el humano)."""
from app.comparacion import comparar
from app.models import Estado, Interpretacion, Validacion
from tests.comparacion.ayudantes import juez_por_par, juicio
from tests.escenarios import EXTRACCION_SESION, I1, MODELADO, P1_CERCANA, P2, SESION, clasificacion, montar
from tests.fakes import EmbeddingsFalsos, interp

MODELADO_CONEXION = {"entrada_lel": {"simbolo": "sesión", "tipo": "objeto", "nocion": ["Evento de conexión al sistema."],
                                     "impacto": ["Se registra al conectarse."]}}


def test_trazas_del_grafo(tmp_path, analizador):
    guiones = {
        "extractor_v1": [EXTRACCION_SESION, EXTRACCION_SESION],
        "clasificador_v2": [clasificacion(I1, interp("I2", "periodo de uso", P1_CERCANA))] * 2,
        "modelador_v1": [MODELADO, MODELADO_CONEXION],
        "comparador_v1": juez_por_par({("R01", "R02"): juicio("redundancia", "registrar la sesión", "registrar la sesión")}),
    }
    srv, llm, repo = montar(tmp_path, analizador, guiones)
    pid = srv.proyectos.crear("Banca").proyecto_id
    r1, r2 = srv.procesar(SESION, pid), srv.procesar(SESION, pid)  # ninguno ve el LEL del otro
    srv.validar(r1, Validacion(decision="aprobar"))
    editada = Interpretacion.model_validate(interp("I2", "evento de conexión", P2))
    srv.validar(r2, Validacion(decision="aprobar", interpretaciones_editadas={"sesión": editada}))
    assert [srv.traza(r).estado for r in (r1, r2)] == [Estado.FORMALIZADO, Estado.FORMALIZADO]
    srv.deps.embeddings = EmbeddingsFalsos({SESION: [1.0, 0.0, 0.0]})

    c = comparar(srv, pid)

    assert c.estado == "terminada"
    assert [(r.req_id, r.base) for r in c.requisitos] == [(r1, "reescrito"), (r2, "reescrito")]
    assert [(h.tipo, h.fuente) for h in c.hallazgos] == [
        ("inconsistencia_vocabulario", "lel"), ("casi_duplicado", "embeddings"), ("redundancia", "llm")]
    vocab = c.hallazgos[0]
    assert vocab.terminos == ["sesión"] and vocab.requisitos == [r1, r2]
    assert "«periodo de uso» en R01 y «evento de conexión» en R02" in vocab.explicacion
    assert c.relaciones_por_par[0].motivos == ["similitud", "simbolo_lel", "lema"]
