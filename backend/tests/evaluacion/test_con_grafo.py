"""Evaluación de punta a punta: el grafo real con LLM y embeddings falsos, por la cola.

Números esperados del escenario (ver `ayudantes`), calculados a mano:

Detección (todo lo que marca el ground truth): esperados A sesión, B jalar y ahorita,
C todos los usuarios = 4.
- Sistema: sesión (interpretaciones), jalar (regional listado), ahorita (vaguedad
  listada), Todos los usuarios (exacto tras normalizar) = 4 vp; comprobante = 1 fp; 0 fn.
  precisión 4/5 = 0.8, exhaustividad 1, F1 8/9 = 0.888889.
- Línea base: sesión y usuarios (contención) = 2 vp; jalar y ahorita = 2 fn; D falló.
  precisión 1, exhaustividad 0.5, F1 4/6 = 0.666667.
Detección de ambigüedad (solo términos ambiguos: sesión, jalar, todos los usuarios):
- Sistema: sesión y Todos los usuarios = 2 vp; comprobante 1 fp; jalar 1 fn → 2/3 en todo.
- Línea base: 2 vp, 0 fp, jalar 1 fn → precisión 1, exhaustividad 2/3, F1 4/5 = 0.8.
Requisito: sistema A sí, B no, C sí, D sí contra sí, sí, sí, no → vp 2, fn 1, fp 1 → 2/4.
Línea base: A sí, B no, C sí, D sin decisión → vp 2, fn 1, sin decisión 1 → 2/4.
Tipo: sistema sesión bien, Todos los usuarios sintáctica contra alcance mal → 1/2;
línea base sesión y usuarios bien → 2/2.
Debates: activados A y D; necesarios A, B, C; justificado A; de más D; faltantes B y C.
"""
import pytest

from app import evaluacion
from app.calibracion import seleccionar_etiquetas
from app.evaluacion import formas
from tests.escenarios import montar
from tests.evaluacion.ayudantes import GROUND_TRUTH, escribir_corpus, guiones

SECRETO = "SECRETO-GT"


@pytest.fixture(scope="module")
def corrida(tmp_path_factory, analizador):
    tmp = tmp_path_factory.mktemp("evaluacion")
    srv, llm, repo = montar(tmp, analizador, guiones(), corpus_dir=str(tmp / "corpus"))
    gt = [{**g, "notas": f"{SECRETO} {g['id']}"} for g in GROUND_TRUTH]
    gt[1]["terminos"] = [{**gt[1]["terminos"][0], "interpretaciones_validas": ["consultar", f"{SECRETO} descargar"]}]
    escribir_corpus(tmp / "corpus", "escenario", ground_truth=gt)
    srv.cola.iniciar()
    ev = evaluacion.solicitar(srv, "escenario")
    assert srv.cola.esperar(20)
    informe = formas.InformeEvaluacion.model_validate(evaluacion.informe(srv, ev.evaluacion_id))
    yield srv, llm, repo, ev, informe, tmp
    srv.detener()


def test_resumen_del_sistema(corrida):
    r = corrida[4].resumen.sistema.model_dump()
    assert r == {
        "n": 4, "errores": 0,
        "deteccion": {"vp": 4, "fp": 1, "fn": 0, "precision": 0.8, "exhaustividad": 1.0, "f1": 0.888889},
        "deteccion_ambiguedad": {"vp": 2, "fp": 1, "fn": 1, "precision": 0.666667, "exhaustividad": 0.666667,
                                 "f1": 0.666667},
        "requisito": {"vp": 2, "fp": 1, "vn": 0, "fn": 1, "sin_decision": 0, "exactitud": 0.5},
        "tipo": {"n": 2, "aciertos": 1, "exactitud": 0.5},
        "debates": {"activados": 2, "necesarios": 3, "justificados": 1, "de_mas": 1, "faltantes": 2},
        "vias": {"aceptado_directo": 1, "consenso": 2, "arbitraje": 0, "sin_via": 0},
    }


