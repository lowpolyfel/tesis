# catalogos

Catálogos deterministas que usan los filtros previos al Clasificador
(`backend/app/nlp/filtros.py`, ADR 0003):

- `regionales.json`: términos regionales (mexicanismos y regionalismos de trabajo).
  Siempre pasan al Clasificador como candidatos. Se detectan con `PhraseMatcher`,
  incluidas frases multipalabra como *dar de alta*.
- `vaguedad.json`: expresiones vagas (*ahorita*, *rápido*, *pronto*…). Se marcan
  como vaguedad y **no entran a debate**: no producen dos interpretaciones
  discretas, marcan un límite impreciso.

Cada entrada lista sus `formas` flexionadas porque el lematizador de
`es_core_news_sm` no reconoce bien las formas regionales (p. ej. *jale* → *jalir*).
Las versiones sin acento se generan automáticamente al cargar.
