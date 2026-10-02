# divergence

Mecanismo que decide si se dispara el debate. **No es un agente.**

- Calcula embeddings de las interpretaciones con `nomic-embed-text` vía Ollama.
- Calcula la similitud coseno entre pares de interpretaciones.
- Compara contra `SIMILARITY_THRESHOLD` (inicial 0.75): por debajo del umbral hay
  divergencia y se activa el Crítico.