def test_resumen_de_la_linea_base(corrida):
    assert corrida[4].resumen.linea_base.model_dump() == {
        "n": 4, "errores": 1,
        "deteccion": {"vp": 2, "fp": 0, "fn": 2, "precision": 1.0, "exhaustividad": 0.5, "f1": 0.666667},
        "deteccion_ambiguedad": {"vp": 2, "fp": 0, "fn": 1, "precision": 1.0, "exhaustividad": 0.666667, "f1": 0.8},
        "requisito": {"vp": 2, "fp": 0, "vn": 0, "fn": 1, "sin_decision": 1, "exactitud": 0.5},
        "tipo": {"n": 2, "aciertos": 2, "exactitud": 1.0},
    }


def test_filas_por_requisito(corrida):
    informe = corrida[4]
    assert informe.estado == "terminada" and informe.terminado is not None
    assert informe.progreso.model_dump() == {"total": 4, "listos_sistema": 4, "listos_linea_base": 4}
    a, b, c, d = informe.requisitos
    assert [(f.id_corpus, f.req_id) for f in informe.requisitos] == [("A", "R01"), ("B", "R02"), ("C", "R03"),
                                                                     ("D", "R04")]

    sesion = next(t for t in a.sistema.terminos if t.termino == "sesión")
    assert (sesion.via, sesion.similitud, sesion.interpretacion, sesion.criterio) == ("consenso", 0.0, "periodo de uso",
                                                                                      "exacto")
    assert a.sistema.debate_gt == "justificado" and a.ground_truth.terminos[0].interpretacion_esperada == "periodo de uso"

    detectados = {t.termino: t.motivo_deteccion for t in b.sistema.terminos if t.detectado}
    assert detectados == {"jalar": "regional", "ahorita": "vaguedad"}
    assert (b.sistema.ambiguo, b.sistema.debate_gt, b.linea_base.faltantes) == (False, "faltante", ["jalar", "ahorita"])

    [todos] = c.sistema.terminos
    assert (todos.termino, todos.origen, todos.via, todos.similitud) == ("Todos los usuarios", "alcance",
                                                                         "aceptado_directo", 1.0)
    assert (todos.tipo_ambiguedad, todos.tipo_gt, todos.tipo_correcto) == ("sintactica", "alcance", False)
    [usuarios] = c.linea_base.terminos
    assert (usuarios.emparejado_con, usuarios.criterio, usuarios.tipo_correcto) == ("todos los usuarios",
                                                                                    "contencion", True)

    assert (d.sistema.debate_gt, d.sistema.deteccion.model_dump()) == ("de_mas", {"vp": 0, "fp": 1, "fn": 0})
    assert d.linea_base.listo and d.linea_base.ambiguo is None and "no produjo una salida válida" in d.linea_base.error
    assert informe.avisos == ["1 requisito(s) de la línea base terminaron en error (D): cuentan como «sin decisión» "
                              "y sus términos como no detectados"]


