"""Cuestionario de evaluación: se abre al terminar un proyecto, se guarda por cuenta y los
resultados salen anónimos y solo para quien coordina."""
import pytest
from fastapi.testclient import TestClient

from app import cuestionario as cq
from app.api.main import create_app
from app.auth import Usuario
from tests.escenarios import montar
from tests.fakes import como_usuario

OTRA = Usuario(usuario_id="U07", nombre="Otra", correo="otra@ejemplo.mx", contrasena="-", verificado=True)


def completas(sus=None, **cambios) -> dict:
    """Todas las obligatorias contestadas con la primera opción (o 3 en las escalas)."""
    r = {}
    for qid in cq.ORDEN:
        p = cq.PREGUNTAS[qid]
        if not p["obligatoria"]:
            continue
        t = p["tipo"]
        r[qid] = (p["opciones"][0] if t == "opcion" else 3 if t == "escala" else 2 if t == "numero"
                  else [p["exclusiva"] or p["opciones"][0]])
    if sus is not None:
        r.update({q: v for q, v in zip(cq.SUS, sus, strict=True)})
    r.update(cambios)
    return r


@pytest.fixture
def entorno(tmp_path, analizador):
    srv, _, repo = montar(tmp_path, analizador, {}, cuestionario_admins="Prueba@Ejemplo.mx, coord@x.mx")
    with TestClient(como_usuario(create_app(srv))) as c:
        yield c, srv, repo


def terminar_proyecto(repo, pid="P00"):
    repo.guardar_doc("fase_requisitos", pid, {"proyecto_id": pid, "contenido": {"requisitos": []}})


def test_cerrado_hasta_terminar_un_proyecto_hasta_requisitos(entorno):
    c, srv, repo = entorno
    r = c.get("/cuestionario").json()
    assert r["disponible"] is False and r["preguntas"] is None and "cinco fases" in r["motivo"]
    assert c.put("/cuestionario", json={"respuestas": {}}).status_code == 403
    assert c.post("/cuestionario/enviar", json={"respuestas": completas()}).status_code == 403
    # llegar a metas no basta
    repo.guardar_doc("fase_metas", "P00", {"proyecto_id": "P00"})
    assert c.get("/cuestionario").json()["disponible"] is False
    # un proyecto de otra cuenta que sí terminó tampoco cuenta
    otro = srv.proyectos.crear("Ajeno", propietario="U09")
    terminar_proyecto(repo, otro.proyecto_id)
    assert c.get("/cuestionario").json()["disponible"] is False
    terminar_proyecto(repo)
    r = c.get("/cuestionario").json()
    assert r["disponible"] and r["proyectos_terminados"] == [{"proyecto_id": "P00", "nombre": "General"}]
    assert r["preguntas"]["total"] == 60 and len(r["preguntas"]["secciones"]) == 7
    assert r["respuesta"] is None and r["es_admin"] is True


def test_el_cuestionario_tiene_las_60_preguntas_del_md_y_el_sus_en_orden():
    assert [cq.PREGUNTAS[q]["n"] for q in cq.ORDEN] == list(range(1, 61))
    assert cq.PREGUNTAS["q25"]["texto"] == "Creo que me gustaría usar este sistema con frecuencia."
    assert cq.PREGUNTAS["q34"]["texto"].startswith("Necesité aprender muchas cosas antes")
    abiertas = [cq.PREGUNTAS[q]["n"] for q in cq.ORDEN if not cq.PREGUNTAS[q]["obligatoria"]]
    assert abiertas == [24, 49, 54, 55, 56, 57, 58, 60]


