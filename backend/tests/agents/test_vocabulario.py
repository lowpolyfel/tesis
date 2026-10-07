"""Un concepto, un nombre (ADR 0001 §3): la documentación y el código del núcleo dicen
«interpretación», nunca lectura, visión ni postura."""
import re

from app.config import RAIZ_BACKEND, RAIZ_REPO

PROHIBIDAS = re.compile(r"\b(lecturas?|visi[oó]n|visiones|posturas?)\b", re.IGNORECASE)
PERMITIDAS = re.compile(r"solo lectura", re.IGNORECASE)  # «de solo lectura» no nombra el concepto
NUCLEO = ["agents", "prompts", "orchestration", "divergence", "llm", "models", "nlp", "db"]


def _archivos():
    yield RAIZ_REPO / "README.md"
    yield RAIZ_BACKEND / "README.md"
    for carpeta in NUCLEO:
        for ruta in sorted((RAIZ_BACKEND / "app" / carpeta).rglob("*")):
            if ruta.suffix in (".md", ".py", ".txt") and "__pycache__" not in ruta.parts:
                yield ruta


def test_el_nucleo_no_usa_sinonimos_de_interpretacion():
    hallazgos = [f"{ruta.relative_to(RAIZ_REPO)}:{n}: {linea.strip()}"
                 for ruta in _archivos()
                 for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1)
                 if PROHIBIDAS.search(PERMITIDAS.sub("", linea))]
    assert hallazgos == []