def test_documento_guardado_y_etiquetas_para_la_calibracion(corrida):
    srv, _, repo, ev, informe, _ = corrida
    doc = repo.obtener_doc("evaluaciones", ev.evaluacion_id)
    assert doc["estado"] == "terminada" and doc["corpus"] == "escenario"
    assert doc["items"] == [{"id_corpus": i, "req_id": r} for i, r in zip("ABCD", ("R01", "R02", "R03", "R04"))]
    assert doc["config"]["agente_unico"] == {"modelo": "llm-falso", "prompt_version": "agente_unico_v1"}
    assert doc["config"]["similarity_threshold"] == 0.75
    assert set(doc["linea_base"]) == set("ABCD") and doc["linea_base"]["D"]["error"]["excepcion"] == "FalloEstructurado"
    assert doc["etiquetas"] == [
        {"req_id": "R01", "termino": "sistema", "ambiguo": False, "tipo_ambiguedad": None},
        {"req_id": "R01", "termino": "registrar", "ambiguo": False, "tipo_ambiguedad": None},
        {"req_id": "R01", "termino": "sesión", "ambiguo": True, "tipo_ambiguedad": "lexica"},
        {"req_id": "R02", "termino": "sistema", "ambiguo": False, "tipo_ambiguedad": None},
        {"req_id": "R02", "termino": "jalar", "ambiguo": True, "tipo_ambiguedad": "lexica"},
        {"req_id": "R02", "termino": "datos", "ambiguo": False, "tipo_ambiguedad": None},
        {"req_id": "R03", "termino": "Todos los usuarios", "ambiguo": True, "tipo_ambiguedad": "alcance"},
        {"req_id": "R04", "termino": "comprobante", "ambiguo": False, "tipo_ambiguedad": None},
    ]
    assert [e.model_dump(mode="json") for e in informe.etiquetas] == doc["etiquetas"]
    # el módulo de calibración las lee sin descartar ninguna
    fuentes, etiquetas, invalidas = seleccionar_etiquetas(repo.listar_docs("evaluaciones"))
    assert invalidas == 0 and len(etiquetas) == 8
    assert fuentes == [{"proyecto_id": ev.proyecto_id, "evaluacion_id": ev.evaluacion_id, "n_etiquetas": 8}]


def test_proyecto_de_evaluacion_y_origen_de_cada_requisito(corrida):
    srv, _, _, ev, _, _ = corrida
    p = srv.proyectos.obtener(ev.proyecto_id)
    assert p.tipo == "evaluacion" and p.nombre == "Evaluación del corpus escenario"
    trazas = srv.repo.trazas_completas(ev.proyecto_id)
    assert [(t.origen.marca, t.origen.archivo, t.origen.indice, t.ciclo) for t in trazas] == [
        ("A", "corpus:escenario", 1, 1), ("B", "corpus:escenario", 2, 1), ("C", "corpus:escenario", 3, 1),
        ("D", "corpus:escenario", 4, 1)]
    assert {t.estado.value for t in trazas} == {"pendiente_validacion"}  # nadie validó


def test_el_ground_truth_no_entra_a_ningun_prompt(corrida):
    llm = corrida[1]
    assert len(llm.llamadas["agente_unico_v1"]) == 5  # una por requisito y el reintento de D
    prompts = [p.sistema + p.usuario for llamadas in llm.llamadas.values() for p in llamadas]
    assert prompts and not any(SECRETO in p for p in prompts)


def test_listado(corrida):
    srv, _, _, ev, _, _ = corrida
    [resumen] = [formas.ResumenEvaluacion.model_validate(r) for r in evaluacion.listar(srv)]
    assert (resumen.evaluacion_id, resumen.estado, resumen.ejemplo) == (ev.evaluacion_id, "terminada", False)
    assert resumen.progreso.model_dump() == {"total": 4, "listos_sistema": 4, "listos_linea_base": 4}


def test_avisos_si_el_corpus_cambia_o_desaparece(corrida):
    srv, _, _, ev, informe, tmp = corrida
    archivo = tmp / "corpus" / "escenario" / "ground_truth.jsonl"
    original = archivo.read_text(encoding="utf-8")
    try:
        cambiado = original.replace(f"{SECRETO} D", f"{SECRETO} D revisada")
        assert cambiado != original
        archivo.write_text(cambiado, encoding="utf-8")
        r = evaluacion.informe(srv, ev.evaluacion_id)
        assert any("cambió desde que se creó la evaluación" in a for a in r["avisos"])
        assert r["resumen"] == informe.resumen.model_dump(mode="json")  # se mide contra el ground truth guardado
        archivo.unlink()
        r = evaluacion.informe(srv, ev.evaluacion_id)
        assert any("ya no está en disco o no es válido" in a for a in r["avisos"])
    finally:
        archivo.write_text(original, encoding="utf-8")
