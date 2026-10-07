"""Rutas sobre trazas reales del grafo que terminaron en error y una cadena de reprocesos.

R01: el Crítico falla en el debate, después de la similitud inicial (0.0): la traza
queda en `error` y su similitud cuenta, sin vía. R02 se debate hasta consenso; R03
la vuelve a procesar y falla en el Extractor (sin similitud); R04 vuelve a procesar
R03 y termina: es la única versión del requisito que cuenta (R02 y R03 quedan
sustituidas). Las dos rutas son de solo lectura: no tocan ni el repositorio ni la
configuración.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import calibracion, proyectos
from app.calibracion import formas
from app.models import Origen
from tests.escenarios import EXTRACCION_SESION, I1, I2, SESION, clasificacion, montar
from tests.fakes import r3_todas

RETIRA_I2 = {"interpretaciones": [I1], "retiradas": [{"interpretacion_id": "I2", "motivo": "agrega red"}]}


def foto(directorio: Path) -> dict[str, bytes]:
    return {str(r.relative_to(directorio)): r.read_bytes() for r in sorted(directorio.rglob("*")) if r.is_file()}


def falla_en(llamada: int, respuesta):
    """Guion que levanta en la llamada número `llamada` (1, 2, …) y en las demás responde `respuesta`."""
    n = 0

    def guion(prompt):
        nonlocal n
        n += 1
        if n == llamada:
            raise RuntimeError("LLM caído")
        return respuesta(prompt) if callable(respuesta) else respuesta

    return guion


def test_trazas_en_error_y_reprocesos_en_cadena(tmp_path, analizador):
    srv, _, _ = montar(tmp_path, analizador, {
        "extractor_v1": falla_en(3, EXTRACCION_SESION),
        "clasificador_v3": falla_en(0, clasificacion(I1, I2)),
        "critico_v1": falla_en(1, r3_todas(False)),
        "clasificador_refinamiento_v1": falla_en(0, RETIRA_I2),
    })
    p = srv.proyectos.crear("Banca", "proyecto normal")
    r1 = srv.procesar(SESION, p.proyecto_id)
    r2 = srv.procesar(SESION, p.proyecto_id)
    r3 = srv.procesar(SESION, p.proyecto_id, Origen(reproceso_de=r2))
    r4 = srv.procesar(SESION, p.proyecto_id, Origen(reproceso_de=r3))
    assert [srv.traza(r).estado.value for r in (r1, r2, r3, r4)] == ["error", "pendiente_validacion", "error",
                                                                       "pendiente_validacion"]

    app = FastAPI()
    app.include_router(calibracion.router)
    app.include_router(proyectos.router)
    app.state.servicio = srv
    cliente = TestClient(app)
    archivos, configuracion = foto(srv.repo.dir), srv.deps.settings.model_dump()
    assert any(k.startswith("trazas") for k in archivos)
    for ruta in (f"/proyectos/{p.proyecto_id}/calibracion", "/calibracion"):
        r = cliente.get(ruta)
        assert r.status_code == 200, r.text
        c = formas.Calibracion.model_validate(r.json()).model_dump(mode="json")
        assert [(v["req_id"], v["similitud"], v["decision_real"], v["estado_requisito"], v["via"])
                for v in c["valores"]] == [(r1, 0.0, "en_debate", "error", None),
                                          (r4, 0.0, "en_debate", "pendiente_validacion", "consenso")]
        assert c["reprocesados"] == [r2, r3]
        configurada = next(f for f in c["rejilla"] if f["configurado"])
        assert (configurada["directos"], configurada["debates"], configurada["cambian"]) == (0, 2, [])
    assert foto(srv.repo.dir) == archivos and srv.deps.settings.model_dump() == configuracion