def test_borrador_se_guarda_por_cuenta_y_se_valida(entorno):
    c, srv, repo = entorno
    terminar_proyecto(repo)
    r = c.put("/cuestionario", json={"respuestas": {"q1": cq.PREGUNTAS["q1"]["opciones"][1], "q9": 4, "q24": "  ", "q7": None}})
    assert r.status_code == 200 and r.json()["estado"] == "borrador"
    assert r.json()["respuestas"] == {"q1": cq.PREGUNTAS["q1"]["opciones"][1], "q9": 4}  # las vacías no se guardan
    assert repo.obtener_doc("cuestionarios", "U00")["usuario_id"] == "U00"
    assert c.get("/cuestionario").json()["respuesta"]["respuestas"]["q9"] == 4

    malas = c.put("/cuestionario", json={"respuestas": {"q9": 6, "q1": "otra", "q99": 1, "q41": ["Ninguno", "Gemini"]}})
    assert malas.status_code == 422
    errores = malas.json()["detail"]["errores"]
    assert "pregunta 9: tiene que ser un número del 1 al 5" in errores and len(errores) == 4

    # otra cuenta tiene su propio cuestionario (y su propio candado)
    c.app.dependency_overrides.clear()
    como_usuario(c.app, OTRA)
    assert c.get("/cuestionario").json()["disponible"] is False
    p = srv.proyectos.crear("Suyo", propietario="U07")
    terminar_proyecto(repo, p.proyecto_id)
    assert c.get("/cuestionario").json()["respuesta"] is None
    c.put("/cuestionario", json={"respuestas": {"q9": 1}})
    assert repo.obtener_doc("cuestionarios", "U00")["respuestas"]["q9"] == 4


def test_enviar_exige_las_obligatorias_y_calcula_el_sus(entorno):
    c, _, repo = entorno
    terminar_proyecto(repo)
    r = c.post("/cuestionario/enviar", json={"respuestas": {"q1": cq.PREGUNTAS["q1"]["opciones"][0]}})
    assert r.status_code == 422 and len(r.json()["detail"]["faltantes"]) == 51
    # SUS de Brooke: impares valor−1, pares 5−valor; todo en el mejor extremo da 100
    r = c.post("/cuestionario/enviar", json={"respuestas": completas(sus=[5, 1] * 5, q60="Bien")})
    assert r.status_code == 200 and r.json()["estado"] == "enviado" and r.json()["sus"] == 100.0
    enviado = r.json()["enviado"]
    # corregir después del envío: se recalcula, pero no se puede dejar una obligatoria vacía
    sin_q2 = completas(sus=[3] * 10)
    del sin_q2["q2"]
    assert c.put("/cuestionario", json={"respuestas": sin_q2}).status_code == 422
    r = c.put("/cuestionario", json={"respuestas": completas(sus=[3] * 10)}).json()
    assert r["estado"] == "enviado" and r["sus"] == 50.0 and r["enviado"] == enviado


def test_resultados_anonimos_solo_para_coordinacion(entorno):
    c, _, repo = entorno
    terminar_proyecto(repo)
    c.post("/cuestionario/enviar", json={"respuestas": completas(sus=[5, 1] * 5, q8=4, q12=5, q60="Me gustó")})
    repo.guardar_doc("cuestionarios", "U08", {**cq.nuevo("U08"), "estado": "enviado", "enviado": "2026-11-05",
                                              "respuestas": completas(sus=[3] * 10, q8=2, q12=2,
                                                                      q50=["Error 503: el modelo de Gemini estaba saturado"]),
                                              "sus": 50.0})
    repo.guardar_doc("cuestionarios", "U09", cq.nuevo("U09"))  # un borrador no cuenta

    res = c.get("/cuestionario/resultados").json()
    assert res["enviados"] == 2 and res["borradores"] == 1
    assert res["sus"] == {"n": 2, "media": 75.0, "mediana": 75.0, "de": pytest.approx(35.355, abs=1e-3),
                          "valores": [50.0, 100.0]}
    assert res["preguntas"]["q8"] == {"n": 2, "media": 3.0, "mediana": 3.0, "minimo": 2, "maximo": 4,
                                       "valores": [2, 4]}
    assert res["preguntas"]["q12"]["arriba_del_medio"] == 0.5 and res["preguntas"]["q12"]["mediana"] == 3.5
    assert res["preguntas"]["q60"]["respuestas"] == ["Me gustó"]
    assert res["con_fallas_de_infraestructura"] == 1
    assert "U00" not in str(res) and "prueba@ejemplo.mx" not in str(res)

    csv = c.get("/cuestionario/resultados.csv")
    assert csv.status_code == 200 and "attachment" in csv.headers["content-disposition"]
    filas = csv.text.lstrip("﻿").splitlines()
    assert filas[0].startswith("respuesta,enviado,sus,P1,P2") and filas[1].startswith("R01,")
    assert len(filas) == 3 and "U00" not in csv.text and "U08" not in csv.text

    c.app.dependency_overrides.clear()
    como_usuario(c.app, OTRA)
    assert c.get("/cuestionario/resultados").status_code == 403
    assert c.get("/cuestionario/resultados.csv").status_code == 403
    assert c.get("/cuestionario").json()["es_admin"] is False


