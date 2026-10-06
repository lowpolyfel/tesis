"""Big Picture del proyecto: nodos y aristas exactos, relaciones entre símbolos,
panorama y requisitos fuera (funciones puras, sin LLM)."""
import random

from app.artefactos import big_picture_proyecto, formas
from tests.artefactos.ayudantes import (
    R01_REESCRITO,
    R02_TEXTO,
    R03_REESCRITO,
    documentos,
    lel,
    trazas,
)


def _bp(analizador=None, docs=None, entradas=None, resumenes=None):
    bp = big_picture_proyecto(documentos() if docs is None else docs, lel() if entradas is None else entradas,
                              trazas() if resumenes is None else resumenes, analizador)
    formas.BigPicture.model_validate(bp)
    return bp


def _nodo(id_, tipo, etiqueta, req_ids, subtipo=None, detalle=None):
    return {"id": id_, "tipo": tipo, "subtipo": subtipo, "etiqueta": etiqueta, "detalle": detalle, "req_ids": req_ids}


def test_nodos_exactos():
    assert _bp()["nodos"] == [
        _nodo("R01", "requisito", "R01", ["R01"], detalle=R01_REESCRITO),
        _nodo("R02", "requisito", "R02", ["R02"], detalle=R02_TEXTO),
        _nodo("R03", "requisito", "R03", ["R03"], detalle=R03_REESCRITO),
        _nodo("R01.M1", "meta", "Registrar el periodo de uso del usuario", ["R01"]),
        _nodo("R01.M2", "tarea", "Guardar la hora de inicio y de cierre", ["R01"]),
        _nodo("R02.M1", "meta", "Consultar la bitácora", ["R02"]),
        _nodo("R02.M2", "meta_blanda", "Responder ahorita", ["R02"]),
        _nodo("R03.M1", "tarea", "Dar de alta al cliente", ["R03"]),
        _nodo("R03.M2", "recurso", "Expediente del cliente", ["R03"]),
        _nodo("R03.M3", "meta", "Que el cliente quede registrado", ["R03"]),
        _nodo("actor:administrador", "actor", "administrador", ["R03"]),
        _nodo("actor:sistema", "actor", "sistema", ["R01"]),
        _nodo("actor:usuario", "actor", "usuario", ["R02"]),  # sujeto del LEL resuelto en R02
        _nodo("actor:usuarios", "actor", "usuarios", ["R02"]),
        _nodo("simbolo:bitacora", "simbolo", "bitácora", ["R02"], "objeto", "Registro de eventos de auditoría."),
        _nodo("simbolo:dar_de_alta", "simbolo", "dar de alta", ["R03"], "verbo",
              "Registrar a un usuario nuevo en el sistema."),
        # R08 quedó fuera del proyecto, pero su entrada sigue en la memoria
        _nodo("simbolo:expediente", "simbolo", "expediente", ["R08"], "objeto", "Conjunto de documentos del trámite."),
        _nodo("simbolo:sesion", "simbolo", "sesión", ["R01"], "objeto",
              "Periodo de uso continuo del sistema por un usuario."),
        _nodo("simbolo:usuario", "simbolo", "usuario", ["R02"], "sujeto", "Persona que usa el sistema."),
    ]


