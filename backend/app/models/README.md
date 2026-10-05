# models

Contratos Pydantic del sistema (ADR 0001):

- `comunes.py`: vocabulario cerrado (estados, tipos de mensaje, nodos, categorías, reglas).
- `contratos.py`: entrada y salida de cada agente. Los modelos `*LLM` son lo que se le
  pide al LLM; el resto lo completa el código.
- `mensajes.py`: sobre común de los mensajes, traza por requisito y validación humana.
