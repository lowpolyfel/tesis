"""Resumen, ambigüedades e indicadores del flujo KMoS-SSA de un proyecto de dos
ciclos armado con el grafo real (ver `caminos.montar_proyecto`)."""
from app.analisis import (
    ambiguedades_proyecto,
    flujo_proyecto,
    formas,
    resumen_proyecto,
    resumen_requisito,
)


def _datos(proyecto):
    _, repo, p, _ = proyecto
    return p, repo.trazas_completas(p.proyecto_id), repo.listar_lel(p.proyecto_id)


# ---------------------------------------------------------------- resumen

def test_resumen_del_proyecto(proyecto):
    p, trazas, lel = _datos(proyecto)
    r = resumen_proyecto(p, trazas, lel)
    formas.ResumenProyecto.model_validate(r)
    assert r["proyecto"]["proyecto_id"] == p.proyecto_id and r["proyecto"]["nombre"] == "Banca"
    assert r["contadores"] == {"requisitos": 7, "ciclos": 2, "en_proceso": 0, "por_validar": 3, "formalizados": 2,
                               "rechazados": 1, "errores": 1, "ambiguos": 4, "lel": 2}
    assert {k: n for k, n in r["por_estado"].items() if n} == {
        "formalizado": 2, "rechazado": 1, "pendiente_validacion": 3, "error": 1}
    assert set(r["por_estado"]) == {e for e in formas.Estado}
    assert [(c["ciclo"], c["requisitos"]) for c in r["por_ciclo"]] == [(1, 3), (2, 4)]
    assert {k: n for k, n in r["por_ciclo"][0]["por_estado"].items() if n} == {"formalizado": 2, "rechazado": 1}
    assert [x["req_id"] for x in r["requisitos"]] == ["R01", "R02", "R03", "R04", "R05", "R06", "R07"]
    assert r["requisitos"] == [resumen_requisito(t) for t in trazas]
    assert [x["via"] for x in r["requisitos"]] == [
        "aceptado_directo", "consenso", None, None, "arbitraje", "aceptado_directo", None]
    assert r["requisitos"][2]["vaguedad"] == ["ahorita"] and r["requisitos"][4]["rondas_max"] == 2


def test_proyecto_vacio():
    from app.models import Proyecto

    p = Proyecto(proyecto_id="P09", nombre="Vacío")
    r = resumen_proyecto(p, [], [])
    formas.ResumenProyecto.model_validate(r)
    assert r["contadores"]["requisitos"] == 0 and r["por_ciclo"] == [] and r["requisitos"] == []
    f = flujo_proyecto([], [])
    formas.FlujoProyecto.model_validate(f)
    assert f["ciclos"] == [] and f["total"]["requisitos"] == 0 and f["total"]["duracion_s"] is None
    a = ambiguedades_proyecto([], [])
    formas.AmbiguedadesProyecto.model_validate(a)
    assert a["terminos"] == [] and a["totales"]["inconsistentes"] == 0


# ---------------------------------------------------------------- ambigüedades

