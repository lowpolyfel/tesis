"""Escenario de la versión 2 (ADR 0024): la entrevista del consultorio, con guiones de LLM falso.

«consultas» es el caso de la tesis: puede ser la cita médica o una búsqueda en la base de
datos. Sus paráfrasis tienen vectores ortogonales: los agentes debaten dos rondas y el Crítico
arbitra. «dar de alta» sale del catálogo regional con dos intenciones parecidas: se acepta
directo. Los demás términos son unívocos.
"""
import json
import re

from langgraph.checkpoint.memory import InMemorySaver

from app.config import Settings
from app.db import RepositorioJson
from app.orchestration import Servicio, armar
from tests.fakes import USUARIO_PRUEBA, EmbeddingsFalsos, LLMFalso

ENTREVISTA = """Entrevista con la Dra. Ruiz
Entrevistador: ¿Qué necesita registrar, doctora?
Dra. Ruiz: Quiero registrar las consultas de mis pacientes. Ahorita todo es en papel.
Entrevistador: ¿Quién agenda las citas?
Dra. Ruiz: Mi asistente da de alta a los pacientes nuevos y agenda las citas.
Entrevistador: ¿Qué lleva una consulta?
Dra. Ruiz: El motivo, el diagnóstico y la receta. Las consultas se guardan en el expediente del paciente.
"""

P_CITA = "Quiero registrar las citas médicas de mis pacientes."
P_BD = "Quiero registrar las búsquedas en la base de datos de mis pacientes."
VECTORES = {P_CITA: [1.0, 0.0, 0.0], P_BD: [0.0, 1.0, 0.0]}

SIMBOLO = {"consultas": "consulta", "pacientes": "paciente", "asistente": "asistente", "citas": "cita",
           "expediente": "expediente", "receta": "receta", "da de alta": "dar de alta", "dar de alta": "dar de alta"}
TIPO = {"consulta": "objeto", "paciente": "sujeto", "asistente": "sujeto", "cita": "objeto",
        "expediente": "objeto", "receta": "objeto", "dar de alta": "verbo"}


def terminos_del_prompt(prompt) -> list[str]:
    return re.findall(r'"termino": "([^"]+)"', prompt.usuario)


def ids_del_prompt(prompt) -> list[str]:
    return sorted(set(re.findall(r'"id": "(I\d+)"', prompt.usuario)))


def revisor(prompt):
    return {"participantes": [{"nombre": "Dra. Ruiz", "rol": "médica del consultorio"},
                              {"nombre": "asistente", "rol": "agenda las citas"}],
            "objetivo": "Dejar de llevar las consultas en papel",
            "problemas": [{"texto": "Todo se lleva en papel", "turnos": [3]}],
            "necesidades": [{"texto": "Registrar las consultas de los pacientes", "turnos": [3]},
                            {"texto": "Agendar las citas", "turnos": [5, 99]}],
            "reglas": [{"texto": "La consulta lleva motivo, diagnóstico y receta", "turnos": [7]}]}


def extractor(prompt):
    return {"terminos": [
        {"termino": "consultas", "categoria": "objeto", "turnos": [3]},
        {"termino": "pacientes", "categoria": "Actor", "turnos": [3, 5]},
        {"termino": "asistente", "categoria": "sujeto", "turnos": [5]},
        {"termino": "citas", "categoria": "objeto", "turnos": [5]},
        {"termino": "expediente", "categoria": "objeto", "turnos": [7]},
        {"termino": "receta", "categoria": "objeto", "turnos": [7]},
        {"termino": "teletransportador", "categoria": "objeto", "turnos": [2]},  # no está: se descarta
    ]}


def intencion(id_, significado, parafrasis, que="llevar el registro"):
    return {"id": id_, "significado": significado, "intencion": que, "parafrasis": parafrasis}


def clasificador(prompt):
    resultados = []
    for t in terminos_del_prompt(prompt):
        if t == "consultas":
            resultados.append({"termino": t, "tipo_ambiguedad": "léxica", "intenciones": [
                intencion("I1", "cita médica con un paciente", P_CITA, "llevar el registro de las atenciones"),
                intencion("I2", "búsqueda en la base de datos", P_BD, "saber qué se buscó")]})
        elif t in ("da de alta", "dar de alta"):
            resultados.append({"termino": t, "intenciones": [
                intencion("I1", "registrar a un paciente nuevo", "Mi asistente registra a los pacientes nuevos."),
                intencion("I2", "inscribir a un paciente nuevo", "Mi asistente inscribe a los pacientes nuevos.")]})
        else:
            resultados.append({"termino": t, "intenciones": [intencion("I1", f"el {t} del consultorio", f"el {t}")]})
    return {"resultados": resultados}


def critico(prompt):
    return {"evaluaciones": [{"interpretacion_id": i, "cumple": False, "evidencia": "registrar",
                              "objecion": "sigue siendo ambiguo"} for i in ids_del_prompt(prompt)]}


def refinamiento(prompt):
    actuales = json.loads(prompt.usuario.split("Intenciones actuales", 1)[1].split(":\n", 1)[1]
                          .split("\n\nObjeciones del Crítico", 1)[0])
    return {"interpretaciones": actuales, "retiradas": []}


def arbitraje(prompt):
    return {"interpretacion_elegida": "I1", "justificacion_por_regla": [
        {"regla": r, "argumento": "la entrevista habla de pacientes"} for r in ("R1", "R2", "R3")]}


