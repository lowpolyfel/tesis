"""De punta a punta con el grafo real (LLM y embeddings falsos): un requisito
procesado, validado y formalizado aparece en el modelo de metas y en el Big
Picture tal como lo escribió el Modelador."""
from app.artefactos import big_picture_proyecto, formas, metas_proyecto
from app.models import Estado, Validacion
from tests.escenarios import SESION, guiones_sesion_cercana, montar

METAS = {"requisito_reescrito": "El sistema debe registrar el periodo de uso del usuario.", "tipo_requisito": "funcional", "metas": [
    {"id": "M1", "enunciado": "Registrar el periodo de uso del usuario", "tipo": "meta", "actor": "El sistema",
     "simbolos": ["sesión"], "contribuye_a": None},
    {"id": "M2", "enunciado": "Conservar el historial de sesiones", "tipo": "recurso", "actor": None,
     "simbolos": ["sesión"], "contribuye_a": "M1"}]}


def test_formalizado_por_el_grafo(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, {**guiones_sesion_cercana(), "modelador_requisito_v2": [METAS]})
    p = srv.proyectos.crear("Con grafo")
    req_id = srv.procesar(SESION, p.proyecto_id)
    assert srv.traza(req_id).estado == Estado.PENDIENTE_VALIDACION

    pendiente = big_picture_proyecto(repo.listar_docs("formalizados", proyecto_id=p.proyecto_id),
                                     repo.listar_lel(p.proyecto_id), repo.listar_trazas(p.proyecto_id), analizador)
    assert pendiente["nodos"] == [] and pendiente["requisitos_fuera"][0]["motivo"] == "en_proceso"

    srv.validar(req_id, Validacion(decision="aprobar"))
    assert srv.traza(req_id).estado == Estado.FORMALIZADO
    insumos = (repo.listar_docs("formalizados", proyecto_id=p.proyecto_id), repo.listar_lel(p.proyecto_id),
               repo.listar_trazas(p.proyecto_id))

    m = metas_proyecto(*insumos, analizador)
    formas.MetasProyecto.model_validate(m)
    assert [(x["id"], x["actor"], x["contribuye_a"]) for x in m["metas"]] == [
        (f"{req_id}.M1", "sistema", None), (f"{req_id}.M2", None, f"{req_id}.M1")]
    assert m["por_tipo"] == {"meta": 1, "meta_blanda": 0, "tarea": 0, "recurso": 1}

    bp = big_picture_proyecto(*insumos, analizador)
    formas.BigPicture.model_validate(bp)
    aristas = {(a["origen"], a["relacion"], a["destino"]) for a in bp["aristas"]}
    assert {(req_id, "resuelve", "simbolo:sesion"), (f"{req_id}.M1", "usa", "simbolo:sesion"),
            (f"{req_id}.M2", "usa", "simbolo:sesion"), ("actor:sistema", "persigue", f"{req_id}.M1"),
            (f"{req_id}.M2", "contribuye_a", f"{req_id}.M1")} <= aristas
    assert bp["panorama"]["terminos_resueltos"] == [
        {"termino": "sesión", "significado": "periodo de uso", "via": "aceptado_directo", "tipo_ambiguedad": "lexica",
         "cambio": "ninguno", "req_id": req_id}]
    assert bp["panorama"]["requisitos"] == [{"req_id": req_id, "requisito_reescrito": METAS["requisito_reescrito"]}]
