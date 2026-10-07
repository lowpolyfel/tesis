"""Exportaciones de texto del Big Picture: Mermaid y PlantUML estables y sin
caracteres que rompan la sintaxis."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.artefactos import a_mermaid, big_picture_proyecto, texto_mermaid
from app.artefactos.exportar import ids_saneados
from app.config import RAIZ_REPO
from tests.artefactos.ayudantes import (
    documentos,
    entrada,
    formalizado,
    lel,
    meta,
    resumen,
    trazas,
)

FORMAS = r'(\[/"|\(\("|\("|\(\["|\{\{"|\["|\[\[")(?P<etiqueta>[^"]*)("/\]|"\)\)|"\)|"\]\)|"\}\}|"\]|"\]\])'
NODO = re.compile(rf"^    (?P<id>[A-Za-z][A-Za-z0-9_]*){FORMAS}$")
ARISTA = re.compile(r"^    [A-Za-z][A-Za-z0-9_]* (-->|-\.->)\|[a-z_]+\| [A-Za-z][A-Za-z0-9_]*$")
ESTILO = re.compile(r"^    (classDef [a-z_]+ [a-z0-9:#,. -]+|class [A-Za-z0-9_,]+ [a-z_]+)$")
CON_RAREZAS = 'campo "RFC" [obligatorio] {x} <b>#1</b> `y` | ñandú'
DIR_MERMAID = Path(__file__).parent / "mermaid"
NUCLEO_MERMAID = RAIZ_REPO / "frontend" / "node_modules" / "mermaid" / "dist" / "mermaid.core.mjs"
# PlantUML no viene con el repositorio: PLANTUML_JAR=/ruta/plantuml.jar activa su prueba
JAR_PLANTUML = os.environ.get("PLANTUML_JAR", "")
# lo que PlantUML interpreta: la barra invertida al final une la línea con la siguiente y
# «/'» abre un comentario; el NUL de un PDF no es válido en el SVG de ningún visor
CON_CONTROL = "Valida\x00 el RFC /' sin comentario \\"


def _raro():
    """Proyecto con etiquetas que romperían Mermaid si no se escaparan."""
    docs = documentos() + [formalizado("R10", f"El sistema debe validar el {CON_RAREZAS}.", [
        meta("M1", f"Validar el {CON_RAREZAS}", actor='El "auditor" <externo>', simbolos=[CON_RAREZAS])])]
    entradas = lel() + [entrada(CON_RAREZAS, "objeto", ['Dato con "comillas", [corchetes] y {llaves}.'],
                                ["Se valida antes de guardar; #importante."], "R10")]
    return big_picture_proyecto(docs, entradas, trazas() + [resumen("R10", "formalizado")])


def _con_control():
    """Textos con caracteres de control y con lo que PlantUML interpreta."""
    docs = [formalizado("R01", CON_CONTROL, [meta("M1", CON_CONTROL, actor=CON_CONTROL, simbolos=["RFC"])])]
    entradas = [entrada("RFC", "objeto", [CON_CONTROL], [CON_CONTROL], "R01"),
                entrada("contribuyente", "sujeto", ["Persona con RFC."], [CON_CONTROL], "R01")]
    return big_picture_proyecto(docs, entradas, [resumen("R01", "formalizado")])


def _lineas_validas(texto: str) -> list[str]:
    lineas = texto.rstrip("\n").split("\n")
    assert lineas[0] == "flowchart LR"
    for linea in lineas[1:]:
        m = NODO.match(linea)
        if m:
            etiqueta = m.group("etiqueta")
            assert not re.search(r'["<>`]', etiqueta), linea
            assert not re.search(r"#(?![a-z0-9]+;)", etiqueta), linea  # «#» solo como entidad
        else:
            assert ARISTA.match(linea) or ESTILO.match(linea), linea
    return lineas


def test_mermaid_del_proyecto_es_valido_y_estable():
    bp = big_picture_proyecto(documentos(), lel(), trazas())
    lineas = _lineas_validas(bp["mermaid"])
    assert '    R01_M1("R01.M1: Registrar el periodo de uso del usuario")' in lineas
    assert '    actor_sistema(("sistema"))' in lineas
    assert '    simbolo_dar_de_alta[["dar de alta (verbo)"]]' in lineas
    assert '    R02_M2(["R02.M2: Responder ahorita"])' in lineas
    assert '    R01_M2{{"R01.M2: Guardar la hora de inicio y de cierre"}}' in lineas
    assert '    R03_M2["R03.M2: Expediente del cliente"]' in lineas
    assert f'    R01[/"R01: {documentos()[0]["requisito_reescrito"]}"/]' in lineas
    assert "    R01_M2 -->|contribuye_a| R01_M1" in lineas
    assert "    simbolo_sesion -.->|relacionado_con| simbolo_usuario" in lineas
    assert "    class R01_M2,R03_M1 tarea" in lineas
    assert sum(bool(NODO.match(x)) for x in lineas) == len(bp["nodos"])
    assert sum(bool(ARISTA.match(x)) for x in lineas) == len(bp["aristas"])
    assert big_picture_proyecto(documentos(), lel(), trazas())["mermaid"] == bp["mermaid"]


def test_mermaid_escapa_comillas_corchetes_y_html():
    bp = _raro()
    lineas = _lineas_validas(bp["mermaid"])
    esperado = ("campo #quot;RFC#quot; [obligatorio] {x} #lt;b#gt;#35;1#lt;/b#gt; #96;y#96; | ñandú (objeto)")
    assert f'    simbolo_campo_rfc_obligatorio_x_b_1_b_y_nandu[["{esperado}"]]' in lineas
    assert '    actor_auditor_externo(("#quot;auditor#quot; #lt;externo#gt;"))' in lineas


def test_caracteres_de_control_y_lo_que_plantuml_interpreta():
    bp = _con_control()
    _lineas_validas(bp["mermaid"])
    for texto in (bp["mermaid"], bp["plantuml"]):
        assert "\x00" not in texto
    lineas = bp["plantuml"].split("\n")
    assert not any(x.rstrip().endswith("\\") for x in lineas)
    assert not any("/'" in x for x in lineas)
    assert "  {field} noción: Valida el RFC /’ sin comentario ∖" in lineas


def test_texto_mermaid():
    assert texto_mermaid('a "b" #c <d> `e`\n  f') == "a #quot;b#quot; #35;c #lt;d#gt; #96;e#96; f"
    assert texto_mermaid("ñandú [x] (y) {z} | ; &") == "ñandú [x] (y) {z} | ; &"
    assert texto_mermaid("   ") == " "


def test_ids_saneados_sin_colisiones_ni_reservadas():
    assert ids_saneados(["R01.M1", "R01_M1", "end", "1x", "simbolo:y/o", "simbolo:y_o", "Class"]) == {
        "R01.M1": "R01_M1", "R01_M1": "R01_M1_2", "end": "end_", "1x": "n_1x", "simbolo:y/o": "simbolo_y_o",
        "simbolo:y_o": "simbolo_y_o_2", "Class": "Class_"}


def test_mermaid_sin_nodos():
    texto = a_mermaid([], [])
    assert _lineas_validas(texto)[0] == "flowchart LR"
    assert "class " not in texto.replace("classDef", "")


@pytest.mark.skipif(shutil.which("node") is None or not NUCLEO_MERMAID.exists(),
                    reason="sin Node o sin el paquete mermaid del frontend")
def test_parser_de_mermaid_acepta_las_exportaciones(tmp_path):
    archivos = []
    for nombre, texto in (("proyecto", big_picture_proyecto(documentos(), lel(), trazas())["mermaid"]),
                          ("raro", _raro()["mermaid"]), ("control", _con_control()["mermaid"]),
                          ("vacio", a_mermaid([], []))):
        archivos.append(tmp_path / f"{nombre}.mmd")
        archivos[-1].write_text(texto, encoding="utf-8")
    roto = tmp_path / "roto.mmd"
    roto.write_text('flowchart LR\n    A["con "comillas" sin escapar"]\n', encoding="utf-8")

    def validar(*rutas):
        return subprocess.run(["node", "--import", "./registrar.mjs", "validar.mjs", str(NUCLEO_MERMAID), *map(str, rutas)],
                              cwd=DIR_MERMAID, capture_output=True, text=True, timeout=60, check=False)

    r = validar(*archivos)
    assert r.returncode == 0, r.stdout + r.stderr
    assert validar(roto).returncode == 1  # el validador sí detecta un diagrama roto


def test_plantuml():
    bp = big_picture_proyecto(documentos(), lel(), trazas())
    texto = bp["plantuml"]
    lineas = texto.rstrip("\n").split("\n")
    assert lineas[0] == "@startuml" and lineas[-1] == "@enduml"
    assert 'class "sesión" as simbolo_sesion <<objeto>> {' in lineas
    assert "  {field} noción: Periodo de uso continuo del sistema por un usuario." in lineas
    assert "  {field} impacto: Se registra al iniciar y al cerrar." in lineas
    assert 'class "dar de alta" as simbolo_dar_de_alta <<verbo>> {' in lineas
    # actores que no son sujetos del LEL; «usuario» se dibuja como su símbolo
    assert 'class "sistema" as actor_sistema <<actor>>' in lineas
    assert 'class "usuarios" as actor_usuarios <<actor>>' in lineas
    assert not any(x.startswith('class "usuario" as actor_usuario') for x in lineas)
    assert "simbolo_dar_de_alta --> simbolo_sesion : relacionado con" in lineas
    assert "actor_sistema --> simbolo_sesion : registrar (R01.M1)" in lineas
    assert "actor_administrador --> simbolo_dar_de_alta : dar (R03.M1)" in lineas
    assert "actor_usuarios --> simbolo_bitacora : consultar (R02.M1)" in lineas
    assert big_picture_proyecto(documentos(), lel(), trazas())["plantuml"] == texto


def test_plantuml_actor_que_es_sujeto_del_lel(analizador):
    lineas = big_picture_proyecto(documentos(), lel(), trazas(), analizador)["plantuml"].split("\n")
    assert "simbolo_usuario --> simbolo_bitacora : consultar (R02.M1)" in lineas
    assert not any("actor_usuario" in x for x in lineas)


def test_plantuml_escapa():
    texto = _raro()["plantuml"]
    assert 'class "campo \'RFC\' [obligatorio] (x) ‹b›#1‹/b› `y` | ñandú" as simbolo_campo_rfc_obligatorio_x_b_1_b_y_nandu <<objeto>> {' in texto
    assert "  {field} noción: Dato con 'comillas', [corchetes] y (llaves)." in texto
    assert "class \"'auditor' ‹externo›\" as actor_auditor_externo <<actor>>" in texto


@pytest.mark.skipif(not (JAR_PLANTUML and Path(JAR_PLANTUML).is_file() and shutil.which("java")),
                    reason="sin Java o sin PLANTUML_JAR")
def test_plantuml_acepta_las_exportaciones():
    def sintaxis(texto: str) -> str:
        r = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", JAR_PLANTUML, "-syntax"], input=texto,
                           capture_output=True, text=True, timeout=120, check=False)
        return r.stdout

    for bp in (big_picture_proyecto(documentos(), lel(), trazas()), _raro(), _con_control(),
               big_picture_proyecto([], [], [])):
        assert sintaxis(bp["plantuml"]).startswith("CLASS"), bp["plantuml"]
    # el validador sí detecta un diagrama roto: la barra invertida final une dos líneas
    assert sintaxis('@startuml\nclass "a" as a {\n  {field} x \\\n}\n@enduml\n').startswith("ERROR")
