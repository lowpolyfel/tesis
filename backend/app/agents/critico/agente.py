"""Agente Crítico: evalúa interpretaciones contra reglas y arbitra. No genera interpretaciones."""
from __future__ import annotations

from app.llm import ClienteLLM, Respuesta, cargar_prompt, generar
from app.models import (
    EntradaLEL,
    EvaluacionInterpretacion,
    Interpretacion,
    Objecion,
    Regla,
    ResultadoRegla,
    RondaDebate,
    SalidaArbitraje,
    SalidaCriticoEvaluacion,
    SalidaR3LLM,
)
from app.nlp import normalizar

from ..base import a_json, texto_contexto
from .reglas import ReglasCritico


class Critico:
    def __init__(self, cliente: ClienteLLM, reglas: ReglasCritico,
                 prompt: str = "critico_v1", prompt_arbitraje: str = "critico_arbitraje_v2"):
        self.cliente = cliente
        self.reglas = reglas
        self.prompt = cargar_prompt(prompt)
        self.prompt_arbitraje = cargar_prompt(prompt_arbitraje)

    def evaluar(self, texto: str, termino: str, interpretaciones: list[Interpretacion],
                lel: list[EntradaLEL]) -> Respuesta[SalidaCriticoEvaluacion]:
        ids = {i.id for i in interpretaciones}

        def verificar(s: SalidaR3LLM) -> None:
            recibidos = [e.interpretacion_id for e in s.evaluaciones]
            if set(recibidos) != ids or len(recibidos) != len(ids):
                raise ValueError(f"debe evaluar exactamente una vez cada interpretación {sorted(ids)}")

        prompt = self.prompt.renderizar(texto=texto, termino=termino, interpretaciones=a_json(interpretaciones), lel=a_json(lel))
        r3 = generar(self.cliente, prompt, SalidaR3LLM, verificar=verificar)
        r3_por_id = {e.interpretacion_id: e for e in r3.valor.evaluaciones}

        evaluaciones, objeciones = [], []
        for interp in interpretaciones:
            r1, r1_estricta = self.reglas.r1(texto, interp, lel)
            r2, r2_estricta = self.reglas.r2(texto, interp, lel)
            e3 = r3_por_id[interp.id]
            # Se registra (sin decidir) si la evidencia es de verdad una cita de la paráfrasis.
            cita = normalizar(e3.evidencia).strip(" «»\"'.") in normalizar(interp.parafrasis_del_requisito)
            r3_res = ResultadoRegla(regla=Regla.R3, cumple=e3.cumple, evidencia=e3.evidencia,
                                    detalle={"evidencia_es_cita_de_la_parafrasis": cita})
            evaluaciones.append(EvaluacionInterpretacion(interpretacion_id=interp.id, reglas=[r1, r2, r3_res],
                                                         r1_estricta=r1_estricta, r2_estricta=r2_estricta))
            for r in (r1, r2):
                if not r.cumple:
                    objeciones.append(Objecion(interpretacion_id=interp.id, regla=r.regla, texto=r.evidencia))
            if not e3.cumple:
                objeciones.append(Objecion(interpretacion_id=interp.id, regla=Regla.R3, texto=e3.objecion or e3.evidencia))

        salida = SalidaCriticoEvaluacion(evaluaciones=evaluaciones, objeciones=objeciones)
        return Respuesta(salida, r3.modelo, r3.prompt_version, r3.intentos)

    def arbitrar(self, texto: str, termino: str, interpretaciones: list[Interpretacion], lel: list[EntradaLEL],
                 historial: list[RondaDebate], contexto: str | None = None) -> Respuesta[SalidaArbitraje]:
        ids = {i.id for i in interpretaciones}

        def verificar(s: SalidaArbitraje) -> None:
            if s.interpretacion_elegida not in ids:
                raise ValueError(f"interpretacion_elegida debe ser una de {sorted(ids)}")

        variables = {"texto": texto, "termino": termino, "interpretaciones": a_json(interpretaciones),
                     "lel": a_json(lel), "historial": a_json(historial)}
        if "${contexto}" in self.prompt_arbitraje.usuario:
            variables["contexto"] = texto_contexto(contexto)
        prompt = self.prompt_arbitraje.renderizar(**variables)
        return generar(self.cliente, prompt, SalidaArbitraje, verificar=verificar)
