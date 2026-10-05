# nlp

- `spacy_es.py`: carga única de `es_core_news_sm`, normalización y extracción de lemas,
  sustantivos y entidades (lo usan los filtros y las reglas R1/R2).
- `catalogos.py`: catálogos regional y de vaguedad compilados como `PhraseMatcher`.
- `filtros.py`: filtros deterministas antes del Clasificador (ADR 0003).
