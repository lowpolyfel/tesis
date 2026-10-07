"""Qué texto se compara de cada requisito y qué significados quedaron validados.

Funciones puras sobre las trazas y los documentos de `formalizados`.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models import TIPOS_QUE_VAN_AL_LEL, Estado, TipoMensaje, Traza

from .modelos import Excluido, RequisitoBase

EXCLUIR = {Estado.ERROR: "error", Estado.RECHAZADO: "rechazado"}
_TIPOS_LEXICOS = {t.value for t in TIPOS_QUE_VAN_AL_LEL}


def numero(req_id: str) -> int:
    return int(req_id[1:]) if req_id[1:].isdigit() else 0


def bases_de_comparacion(trazas: list[Traza], formalizados: dict[str, dict]) -> tuple[list[RequisitoBase], list[Excluido]]:
    """Base = `requisito_reescrito` si el requisito se formalizó; si no, el texto original.

    Se excluyen los requisitos en `error` o `rechazado` y los que otro requisito
    (no excluido) vuelve a procesar: compararlos con su propia versión nueva
    solo produciría un duplicado obvio. La cadena se sigue hacia atrás: si R02
    reprocesa R01 y falla, y R03 reprocesa R02, R03 sustituye también a R01.
    """
    anterior = {t.req_id: t.origen.reproceso_de for t in trazas if t.origen and t.origen.reproceso_de}
    reprocesado_en: dict[str, str] = {}
    for t in trazas:
        if t.estado in EXCLUIR:
            continue
        r = anterior.get(t.req_id)
        while r is not None and r not in reprocesado_en:  # lo ya marcado ya tiene marcada su cadena (y corta ciclos)
            reprocesado_en[r] = t.req_id
            r = anterior.get(r)
    requisitos, excluidos = [], []
    for t in sorted(trazas, key=lambda t: (numero(t.req_id), t.req_id)):
        if t.estado in EXCLUIR:
            excluidos.append(Excluido(req_id=t.req_id, estado=t.estado.value, motivo=EXCLUIR[t.estado]))
        elif t.req_id in reprocesado_en:
            excluidos.append(Excluido(req_id=t.req_id, estado=t.estado.value, motivo="reprocesado",
                                      detalle=f"lo vuelve a procesar {reprocesado_en[t.req_id]}"))
        else:
            reescrito = ((formalizados.get(t.req_id) or {}).get("requisito_reescrito") or "").strip()
            requisitos.append(RequisitoBase(req_id=t.req_id, base="reescrito" if reescrito else "original",
                                            texto=reescrito or t.texto))
    return requisitos, excluidos


@dataclass(frozen=True)
class SignificadoValidado:
    req_id: str
    termino: str
    significado: str


def _ultimo(traza: Traza, tipo: TipoMensaje):
    return next((m for m in reversed(traza.mensajes) if m.tipo == tipo), None)


def significados_validados(traza: Traza, formalizado: dict | None) -> list[SignificadoValidado]:
    """Significado que aprobó el humano por término, de las `resoluciones` del documento
    formalizado o, si no lo hay, del último mensaje `validacion` aprobado.

    Solo ambigüedad léxica (o sin tipo, trazas anteriores al tipo): el referente de
    una anáfora o el alcance de un cuantificador son propios de cada requisito y que
    difieran entre requisitos no es una inconsistencia de vocabulario.
    """
    if formalizado and formalizado.get("resoluciones") is not None:
        filas = [(r.get("termino"), r.get("tipo_ambiguedad"), (r.get("interpretacion") or {}).get("significado"))
                 for r in formalizado["resoluciones"]]
    else:
        validacion = _ultimo(traza, TipoMensaje.VALIDACION)
        if validacion is None or validacion.payload.get("decision") != "aprobar":
            return []
        solicitud = _ultimo(traza, TipoMensaje.SOLICITUD_VALIDACION)
        tipos = {t.get("termino"): t.get("tipo_ambiguedad") for t in (solicitud.payload.get("terminos", []) if solicitud else [])}
        filas = [(t.get("termino"), tipos.get(t.get("termino")), (t.get("final") or {}).get("significado"))
                 for t in validacion.payload.get("terminos", [])]
    return [SignificadoValidado(traza.req_id, termino, significado) for termino, tipo, significado in filas
            if termino and significado and (tipo is None or tipo in _TIPOS_LEXICOS)]
