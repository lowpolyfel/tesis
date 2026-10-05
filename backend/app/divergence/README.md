# divergence

Mecanismo de divergencia (no es un agente, ADR 0002):

- `similitud.py`: coseno a mano con numpy, mínimo entre pares y decisión del umbral. Puro.
- `embeddings.py`: interfaz `ProveedorEmbeddings` y su implementación con Ollama.
- `evaluacion.py`: compara las paráfrasis de las interpretaciones de un término.