def modelador_lexico(prompt):
    entradas = []
    for t in terminos_del_prompt(prompt):
        s = SIMBOLO.get(t, t)
        entradas.append({"termino": t, "simbolo": s, "tipo": TIPO.get(s, "objeto"), "nocion": [f"{s} del consultorio."],
                         "impacto": [f"Se usa al atender al paciente ({s})."],
                         "intencion": f"Llevar el registro de {s}", "sinonimos": [t] if t != s else []})
    return {"entradas": entradas}


def mapa(prompt):
    return {"proposito": "¿Cómo registra el consultorio las consultas de sus pacientes?", "central": "C1",
            "conceptos": [{"id": "C1", "etiqueta": "Consulta", "simbolo": "consulta"},
                          {"id": "C2", "etiqueta": "Paciente", "simbolo": "pacientes"},
                          {"id": "C3", "etiqueta": "Expediente", "simbolo": "expediente"},
                          {"id": "C4", "etiqueta": "Receta", "simbolo": None},
                          {"id": "C5", "etiqueta": "Asistente", "simbolo": "asistente"},
                          {"id": "C6", "etiqueta": "Nube", "simbolo": "nube"}],
            "relaciones": [{"origen": "C2", "enlace": "recibe", "destino": "C1"},
                           {"origen": "C1", "enlace": "se guarda en", "destino": "C3"},
                           {"origen": "C1", "enlace": "incluye", "destino": "C4"},
                           {"origen": "C5", "enlace": "da de alta a", "destino": "C2"},
                           {"origen": "C2", "enlace": "recibe", "destino": "C1"},
                           {"origen": "C1", "enlace": "se repite", "destino": "C1"}]}


def metas(prompt):
    return {"organizacionales": [{"id": "MO1", "enunciado": "Atender ordenadamente a los pacientes"}],
            "estrategicas": [{"id": "ME1", "enunciado": "Tener el historial de consultas al momento",
                              "contribuye_a": "MO1", "simbolos": ["consultas", "nube"]},
                             {"id": "ME2", "enunciado": "Agendar las citas sin papel", "contribuye_a": "MO1"}],
            "especificas": [{"id": "MS1", "enunciado": "Registrar cada consulta con motivo, diagnóstico y receta",
                             "contribuye_a": "ME1", "indicador": "el 100 % de las consultas del día",
                             "simbolos": ["consulta", "receta"], "evidencia": ["E01:T3", "E01:T7", "E09:T1"]},
                            {"id": "MS2", "enunciado": "Consultar el expediente de un paciente", "contribuye_a": "ME1",
                             "evidencia": ["e01:t7"]},
                            {"id": "MS3", "enunciado": "Agendar una cita para un paciente", "contribuye_a": "ME2",
                             "evidencia": ["E01:T5"]}]}


def requisitos(prompt):
    if "ME1:" in prompt.usuario.split("Meta estratégica:", 1)[1].split("\n", 1)[0]:
        return {"requisitos": [
            {"texto": "El sistema debe permitir que el doctor registre cada consulta de un paciente con su motivo, "
                      "diagnóstico y receta.", "tipo": "funcional", "prioridad": "alta", "metas": ["MS1"],
             "simbolos": ["consulta", "pacientes", "receta"], "evidencia": ["E01:T3", "E01:T7"],
             "criterios": ["La consulta guardada muestra motivo, diagnóstico y receta."]},
            {"texto": "El sistema debe mostrar el expediente rápido.", "tipo": "No funcional",
             "categoria": "Rendimiento", "prioridad": "media", "metas": ["MS2"], "simbolos": [],
             "evidencia": ["E01:T7"], "criterios": []}]}
    return {"requisitos": [
        {"texto": "El sistema debe permitir que el asistente agende una cita para un paciente.", "tipo": "funcional",
         "metas": ["MS3"], "simbolos": ["cita", "asistente"], "evidencia": ["E01:T5"],
         "criterios": ["La cita aparece en la agenda."], "supuestos": ["Una cita dura 30 minutos."]}]}


def guiones() -> dict:
    return {"revisor_entrevista_v1": revisor, "extractor_entrevista_v1": extractor,
            "clasificador_intencion_v1": clasificador, "critico_entrevista_v1": critico,
            "clasificador_refinamiento_entrevista_v1": refinamiento, "critico_arbitraje_entrevista_v1": arbitraje,
            "modelador_lexico_v1": modelador_lexico, "modelador_mapa_proposito_v1": mapa,
            "modelador_metas_v1": metas, "modelador_requisitos_v1": requisitos}


def montar(tmp_path, analizador, **ajustes):
    settings = Settings(_env_file=None, similarity_threshold=0.75, max_debate_rounds=2, separacion_ia=False,
                        resultados_dir=str(tmp_path / "resultados"), checkpoint_path=str(tmp_path / "cp.sqlite"),
                        **ajustes)
    llm = LLMFalso(guiones())
    repo = RepositorioJson(settings.ruta(settings.resultados_dir))
    deps = armar(settings, repo, analizador, extractor=llm, clasificador=llm, critico=llm, modelador=llm,
                 embeddings=EmbeddingsFalsos(VECTORES), comparador=llm, agente_unico=llm)
    srv = Servicio(deps, InMemorySaver())
    proyecto = srv.proyectos.crear("Consultorio", contexto="Consultorio médico de una doctora con su asistente.",
                                   propietario=USUARIO_PRUEBA.usuario_id)
    return srv, llm, proyecto
