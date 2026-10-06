"""Formato del corpus y cargador: errores claros, todos juntos, y el corpus de ejemplo del repositorio."""
import json

import pytest

from app.config import RAIZ_REPO
from app.evaluacion.corpus import (
    CorpusInvalido,
    CorpusNoEncontrado,
    cargar_corpus,
    conteo,
    huella,
    nombres_de_corpus,
    resumen_corpus,
)
from app.evaluacion.formas import ResumenCorpus
from tests.evaluacion.ayudantes import GROUND_TRUTH, REQUISITOS, escribir_corpus


def gt(id_, ambiguo=False, terminos=(), **extra):
    return {"id": id_, "ambiguo": ambiguo, "terminos": list(terminos), "vaguedad": [], "regionales": [], "notas": None,
            **extra}


def termino(t="sesión", tipo="lexica", validas=("uno", "dos"), esperada=None):
    return {"termino": t, "tipo_ambiguedad": tipo, "interpretaciones_validas": list(validas),
            "interpretacion_esperada": esperada}


def errores_de(raiz, nombre="c") -> list[str]:
    with pytest.raises(CorpusInvalido) as e:
        cargar_corpus(raiz, nombre)
    return e.value.errores


def test_corpus_de_ejemplo_del_repositorio_es_valido_y_esta_marcado():
    c = cargar_corpus(RAIZ_REPO / "data" / "corpus", "ejemplo")
    assert c.ejemplo is True and c.validado_por is None
    assert "EJEMPLO" in c.descripcion and "NO es el corpus de la tesis" in c.descripcion
    assert all(it.ground_truth.notas.startswith("EJEMPLO") for it in c.items)
    assert c.avisos == []
    n = conteo(c.items)
    assert 6 <= n["n_requisitos"] <= 8
    assert n["n_sin_ambiguedad"] == 3  # dos sin nada y uno solo vago
    assert {k for k, v in n["por_tipo"].items() if v} == {"lexica", "anaforica", "alcance"}
    por_id = {it.id: it.ground_truth for it in c.items}
    assert por_id["EJ02"].terminos[0].termino == "sesión"
    assert por_id["EJ03"].regionales == ["jalar"] and por_id["EJ03"].vaguedad == ["ahorita"]
    assert por_id["EJ04"].terminos[0].termino == "su historial"
    assert por_id["EJ05"].terminos[0].tipo_ambiguedad == "alcance"
    assert por_id["EJ06"].ambiguo is False and por_id["EJ06"].vaguedad == ["rápido"]


def test_carga_un_corpus_valido_en_orden(tmp_path):
    escribir_corpus(tmp_path, "c")
    c = cargar_corpus(tmp_path, "c")
    assert [it.id for it in c.items] == ["A", "B", "C", "D"]
    assert c.items[1].ground_truth.regionales == ["jalar"]
    assert c.ejemplo is False and c.descripcion is None
    assert c.huella == huella(tmp_path / "c") and len(c.huella) == 64


def test_ids_que_no_coinciden(tmp_path):
    escribir_corpus(tmp_path, "c", REQUISITOS[:3], [GROUND_TRUTH[0], GROUND_TRUTH[1], gt("X")])
    assert errores_de(tmp_path) == ["requisitos sin ground truth: C",
                                    "ground truth de ids que no están en requisitos.jsonl: X"]


def test_errores_de_formato_se_reportan_juntos_con_su_linea(tmp_path):
    requisitos = ('{"id": "A", "texto": "El sistema debe registrar la sesión."}\n'
                  '\n'
                  '{"id": "B", "texto": "x", "prioridad": 1}\n'
                  'esto no es json\n'
                  '{"id": "A", "texto": "repetido"}\n'
                  '{"texto": "sin id"}\n')
    filas = [gt("A", True, [termino()]),
             gt("B", True, []),
             gt("C", False, [termino()]),
             gt("D", True, [termino(esperada="tres")]),
             gt("E", True, [termino(tipo="pragmatica")]),
             gt("F", True, [termino(validas=["solo una"])]),
             gt("G", True, [termino("Sesión"), termino("sesion")])]
    escribir_corpus(tmp_path, "c", crudo_requisitos=requisitos,
                    crudo_ground_truth="\n".join(json.dumps(f, ensure_ascii=False) for f in filas))
    e = errores_de(tmp_path)
    esperados = [
        "requisitos.jsonl, línea 3 (id B): prioridad: campo no permitido",
        "requisitos.jsonl, línea 4: no es JSON válido",
        "requisitos.jsonl, línea 6: id: falta el campo",
        "ground_truth.jsonl, línea 2 (id B): ambiguo es true pero no hay terminos",
        "ground_truth.jsonl, línea 3 (id C): ambiguo es false pero hay terminos",
        "ground_truth.jsonl, línea 4 (id D): terminos.0: 'sesión': interpretacion_esperada debe ser una de",
        "ground_truth.jsonl, línea 5 (id E): terminos.0.tipo_ambiguedad:",
        "ground_truth.jsonl, línea 6 (id F): terminos.0.interpretaciones_validas:",
        "ground_truth.jsonl, línea 7 (id G): hay términos repetidos en terminos",
        "requisitos.jsonl: el id «A» se repite (líneas 1 y 5)",
        "ground truth de ids que no están en requisitos.jsonl: C, D, E, F, G",
    ]
    for prefijo in esperados:
        assert any(x.startswith(prefijo) for x in e), (prefijo, e)
    # B tiene ground truth aunque su línea de requisitos no validó: no se inventa un faltante
    assert not any(x.startswith("requisitos sin ground truth") for x in e)


