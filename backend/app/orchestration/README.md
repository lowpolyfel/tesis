# orchestration

El grafo de LangGraph es la máquina de estados del requisito (ADR 0005).

- `estado.py`: estado tipado del grafo (JSON plano).
- `grafo.py`: un nodo por estado + el nodo `humano` (pausa con `interrupt`).
  Aristas condicionales: umbral de similitud, rondas de debate, decisión humana
  y desvío a `error`.
- `dependencias.py`: arma agentes, filtros, embeddings y repositorio desde la
  configuración (las pruebas los sustituyen por dobles).
- `servicio.py`: registrar, ejecutar, validar y reanudar; checkpointer SQLite en
  `data/checkpoints.sqlite` con `thread_id = req_id`. La validación que acepta la
  API se guarda (colección `validaciones`) antes de encolarla, y `recuperar()`
  retoma al arrancar lo que quedó a medias según el checkpoint (ADR 0008).
- `cola.py`: cola de un solo trabajador con prioridades (ADR 0008).

```
cargado → extraido → interpretado → aceptado_directo ──────────────┐
                                  └→ en_debate ⟲ → consenso ───────┤
                                               └→ arbitrado ───────┤
                                             pendiente_validacion ←┘
                                                      ↓ humano (interrupt)
                                      validado → formalizado | rechazado
(cualquier nodo con fallo → error)
```
