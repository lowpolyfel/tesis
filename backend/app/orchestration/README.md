# orchestration

El grafo de LangGraph es la máquina de estados del requisito (ADR 0005).

- `estado.py`: estado tipado del grafo (JSON plano).
- `grafo.py`: un nodo por estado + el nodo `humano` (pausa con `interrupt`).
  Aristas condicionales: umbral de similitud, rondas de debate, decisión humana
  y desvío a `error`.
- `dependencias.py`: arma agentes, filtros, embeddings y repositorio desde la
  configuración (las pruebas los sustituyen por dobles).
- `servicio.py`: registrar, ejecutar, validar y reanudar; checkpointer SQLite en
  `data/checkpoints.sqlite` con `thread_id = req_id`.

```
cargado → extraido → interpretado → aceptado_directo ──────────────┐
                                  └→ en_debate ⟲ → consenso ───────┤
                                               └→ arbitrado ───────┤
                                             pendiente_validacion ←┘
                                                      ↓ humano (interrupt)
                                      validado → formalizado | rechazado
(cualquier nodo con fallo → error)
```