def test_exportar_latex_para_overleaf(entorno, tmp_path):
    import io
    import shutil
    import subprocess
    import zipfile

    c, _, repo = entorno
    terminar_proyecto(repo)
    vacio = zipfile.ZipFile(io.BytesIO(c.get("/cuestionario/resultados/overleaf.zip").content))
    assert "Todavía no hay cuestionarios enviados" in vacio.read("main.tex").decode()
    c.post("/cuestionario/enviar", json={"respuestas": completas(sus=[5, 1] * 5, q60="Bien & 100% {sí} 😅")})
    repo.guardar_doc("cuestionarios", "U08", {**cq.nuevo("U08"), "estado": "enviado", "enviado": "2026-11-05",
                                              "respuestas": completas(sus=[3] * 10), "sus": 50.0})
    r = c.get("/cuestionario/resultados/overleaf.zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    nombres = set(z.namelist())
    assert {"main.tex", "estilo-dudamel.tex", "estilo-cuestionario.tex", "figuras/sus.tex", "figuras/comparacion.tex",
            "figuras/sus_items.tex", "figuras/etapas.tex", "figuras/ambiguedad.tex", "figuras/problemas.tex",
            "tablas/escalas.tex", "tablas/abiertas.tex", "datos/respuestas.csv", "datos/sus.csv",
            "datos/sus_items.csv", "resultados.json"} <= nombres
    # el histograma y los ítems del SUS no comparten archivo de datos
    assert z.read("datos/sus.csv").decode().startswith("centro,personas")
    assert "U00" not in r.content.decode("latin-1") and "prueba@ejemplo.mx" not in r.content.decode("latin-1")
    # lo que escribió la persona va escapado y sin el emoji (pdfLaTeX no lo conoce)
    assert r"Bien \& 100\% \{sí\} ?" in z.read("tablas/abiertas.tex").decode()
    if shutil.which("pdflatex"):
        z.extractall(tmp_path / "paq")
        for _ in range(2):
            p = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=tmp_path / "paq",
                               capture_output=True, timeout=180, check=False)
        assert p.returncode == 0, p.stdout.decode(errors="replace")[-2000:]

    c.app.dependency_overrides.clear()
    como_usuario(c.app, OTRA)
    assert c.get("/cuestionario/resultados/overleaf.zip").status_code == 403


def test_resultados_traen_las_preguntas_y_los_grupos_para_graficar(entorno):
    c, _, _ = entorno
    r = c.get("/cuestionario/resultados").json()  # sin enviados, igual responde
    assert r["enviados"] == 0 and r["cuestionario"]["total"] == 60
    assert [g["id"] for g in r["grupos"]] == ["comparacion", "sus", "etapas", "ambiguedad"]
    assert r["grupos"][1]["preguntas"] == [f"q{n}" for n in range(25, 35)]


def test_la_cuenta_dice_si_coordina_la_evaluacion(entorno):
    from app.api.routes.auth import yo
    from tests.fakes import USUARIO_PRUEBA

    _, srv, _ = entorno
    assert yo(USUARIO_PRUEBA, srv).coordina_evaluacion is True  # Prueba@Ejemplo.mx, sin importar mayúsculas
    assert yo(OTRA, srv).coordina_evaluacion is False


@pytest.mark.parametrize("admins", ["", "*", " * , coord@x.mx"])
def test_sin_lista_todas_las_cuentas_ven_y_exportan_los_resultados(tmp_path, analizador, admins):
    """Lo de omisión (CUESTIONARIO_ADMINS vacío) o «*»: cualquier cuenta ve los resultados."""
    srv, _, _ = montar(tmp_path, analizador, {}, cuestionario_admins=admins)
    with TestClient(como_usuario(create_app(srv), OTRA)) as c:
        assert c.get("/cuestionario").json()["es_admin"] is True
        assert c.get("/auth/yo").json()["coordina_evaluacion"] is True
        assert c.get("/cuestionario/resultados").status_code == 200
        assert c.get("/cuestionario/resultados.csv").status_code == 200
        assert c.get("/cuestionario/resultados/overleaf.zip").status_code == 200
