# scripts

Utilidades de línea de comandos:

- `casos_aceptacion.py`: corre con Ollama real los tres requisitos de aceptación
  de la fase (eliminar usuarios, sesión, jalar ahorita) y reporta filtros,
  interpretaciones, similitudes y estado. Guarda el reporte en
  `data/resultados/aceptacion/`. Puede correr con la API arriba (también con el
  respaldo JSON); no arranques la API mientras el script está a mitad de un
  requisito, porque lo retomaría en paralelo (ADR 0006).
- Pendiente: carga del corpus y evaluación contra el ground truth.