def test_aristas_exactas():
    aristas = [(a["origen"], a["relacion"], a["destino"]) for a in _bp()["aristas"]]
    assert aristas == [
        ("actor:sistema", "persigue", "R01.M1"), ("actor:sistema", "persigue", "R01.M2"),
        ("actor:usuarios", "persigue", "R02.M1"),
        ("actor:administrador", "persigue", "R03.M1"), ("actor:administrador", "persigue", "R03.M3"),
        ("R01.M2", "contribuye_a", "R01.M1"), ("R02.M2", "contribuye_a", "R02.M1"),
        ("R03.M1", "contribuye_a", "R03.M3"), ("R03.M2", "contribuye_a", "R03.M1"),
        ("R01.M1", "deriva_de", "R01"), ("R01.M2", "deriva_de", "R01"), ("R02.M1", "deriva_de", "R02"),
        ("R02.M2", "deriva_de", "R02"), ("R03.M1", "deriva_de", "R03"), ("R03.M2", "deriva_de", "R03"),
        ("R03.M3", "deriva_de", "R03"),
        ("R01.M1", "usa", "simbolo:sesion"), ("R01.M2", "usa", "simbolo:sesion"),
        ("R02.M1", "usa", "simbolo:bitacora"), ("R03.M1", "usa", "simbolo:dar_de_alta"),
        ("R01", "resuelve", "simbolo:sesion"), ("R02", "resuelve", "simbolo:bitacora"),
        ("R02", "resuelve", "simbolo:usuario"), ("R03", "resuelve", "simbolo:dar_de_alta"),
        # el símbolo aparece en el texto y no lo resolvió ese requisito
        ("R01", "menciona", "simbolo:usuario"), ("R03", "menciona", "simbolo:sesion"),
        # B aparece en la noción o el impacto de A
        ("simbolo:dar_de_alta", "relacionado_con", "simbolo:sesion"),
        ("simbolo:dar_de_alta", "relacionado_con", "simbolo:usuario"),
        ("simbolo:sesion", "relacionado_con", "simbolo:usuario"),
        ("simbolo:usuario", "relacionado_con", "simbolo:sesion"),
        ("actor:usuario", "relacionado_con", "simbolo:usuario"),
    ]


def test_toda_arista_une_nodos_existentes():
    bp = _bp()
    ids = {n["id"] for n in bp["nodos"]}
    assert len(ids) == len(bp["nodos"])
    assert all(a["origen"] in ids and a["destino"] in ids for a in bp["aristas"])
    assert len({tuple(a.values()) for a in bp["aristas"]}) == len(bp["aristas"])


def test_terminos_de_metas_que_no_estan_en_el_lel():
    assert _bp()["terminos_sin_simbolo"] == [{"termino": "hora de inicio", "metas": ["R01.M2"]},
                                             {"termino": "cliente", "metas": ["R03.M1", "R03.M2"]}]


def test_panorama():
    p = _bp()["panorama"]
    assert p["actores"] == ["administrador", "sistema", "usuario", "usuarios"]
    assert p["acciones"] == [
        {"actor": "sistema", "verbo": "registrar", "objeto": "el periodo de uso del usuario", "req_id": "R01",
         "meta": "R01.M1"},
        {"actor": "sistema", "verbo": "guardar", "objeto": "la hora de inicio y de cierre", "req_id": "R01",
         "meta": "R01.M2"},
        {"actor": "usuarios", "verbo": "consultar", "objeto": "la bitácora", "req_id": "R02", "meta": "R02.M1"},
        {"actor": "administrador", "verbo": "dar", "objeto": "de alta al cliente", "req_id": "R03", "meta": "R03.M1"},
        # no empieza con infinitivo: no se inventa un verbo
        {"actor": "administrador", "verbo": None, "objeto": "Que el cliente quede registrado", "req_id": "R03",
         "meta": "R03.M3"},
    ]
    # «ahorita» ya la recoge la meta blanda R02.M2; «rápido» no
    assert p["restricciones"] == [
        {"texto": "Responder ahorita", "req_id": "R02", "origen": "meta_blanda", "meta": "R02.M2"},
        {"texto": "rápido", "req_id": "R03", "origen": "vaguedad", "meta": None},
    ]
    assert p["terminos_resueltos"] == [
        {"termino": "sesión", "significado": "periodo de uso", "via": "consenso", "tipo_ambiguedad": "lexica",
         "cambio": "ninguno", "req_id": "R01"},
        {"termino": "usuario", "significado": "persona que usa el sistema", "via": "aceptado_directo",
         "tipo_ambiguedad": "lexica", "cambio": "ninguno", "req_id": "R02"},
        {"termino": "bitácora", "significado": "registro de auditoría", "via": "arbitraje",
         "tipo_ambiguedad": "lexica", "cambio": "edicion", "req_id": "R02"},
        {"termino": "dar de alta", "significado": "registrar", "via": "consenso", "tipo_ambiguedad": "lexica",
         "cambio": "eleccion", "req_id": "R03"},
        # R08 se formalizó antes del documento por requisito: su término sale del LEL
        {"termino": "expediente", "significado": "Conjunto de documentos del trámite.", "via": "consenso",
         "tipo_ambiguedad": "lexica", "cambio": None, "req_id": "R08"},
    ]
    assert p["dependencias"] == [{"de": "R01", "a": "R02", "por": "usuario"},
                                 {"de": "R03", "a": "R01", "por": "sesión"}]
    assert p["requisitos"] == [{"req_id": "R01", "requisito_reescrito": R01_REESCRITO},
                               {"req_id": "R02", "requisito_reescrito": R02_TEXTO},
                               {"req_id": "R03", "requisito_reescrito": R03_REESCRITO}]