def test_ambiguedades_agrupadas_por_termino_con_inconsistencia(proyecto):
    _, trazas, lel = _datos(proyecto)
    a = ambiguedades_proyecto(trazas, lel)
    formas.AmbiguedadesProyecto.model_validate(a)
    assert [g["clave"] for g in a["terminos"]] == ["sesion", "jalar", "su cuenta"]  # inconsistentes primero

    sesion = a["terminos"][0]
    assert (sesion["termino"], sesion["tipos"], sesion["origenes"]) == ("sesión", ["lexica"], ["extractor"])
    assert [(ap["req_id"], ap["ciclo"], ap["estado"], ap["decision_filtro"], ap["via"], ap["rondas"])
            for ap in sesion["apariciones"]] == [
        ("R01", 1, "formalizado", "candidato", "aceptado_directo", 0),
        ("R02", 1, "formalizado", "candidato", "consenso", 1),
        ("R04", 2, "pendiente_validacion", "resuelto_por_lel", None, 0)]
    r01, r02, r04 = sesion["apariciones"]
    assert (r01["interpretacion_final"], r01["propuesta"]) == ("periodo de uso", "periodo de uso")
    # en R02 el humano eligió la interpretación que el debate había retirado
    assert (r02["interpretacion_final"], r02["propuesta"]) == ("evento de conexión", "periodo de uso")
    assert r01["similitud_inicial"] >= 0.75 and r02["similitud_inicial"] == 0.0
    assert r04["tipo_ambiguedad"] is None and r04["interpretacion_final"] is None

    assert sesion["inconsistente"] is True
    d = sesion["detalle_inconsistencia"]
    assert d["significados"] == [{"significado": "periodo de uso", "req_ids": ["R01"]},
                                 {"significado": "evento de conexión", "req_ids": ["R02"]}]
    assert [(e["simbolo"], e["req_id"], e["nocion"]) for e in d["lel"]] == [
        ("sesión", "R01", ["Periodo de uso del sistema."]), ("sesión", "R02", ["Evento de conexión al sistema."])]
    assert "2 significados distintos" in d["texto"] and "nociones distintas" in d["texto"]

    jalar = a["terminos"][1]
    assert (jalar["origenes"], jalar["inconsistente"], jalar["detalle_inconsistencia"]) == (["regional"], False, None)
    (ap,) = jalar["apariciones"]
    assert (ap["via"], ap["rondas"], ap["propuesta"], ap["interpretacion_final"]) == ("arbitraje", 2, "descargar", None)
    cuenta = a["terminos"][2]
    assert (cuenta["tipos"], cuenta["origenes"]) == (["anaforica"], ["anafora"])

    assert a["vaguedad"] == [{"termino": "ahorita", "req_ids": ["R03"]}]
    assert a["regionales"] == [{"termino": "jalar", "req_ids": ["R05"]}]
    (e,) = a["estructuras"]
    assert (e["termino"], e["decision_filtro"], e["req_id"]) == ("su cuenta", "anafora", "R06") and e["detalle"]
    assert a["totales"] == {"por_tipo": {"lexica": 3, "alcance": 0, "anaforica": 1, "sintactica": 0},
                            "por_via": {"aceptado_directo": 2, "consenso": 1, "arbitraje": 1, "sin_resolver": 0},
                            "inconsistentes": 1}


def test_inconsistencia_solo_por_el_lel(proyecto):
    """Si la traza de R02 ya no está, el LEL sigue delatando las dos nociones de «sesión»."""
    _, trazas, lel = _datos(proyecto)
    a = ambiguedades_proyecto([t for t in trazas if t.req_id != "R02"], lel)
    sesion = next(g for g in a["terminos"] if g["clave"] == "sesion")
    assert sesion["inconsistente"] and sesion["detalle_inconsistencia"]["significados"] == []
    assert len(sesion["detalle_inconsistencia"]["lel"]) == 2


def test_sin_inconsistencia_con_un_solo_significado(proyecto):
    _, trazas, lel = _datos(proyecto)
    a = ambiguedades_proyecto([t for t in trazas if t.req_id != "R02"], [e for e in lel if e.req_id == "R01"])
    assert a["totales"]["inconsistentes"] == 0
    assert next(g for g in a["terminos"] if g["clave"] == "sesion")["detalle_inconsistencia"] is None


def _entrada(req_id: str, nocion: list[str], simbolo: str = "sesión"):
    from app.models import EntradaLELFormalizada
    from tests.escenarios import I1

    return EntradaLELFormalizada(simbolo=simbolo, tipo="objeto", nocion=nocion, impacto=["Se registra."],
                                 proyecto_id="P01", req_id=req_id, termino=simbolo, via="consenso",
                                 interpretacion=I1, editada_por_humano=False, fecha="2026-10-06")


