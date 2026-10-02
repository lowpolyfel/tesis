# corpus

Requisitos de prueba en español de México.

- Un archivo con los requisitos (ej. `requisitos.jsonl`), cada uno con un identificador.
- Un archivo **separado** con el ground truth (ej. `ground_truth.jsonl`): qué ambigüedad
  contiene cada requisito, referenciado por el mismo identificador.

Mantenerlos separados evita que el ground truth se filtre a los agentes.
