# db

Persistencia de trazas y del LEL (ADR 0006).

- `repositorio.py`: interfaz `Repositorio` con dos implementaciones.
  - `RepositorioMongo`: colecciones `trazas` (un documento por requisito, con
    todos sus mensajes y transiciones) y `lel` (entradas formalizadas).
  - `RepositorioJson`: `data/resultados/trazas/R01.json` y `data/resultados/lel.json`.
- `crear_repositorio(settings)`: usa Mongo si responde al `ping` dentro de
  `MONGO_TIMEOUT_MS`; si no, JSON. La traza registra cuál se usó.
