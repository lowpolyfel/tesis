# Agente Crítico

Se activa cuando `app/divergence/` detecta interpretaciones divergentes. Conduce un
debate acotado (máximo `MAX_DEBATE_ROUNDS` rondas) y, si no hay consenso, arbitra y
decide la interpretación final. Produce un objeto `Debate`.
Modelo: por API (único agente fuera de Ollama). Prompt: `prompts/critico_vN.txt`.