def test_nociones_iguales_en_otro_orden_no_son_inconsistencia():
    """Antes se comparaban como tuplas en su orden: el mismo LEL escrito en otro orden contaba."""
    mismas = [_entrada("R01", ["Periodo de uso.", "Se abre al entrar."]),
              _entrada("R02", ["se abre al entrar.", "Periodo de uso."])]
    a = ambiguedades_proyecto([], mismas)
    formas.AmbiguedadesProyecto.model_validate(a)
    assert a["terminos"] == [] and a["totales"]["inconsistentes"] == 0

    distintas = [*mismas, _entrada("R03", ["Evento de conexión."])]
    (g,) = ambiguedades_proyecto([], distintas)["terminos"]
    assert g["inconsistente"] and [e["req_id"] for e in g["detalle_inconsistencia"]["lel"]] == ["R01", "R02", "R03"]
    assert "2 nociones distintas" in g["detalle_inconsistencia"]["texto"]


# ---------------------------------------------------------------- flujo KMoS-SSA

def _fases(ciclo):
    return [(f["fase"], f["requisitos_que_pasaron"]) for f in ciclo["fases"]]


def test_flujo_por_ciclo(proyecto):
    _, trazas, lel = _datos(proyecto)
    f = flujo_proyecto(trazas, lel)
    formas.FlujoProyecto.model_validate(f)
    c1, c2 = f["ciclos"]

    assert (c1["ciclo"], c1["requisitos"]) == (1, 3)
    assert {k: c1[k] for k in ("debates", "rondas_totales", "consensos", "arbitrajes", "directos", "validados",
                               "rechazados", "formalizados", "lel_nuevas")} == {
        "debates": 1, "rondas_totales": 1, "consensos": 1, "arbitrajes": 0, "directos": 2, "validados": 2,
        "rechazados": 1, "formalizados": 2, "lel_nuevas": 2}
    assert _fases(c1) == [(1, 3), (2, 3), (3, 3), (4, 3), (5, 2)]
    assert [f_["nombre"] for f_ in c1["fases"]] == ["Enriquecimiento de conocimiento", "Generación de modelo",
                                                     "Discusión de modelo", "Validación de modelo",
                                                     "Enriquecimiento (cierre)"]
    assert c1["fases"][2]["agentes"] == ["divergencia", "critico", "clasificador"]
    tipos = c1["mensajes_por_tipo"]
    assert (tipos["extraccion"], tipos["interpretaciones"], tipos["objecion"], tipos["validacion"]) == (3, 3, 1, 3)
    assert tipos["formalizacion"] == 4  # R01 y R02: una por término léxico y una por requisito
    assert c1["fases"][4]["mensajes"] == tipos["formalizacion"]
    assert c1["mensajes_por_agente"]["humano"] == 3 and c1["mensajes_por_agente"]["critico"] == 1
    assert sum(c1["mensajes_por_agente"].values()) == sum(tipos.values())
    assert c1["duracion_s"] >= 0

    assert (c2["ciclo"], c2["requisitos"]) == (2, 4)
    assert {k: n for k, n in c2["por_estado"].items() if n} == {"pendiente_validacion": 3, "error": 1}
    assert {k: c2[k] for k in ("debates", "rondas_totales", "consensos", "arbitrajes", "directos", "validados",
                               "formalizados", "lel_nuevas")} == {
        "debates": 1, "rondas_totales": 2, "consensos": 0, "arbitrajes": 1, "directos": 2, "validados": 0,
        "formalizados": 0, "lel_nuevas": 0}
    assert _fases(c2) == [(1, 3), (2, 3), (3, 3), (4, 3), (5, 0)]  # R07 falló antes de extraer
    assert c2["mensajes_por_tipo"]["error"] == 1 and c2["mensajes_por_tipo"]["arbitraje"] == 1

    total = f["total"]
    assert total["ciclo"] is None and total["requisitos"] == 7
    for k in ("debates", "rondas_totales", "consensos", "arbitrajes", "directos", "validados", "rechazados",
              "formalizados", "lel_nuevas"):
        assert total[k] == c1[k] + c2[k]
    assert total["mensajes_por_tipo"] == {k: c1["mensajes_por_tipo"][k] + c2["mensajes_por_tipo"][k]
                                          for k in total["mensajes_por_tipo"]}
    assert total["duracion_s"] >= max(c1["duracion_s"], c2["duracion_s"])


