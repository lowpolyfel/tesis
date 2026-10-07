"""Caminos reales del grafo (LLM y embeddings falsos) para probar las vistas derivadas.

`montar_proyecto` arma un proyecto de dos ciclos que recorre todos los caminos:
aceptado directo, consenso (con elección de una interpretación retirada),
vaguedad rechazada, término resuelto por el LEL, regional arbitrado, anáfora y
error. «sesión» queda validada con dos significados distintos (inconsistencia).
"""
from __future__ import annotations

from app.analisis import formas, vista_requisito
from app.models import Interpretacion, Mensaje, Traza, Validacion
from tests.escenarios import (
    EXTRACCION_SESION,
    I1,
    I2,
    MODELADO,
    P1_CERCANA,
    SESION,
    VECTORES,
    clasificacion,
    montar,
)
from tests.fakes import EmbeddingsFalsos, interp, r3_todas

APROBAR = Validacion(decision="aprobar")
JUSTIFICACION = [{"regla": r, "argumento": f"argumento {r}"} for r in ("R1", "R2", "R3")]
I2_CERCANA = interp("I2", "periodo de uso", P1_CERCANA)

CERRAR = "El sistema debe cerrar la sesión del usuario."
AHORITA = "El sistema debe responder ahorita."
GUARDAR = "El sistema debe guardar la sesión del usuario."
JALAR = "El sistema debe jalar los datos del servidor."
CUENTA = "El administrador debe notificar al usuario cuando su cuenta expire."
IMPRIMIR = "El sistema debe imprimir el reporte."

C1 = interp("I1", "periodo de uso", "El sistema debe cerrar el periodo de uso del usuario.")
C2 = interp("I2", "evento de conexión", "El sistema debe cerrar la conexión del usuario.")
J1 = interp("I1", "consultar", "El sistema debe consultar los datos del servidor.")
J2 = interp("I2", "descargar", "El sistema debe descargar los datos del servidor.")
PA = "El administrador debe notificar al usuario cuando la cuenta del administrador expire."
PU = "El administrador debe notificar al usuario cuando la cuenta del usuario expire."
VECTORES_PROYECTO = {**VECTORES, C1["parafrasis_del_requisito"]: [1.0, 0.0], C2["parafrasis_del_requisito"]: [0.0, 1.0],
                     J1["parafrasis_del_requisito"]: [1.0, 0.0], J2["parafrasis_del_requisito"]: [0.0, 1.0]}
NOCION_CONEXION = {"entrada_lel": {"simbolo": "sesión", "tipo": "objeto", "nocion": ["Evento de conexión al sistema."],
                                   "impacto": ["Se registra al conectarse."]}}


def extraccion(*pares: tuple[str, str]) -> dict:
    return {"terminos": [{"termino": t, "categoria_tentativa": c} for t, c in pares]}


def segun_texto(tabla: dict):
    """Guion que responde según el requisito que aparece en el prompt; las listas se consumen en orden."""
    colas = {k: (list(v) if isinstance(v, list) else v) for k, v in tabla.items()}

    def responder(prompt):
        for texto, r in colas.items():
            if f"«{texto}»" in prompt.usuario or texto in prompt.usuario:
                return r.pop(0) if isinstance(r, list) else (r(prompt) if callable(r) else r)
        raise AssertionError(f"sin guion para el prompt {prompt.version}")

    return responder


def vista(srv, req_id: str) -> dict:
    """La vista tal como la sirve la ruta, validada contra su forma exacta."""
    v = vista_requisito(srv.traza(req_id), srv.repo.obtener_doc("formalizados", req_id))
    formas.VistaRequisito.model_validate(v)
    return v


def termino(v: dict, nombre: str) -> dict:
    return next(t for t in v["terminos"] if t["termino"] == nombre)


def insertar(traza: Traza, antes_de: int, nuevos: list[dict]) -> Traza:
    """Simula un nodo reejecutado tras un reinicio: `nuevos` quedan en la traza antes
    del mensaje `antes_de` y se renumera todo lo posterior, como lo haría el repositorio."""
    mensajes: list[Mensaje] = []
    for m in sorted(traza.mensajes, key=lambda m: m.secuencia):
        if m.secuencia == antes_de:
            mensajes += [Mensaje(req_id=traza.req_id, secuencia=1, **n) for n in nuevos]
        mensajes.append(m)
    mensajes = [m.model_copy(update={"secuencia": i}) for i, m in enumerate(mensajes, 1)]
    transiciones = [t.model_copy(update={"secuencia": t.secuencia + (len(nuevos) if t.secuencia >= antes_de else 0)})
                    for t in traza.transiciones]
    return traza.model_copy(update={"mensajes": mensajes, "transiciones": transiciones})


TURNO = "El sistema debe registrar la sesión y el turno del usuario."
T1 = interp("I1", "horario", "El sistema debe registrar la sesión y el horario del usuario.")
T2 = interp("I2", "lugar en la fila", "El sistema debe registrar la sesión y el lugar en la fila del usuario.")