def test_faltan_archivos_y_corpus_vacio(tmp_path):
    (tmp_path / "solo").mkdir()
    (tmp_path / "solo" / "requisitos.jsonl").write_text('{"id": "A", "texto": "x"}\n', encoding="utf-8")
    assert errores_de(tmp_path, "solo") == ["falta el archivo ground_truth.jsonl"]
    escribir_corpus(tmp_path, "vacio", crudo_requisitos="", crudo_ground_truth="\n")
    assert errores_de(tmp_path, "vacio") == ["requisitos.jsonl no tiene requisitos"]


def test_descripcion_invalida(tmp_path):
    escribir_corpus(tmp_path, "c", descripcion={"ejemplo": "quizá", "otra": 1})
    e = errores_de(tmp_path)
    assert any(x.startswith("corpus.json: ") and "otra: campo no permitido" in x for x in e)


@pytest.mark.parametrize("nombre", ["no-existe", "../corpus", "a/b", "", ".oculto"])
def test_no_encontrado_y_nombres_que_salen_del_directorio(tmp_path, nombre):
    escribir_corpus(tmp_path, "c")
    with pytest.raises(CorpusNoEncontrado):
        cargar_corpus(tmp_path, nombre)


def test_avisos_sin_casos_negativos_y_terminos_que_no_aparecen(tmp_path):
    escribir_corpus(tmp_path, "c", [{"id": "A", "texto": "El sistema debe jalar los datos."}],
                    [gt("A", True, [termino("jalar")], regionales=["jale"], vaguedad=["ahorita"])])
    c = cargar_corpus(tmp_path, "c")
    sufijo = "no aparece tal cual en el texto; escríbelo como aparece para que el emparejamiento lo encuentre"
    assert c.avisos == [
        f"A: «ahorita» {sufijo}",
        f"A: «jale» {sufijo}",
        "no hay requisitos sin ambigüedad: son los que revelan si el umbral dispara de más (CONTEXTO §11)",
    ]


def test_listado_incluye_los_invalidos_con_sus_errores(tmp_path):
    escribir_corpus(tmp_path, "bueno", descripcion={"descripcion": "prueba", "autoria": "tesista"})
    escribir_corpus(tmp_path, "malo", REQUISITOS, GROUND_TRUTH[:2])
    (tmp_path / "no es corpus").mkdir()  # nombre fuera del patrón: no se lista
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    assert nombres_de_corpus(tmp_path) == ["bueno", "malo"]
    assert nombres_de_corpus(tmp_path / "no-existe") == []

    bueno = ResumenCorpus.model_validate(resumen_corpus(tmp_path, "bueno"))
    assert bueno.valido and bueno.descripcion == "prueba" and bueno.autoria == "tesista"
    assert bueno.conteo.model_dump() == {"n_requisitos": 4, "n_ambiguos": 3, "n_sin_ambiguedad": 1, "n_terminos": 3,
                                         "por_tipo": {"lexica": 2, "alcance": 1, "anaforica": 0, "sintactica": 0},
                                         "n_vaguedad": 1, "n_regionales": 1}
    malo = ResumenCorpus.model_validate(resumen_corpus(tmp_path, "malo"))
    assert not malo.valido and malo.conteo is None
    assert malo.errores == ["requisitos sin ground truth: C, D"]


def test_la_huella_cambia_si_cambia_el_ground_truth(tmp_path):
    d = escribir_corpus(tmp_path, "c")
    antes = huella(d)
    escribir_corpus(tmp_path, "c", ground_truth=[{**GROUND_TRUTH[0], "notas": "otra"}, *GROUND_TRUTH[1:]])
    assert huella(d) != antes
    (d / "ground_truth.jsonl").unlink()
    assert huella(d) is None