def test_requisitos_fuera_y_excluidos_del_grafo():
    bp = _bp()
    assert [(f["req_id"], f["motivo"]) for f in bp["requisitos_fuera"]] == [
        ("R04", "en_proceso"), ("R05", "rechazado"), ("R06", "reprocesado"), ("R07", "en_proceso"),
        ("R08", "sin_formalizacion"), ("R09", "sin_traza")]
    ids = {n["id"] for n in bp["nodos"]}
    assert not {"R06", "R06.M1", "R09", "R09.M1"} & ids


def test_con_lemas(analizador):
    bp = _bp(analizador)
    aristas = {(a["origen"], a["relacion"], a["destino"]) for a in bp["aristas"]}
    assert "actor:usuarios" not in {n["id"] for n in bp["nodos"]}
    assert ("actor:usuario", "persigue", "R02.M1") in aristas
    assert ("actor:usuario", "relacionado_con", "simbolo:usuario") in aristas
    assert bp["panorama"]["actores"] == ["administrador", "sistema", "usuario"]
    assert bp["panorama"]["acciones"][2]["actor"] == "usuario"
    # lo que ya coincidía por forma sigue coincidiendo con lemas
    sin_lemas = {(a["origen"], a["relacion"], a["destino"]) for a in _bp()["aristas"]}
    assert sin_lemas - {("actor:usuarios", "persigue", "R02.M1")} <= aristas


def test_simbolo_con_dos_entradas_es_un_solo_nodo():
    from tests.artefactos.ayudantes import entrada

    entradas = lel() + [entrada("Sesión", "estado", ["Evento de conexión al sistema."], ["Se registra al conectarse."],
                                "R02")]
    bp = _bp(entradas=entradas)
    sesion = [n for n in bp["nodos"] if n["id"] == "simbolo:sesion"]
    assert sesion == [_nodo("simbolo:sesion", "simbolo", "sesión", ["R01", "R02"], "objeto",
                            "Periodo de uso continuo del sistema por un usuario.")]
    assert ("R02", "simbolo:sesion", "resuelve") in {(a["origen"], a["destino"], a["relacion"]) for a in bp["aristas"]}
    assert "Evento de conexión al sistema." in bp["plantuml"]


def test_proyecto_sin_formalizados():
    bp = _bp(docs=[], entradas=[], resumenes=[])
    assert (bp["nodos"], bp["aristas"], bp["terminos_sin_simbolo"], bp["requisitos_fuera"]) == ([], [], [], [])
    assert bp["panorama"] == {"actores": [], "acciones": [], "restricciones": [], "terminos_resueltos": [],
                              "dependencias": [], "requisitos": []}
    assert bp["mermaid"].startswith("flowchart LR\n")
    assert "Sin símbolos del LEL ni actores todavía" in bp["plantuml"]


def test_requisitos_en_proceso_no_son_error():
    bp = _bp(docs=[], entradas=[], resumenes=trazas()[3:5])
    assert bp["nodos"] == [] and [f["motivo"] for f in bp["requisitos_fuera"]] == ["en_proceso", "rechazado"]


def test_estable_y_sin_depender_del_orden():
    base = _bp()
    assert _bp() == base
    docs, entradas, resumenes = documentos(), lel(), trazas()
    for semilla in (1, 2, 3):
        random.Random(semilla).shuffle(docs)
        random.Random(semilla).shuffle(entradas)
        random.Random(semilla).shuffle(resumenes)
        assert _bp(docs=docs, entradas=entradas, resumenes=resumenes) == base