def montar_dos_terminos(tmp_path, analizador):
    """Un requisito con dos términos ambiguos: «sesión» llega a consenso en la ronda 1
    (el Clasificador retira I2) y «turno» se arbitra tras dos rondas sin cambios."""
    sin_cambios = {"interpretaciones": [T1, T2]}
    srv, _, repo = montar(tmp_path, analizador, {
        "extractor_v1": [extraccion(("sesión", "objeto"), ("turno", "objeto"))],
        "clasificador_v2": [{"resultados": [
            {"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretaciones": [I1, I2]},
            {"termino": "turno", "tipo_ambiguedad": "lexica", "interpretaciones": [T1, T2]}]}],
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": [
            {"interpretaciones": [I1], "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega red"}]},
            sin_cambios, sin_cambios],
        "critico_arbitraje_v1": [{"interpretacion_elegida": "I1", "justificacion_por_regla": JUSTIFICACION}]})
    srv.deps.embeddings = EmbeddingsFalsos({**VECTORES, T1["parafrasis_del_requisito"]: [1.0, 0.0],
                                            T2["parafrasis_del_requisito"]: [0.0, 1.0]})
    return srv, repo, srv.procesar(TURNO)


def montar_proyecto(tmp_path, analizador):
    """P01 con dos ciclos. Ciclo 1: R01 directo, R02 consenso, R03 vaguedad rechazada.
    Ciclo 2: R04 resuelto por el LEL, R05 regional arbitrado, R06 anáfora, R07 error."""
    sin_cambios = {"interpretaciones": [J1, J2]}

    def univocos(*terminos: str) -> list[dict]:
        return [{"termino": t, "univoco": True} for t in terminos]

    guiones = {
        "extractor_v1": segun_texto({
            SESION: EXTRACCION_SESION,
            CERRAR: extraccion(("sistema", "sujeto"), ("cerrar", "verbo"), ("sesión", "objeto")),
            AHORITA: extraccion(("sistema", "sujeto"), ("responder", "verbo"), ("ahorita", "estado")),
            GUARDAR: extraccion(("sistema", "sujeto"), ("guardar", "verbo"), ("sesión", "objeto")),
            JALAR: extraccion(("sistema", "sujeto"), ("datos", "objeto")),
            CUENTA: extraccion(("administrador", "sujeto"), ("usuario", "sujeto")),
            IMPRIMIR: ["no es json", "{roto"],
        }),
        "clasificador_v2": segun_texto({
            SESION: clasificacion(I1, I2_CERCANA),
            CERRAR: {"resultados": univocos("sistema", "cerrar") + [
                {"termino": "sesión", "tipo_ambiguedad": "lexica", "interpretaciones": [C1, C2]}]},
            AHORITA: {"resultados": univocos("sistema", "responder")},
            GUARDAR: {"resultados": univocos("sistema", "guardar")},
            JALAR: {"resultados": univocos("sistema", "datos") + [
                {"termino": "jalar", "tipo_ambiguedad": "lexica", "interpretaciones": [J1, J2]}]},
            CUENTA: {"resultados": univocos("administrador", "usuario") + [
                {"termino": "su cuenta", "tipo_ambiguedad": "anaforica", "interpretaciones": [
                    interp("I1", "la cuenta del administrador", PA), interp("I2", "la cuenta del usuario", PU)]}]},
        }),
        "critico_v1": r3_todas(False),
        "clasificador_refinamiento_v1": segun_texto({
            CERRAR: [{"interpretaciones": [C1], "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega red"}]}],
            JALAR: [sin_cambios, sin_cambios],
        }),
        "critico_arbitraje_v1": segun_texto({JALAR: [{"interpretacion_elegida": "I2",
                                                      "justificacion_por_regla": JUSTIFICACION}]}),
        "modelador_v1": segun_texto({SESION: MODELADO, CERRAR: NOCION_CONEXION}),
    }
    srv, _, repo = montar(tmp_path, analizador, guiones)
    srv.deps.embeddings = EmbeddingsFalsos(VECTORES_PROYECTO)
    p = srv.proyectos.crear("Banca", "Proyecto de prueba de las vistas")
    ids = [srv.procesar(t, p.proyecto_id, ciclo=1) for t in (SESION, CERRAR, AHORITA)]
    srv.validar(ids[0], APROBAR)
    srv.validar(ids[1], Validacion(decision="aprobar", interpretaciones_editadas={"sesión": Interpretacion(**C2)}))
    srv.validar(ids[2], Validacion(decision="rechazar", comentario="falta una métrica"))
    ids += [srv.procesar(t, p.proyecto_id, ciclo=2) for t in (GUARDAR, JALAR, CUENTA, IMPRIMIR)]
    return srv, repo, p, ids
