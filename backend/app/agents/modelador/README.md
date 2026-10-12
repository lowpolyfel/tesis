# Agente Modelador

Toma la interpretación validada y, con ayuda de `app/artifacts/`, genera los artefactos:
entrada del LEL, modelo de metas estratégicas y Big Picture.
Modelo: Ollama local. Prompt: `prompts/modelador_vN.txt`.

También organiza el mapa conceptual del proyecto (`mapear`, prompt `modelador_mapa_v1`) sobre los
conceptos y relaciones candidatas que prepara `app/artefactos/mapa_conceptual.py` (ADR 0020).
