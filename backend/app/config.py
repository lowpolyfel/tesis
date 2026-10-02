"""Configuración calibrable del sistema, leída de variables de entorno.

Parámetros previstos (ver .env.example):
- SIMILARITY_THRESHOLD: umbral de similitud coseno que dispara el debate (inicial 0.75).
- MAX_DEBATE_ROUNDS: máximo de rondas del debate antes de que el Crítico arbitre (inicial 2).
- OLLAMA_BASE_URL: URL del servidor Ollama local.
- EXTRACTOR_MODEL, CLASIFICADOR_MODEL, MODELADOR_MODEL: modelos locales en Ollama.
- CRITICO_PROVIDER, CRITICO_MODEL, CRITICO_API_KEY: modelo por API del Crítico.
- EMBEDDING_MODEL: modelo de embeddings en Ollama (nomic-embed-text).
- SPACY_MODEL: modelo de spaCy (es_core_news_sm).
- MONGO_URI, MONGO_DB: conexión a MongoDB.
"""
