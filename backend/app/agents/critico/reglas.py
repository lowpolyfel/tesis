"""Reglas verificables del Crítico, versión v1 provisional (ADR 0004).

R1 y R2 se evalúan en código con spaCy; R3 la juzga el LLM. De R1 y R2 se
calculan dos versiones:

- relajada (decide): vocabulario permitido = requisito + LEL + significado de la
  propia interpretación;
- estricta (solo se registra): vocabulario permitido = requisito + LEL.

La evidencia separa lo que aportó el `significado` de lo que aportó el resto
de la paráfrasis.
"""
from __future__ import annotations

from app.models import EntradaLEL, Interpretacion, Regla, ResultadoRegla
from app.nlp import Analizador, Unidad


def _formas(d: dict[str, Unidad], claves) -> list[str]:
    return sorted(d[k].texto for k in claves)


def _fuera_de(d: dict[str, Unidad], vocabulario: set[str]) -> set[str]:
    """Claves de `d` cuyo lema y forma están ambos fuera del vocabulario."""
    return {k for k, u in d.items() if not (u.claves & vocabulario)}


class ReglasCritico:
    def __init__(self, analizador: Analizador):
        self.analizador = analizador

    def _vocabulario_lel(self, lel: list[EntradaLEL]) -> set[str]:
        # Cada pieza por separado: concatenarlas cambia el análisis de spaCy.
        claves: set[str] = set()
        for e in lel:
            for pieza in (e.simbolo, *e.nocion, *e.impacto):
                claves |= self.analizador.vocabulario(pieza)
        return claves

    def _evaluar(self, regla: Regla, que: str, extraer, texto: str, interp: Interpretacion,
                 lel: list[EntradaLEL]) -> tuple[ResultadoRegla, ResultadoRegla]:
        # Lo que se revisa (paráfrasis y significado) se filtra por categoría;
        # lo que permite (requisito, LEL, significado) se toma completo.
        base = self.analizador.vocabulario(texto) | self._vocabulario_lel(lel)
        vocab_significado = self.analizador.vocabulario(interp.significado)
        significado = extraer(interp.significado)
        parafrasis = extraer(interp.parafrasis_del_requisito)

        nuevos_parafrasis = _fuera_de(parafrasis, base)
        no_justificados = {k for k in nuevos_parafrasis if not (parafrasis[k].claves & vocab_significado)}
        cubiertos = nuevos_parafrasis - no_justificados
        nuevos_significado = _fuera_de(significado, base)

        detalle = {
            "nuevos_en_parafrasis": _formas(parafrasis, nuevos_parafrasis),
            "de_ellos_cubiertos_por_significado": _formas(parafrasis, cubiertos),
            "de_ellos_no_justificados": _formas(parafrasis, no_justificados),
            "nuevos_en_significado": _formas(significado, nuevos_significado),
        }

        relajada_cumple = not no_justificados
        evidencia_relajada = (
            f"Sin {que} fuera del requisito, el LEL y el significado."
            if relajada_cumple
            else f"La paráfrasis introduce {que} no justificados: {', '.join(detalle['de_ellos_no_justificados'])}."
        )
        if cubiertos:
            evidencia_relajada += f" Aportados por el significado: {', '.join(detalle['de_ellos_cubiertos_por_significado'])}."

        estricta_cumple = not (nuevos_parafrasis or nuevos_significado)
        evidencia_estricta = (
            f"Sin {que} fuera del requisito y el LEL."
            if estricta_cumple
            else f"Fuera del requisito y el LEL — en la paráfrasis: {', '.join(detalle['nuevos_en_parafrasis']) or 'ninguno'};"
                 f" en el significado: {', '.join(detalle['nuevos_en_significado']) or 'ninguno'}."
        )
        return (
            ResultadoRegla(regla=regla, cumple=relajada_cumple, evidencia=evidencia_relajada,
                           detalle={**detalle, "version": "relajada", "permitido": "requisito+lel+significado"}),
            ResultadoRegla(regla=regla, cumple=estricta_cumple, evidencia=evidencia_estricta,
                           detalle={**detalle, "version": "estricta", "permitido": "requisito+lel"}),
        )

    def r1(self, texto: str, interp: Interpretacion, lel: list[EntradaLEL]) -> tuple[ResultadoRegla, ResultadoRegla]:
        """R1 Consistencia de vocabulario: lemas de contenido (sustantivo, verbo, adjetivo, adverbio)."""
        return self._evaluar(Regla.R1, "términos de contenido", self.analizador.lemas_contenido, texto, interp, lel)

    def r2(self, texto: str, interp: Interpretacion, lel: list[EntradaLEL]) -> tuple[ResultadoRegla, ResultadoRegla]:
        """R2 Sin entidades nuevas: sustantivos y entidades nombradas."""
        return self._evaluar(Regla.R2, "sustantivos o entidades", self.analizador.sustantivos_y_entidades, texto, interp, lel)
