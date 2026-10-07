"""Proyecto de ejemplo para los artefactos: documentos de `formalizados`, LEL y
resumen de trazas armados a mano (sin correr el grafo), y su siembra en un
repositorio para probar las rutas.

    R01 formalizado  «sesión» (léxica)            metas: meta + tarea del sistema
    R02 formalizado  «usuario», «bitácora»        metas: meta de «Los Usuarios» + meta blanda que recoge «ahorita»
    R03 formalizado  «dar de alta»                metas: tarea, recurso y una meta que no empieza con infinitivo;
                                                  «rápido» queda sin meta blanda
    R04 en debate · R05 rechazado · R06 formalizado pero lo reprocesa R07 (pendiente)
    R08 formalizado antes del documento por requisito (solo su entrada del LEL: «expediente»)
    R09 documento sin traza
"""
from __future__ import annotations

from app.models import EntradaLELFormalizada, Estado, Interpretacion, Origen
from tests.fakes import interp

R01_ORIGINAL = "El sistema debe registrar la sesión del usuario."
R01_REESCRITO = "El sistema debe registrar el periodo de uso del usuario."
R02_TEXTO = "Los usuarios deben consultar la bitácora ahorita."
R03_ORIGINAL = "El administrador debe dar de alta al cliente rápido para que inicie sesión."
R03_REESCRITO = "El administrador debe registrar al cliente nuevo rápido para que inicie sesión."


def meta(id_: str, enunciado: str, tipo: str = "meta", actor: str | None = None, simbolos=(),
         contribuye_a: str | None = None) -> dict:
    return {"id": id_, "enunciado": enunciado, "tipo": tipo, "actor": actor, "simbolos": list(simbolos),
            "contribuye_a": contribuye_a}


def resolucion(termino: str, significado: str, via: str = "consenso", cambio: str = "ninguno",
               tipo: str = "lexica") -> dict:
    return {"termino": termino, "tipo_ambiguedad": tipo, "interpretacion": interp("I1", significado, f"… {significado} …"),
            "via": via, "cambio": cambio}


def formalizado(req_id: str, original: str, metas: list[dict], *, reescrito: str | None = None, resoluciones=(),
                entradas_lel=(), vaguedad=(), proyecto_id: str = "P01") -> dict:
    return {"req_id": req_id, "proyecto_id": proyecto_id, "requisito_original": original,
            "requisito_reescrito": reescrito if reescrito is not None else original,
            "resoluciones": list(resoluciones), "metas": metas, "entradas_lel": list(entradas_lel), "univocos": [],
            "vaguedad": list(vaguedad), "fecha": "2026-10-06", "modelo": "llm-falso",
            "prompt_version": "modelador_requisito_v1"}


def entrada(simbolo: str, tipo: str, nocion: list[str], impacto: list[str], req_id: str, *, termino: str | None = None,
            via: str = "consenso", editada: bool = False, proyecto_id: str = "P01") -> EntradaLELFormalizada:
    return EntradaLELFormalizada(
        simbolo=simbolo, tipo=tipo, nocion=nocion, impacto=impacto, proyecto_id=proyecto_id, req_id=req_id,
        termino=termino or simbolo, via=via, editada_por_humano=editada, fecha="2026-10-06",
        interpretacion=Interpretacion.model_validate(interp("I1", nocion[0][:40], "paráfrasis")))


def resumen(req_id: str, estado: str, reproceso_de: str | None = None, proyecto_id: str = "P01") -> dict:
    return {"req_id": req_id, "proyecto_id": proyecto_id, "ciclo": 1, "texto": f"texto de {req_id}",
            "origen": {"reproceso_de": reproceso_de} if reproceso_de else None, "estado": estado,
            "creado": "2026-10-06T00:00:00Z", "actualizado": "2026-10-06T00:00:00Z"}


def documentos(proyecto_id: str = "P01") -> list[dict]:
    p = proyecto_id
    return [
        formalizado("R01", R01_ORIGINAL, [
            meta("M1", "Registrar el periodo de uso del usuario", actor="El sistema", simbolos=["sesión"]),
            meta("M2", "Guardar la hora de inicio y de cierre", "tarea", actor="sistema",
                 simbolos=["sesión", "hora de inicio"], contribuye_a="M1"),
        ], reescrito=R01_REESCRITO, resoluciones=[resolucion("sesión", "periodo de uso")], entradas_lel=["sesión"],
            proyecto_id=p),
        formalizado("R02", R02_TEXTO, [
            meta("M1", "Consultar la bitácora", actor="Los Usuarios", simbolos=["bitácora"]),
            meta("M2", "Responder ahorita", "meta_blanda", contribuye_a="M1"),
        ], resoluciones=[resolucion("usuario", "persona que usa el sistema", "aceptado_directo"),
                         resolucion("bitácora", "registro de auditoría", "arbitraje", "edicion")],
            entradas_lel=["usuario", "bitácora"], vaguedad=["ahorita"], proyecto_id=p),
        formalizado("R03", R03_ORIGINAL, [
            meta("M1", "Dar de alta al cliente", "tarea", actor="Administrador", simbolos=["dar de alta", "cliente"],
                 contribuye_a="M3"),
            meta("M2", "Expediente del cliente", "recurso", simbolos=["cliente"], contribuye_a="M1"),
            meta("M3", "Que el cliente quede registrado", actor="el administrador"),
        ], reescrito=R03_REESCRITO, resoluciones=[resolucion("dar de alta", "registrar", cambio="eleccion")],
            entradas_lel=["dar de alta"], vaguedad=["rápido"], proyecto_id=p),
        formalizado("R06", "El sistema debe imprimir el reporte.", [
            meta("M1", "Imprimir el reporte", actor="El sistema", simbolos=["reporte"])], proyecto_id=p),
        formalizado("R09", "El sistema debe enviar avisos.", [
            meta("M1", "Enviar avisos", actor="El sistema")], proyecto_id=p),
    ]


def lel(proyecto_id: str = "P01") -> list[EntradaLELFormalizada]:
    p = proyecto_id
    return [
        entrada("sesión", "objeto", ["Periodo de uso continuo del sistema por un usuario."],
                ["Se registra al iniciar y al cerrar."], "R01", proyecto_id=p),
        entrada("usuario", "sujeto", ["Persona que usa el sistema."], ["Inicia una sesión."], "R02",
                via="aceptado_directo", proyecto_id=p),
        entrada("bitácora", "objeto", ["Registro de eventos de auditoría."], ["El administrador la consulta."], "R02",
                via="arbitraje", editada=True, proyecto_id=p),
        entrada("dar de alta", "verbo", ["Registrar a un usuario nuevo en el sistema."],
                ["El usuario puede iniciar sesión."], "R03", proyecto_id=p),
        entrada("expediente", "objeto", ["Conjunto de documentos del trámite."], ["Se archiva al cerrar el trámite."],
                "R08", proyecto_id=p),
    ]


def trazas(proyecto_id: str = "P01") -> list[dict]:
    p = proyecto_id
    return [resumen("R01", "formalizado", proyecto_id=p), resumen("R02", "formalizado", proyecto_id=p),
            resumen("R03", "formalizado", proyecto_id=p), resumen("R04", "en_debate", proyecto_id=p),
            resumen("R05", "rechazado", proyecto_id=p), resumen("R06", "formalizado", proyecto_id=p),
            resumen("R07", "pendiente_validacion", "R06", proyecto_id=p), resumen("R08", "formalizado", proyecto_id=p)]


def sembrar(repo, proyecto_id: str) -> None:
    """Las trazas R01..R08 (en orden, para que los req_id coincidan), los documentos
    de `formalizados` y el LEL del proyecto de ejemplo."""
    for r in trazas(proyecto_id):
        origen = Origen(reproceso_de=r["origen"]["reproceso_de"]) if r["origen"] else None
        t = repo.crear_traza(r["texto"], {}, proyecto_id=proyecto_id, origen=origen)
        assert t.req_id == r["req_id"], "el repositorio debe estar vacío antes de sembrar"
        if r["estado"] != Estado.CARGADO.value:
            repo.cambiar_estado(t.req_id, Estado(r["estado"]))
    for d in documentos(proyecto_id):
        repo.guardar_doc("formalizados", d["req_id"], d)
    repo.guardar_lel(lel(proyecto_id))
