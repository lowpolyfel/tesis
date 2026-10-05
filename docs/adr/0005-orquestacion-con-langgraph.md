# 0005. Orquestación: el grafo es la máquina de estados

- **Fecha:** 2026-10-05
- **Estado:** Aceptada

## Contexto

La fase pide un `StateGraph` de LangGraph con estado tipado cuyos estados sean
exactamente los de la máquina de estados del CONTEXTO §11, aristas condicionales
para el umbral y las rondas, validación humana con `interrupt` antes del
Modelador y un checkpointer para reanudar. Faltaba decidir cómo se corresponden
nodos y estados, dónde se pausa, qué pasa con varios términos por requisito y
qué se propone al humano.

## Decisión

1. **Cada nodo lleva el nombre de un estado** y hace el trabajo que lleva a ese
   estado; al terminar registra la transición en la traza (`transiciones`). El
   dibujo del grafo (`grafo.get_graph().draw_mermaid()`) es la máquina de estados.
   Una prueba verifica que los nodos sean exactamente `Estado` más `humano`.
   - `cargado`: fija el LEL vigente contra el que se procesará el requisito.
   - `extraido`: Extractor + filtros deterministas.
   - `interpretado`: Clasificador + divergencia (la arista necesita la similitud).
   - `en_debate`: una ronda completa; la transición se registra al *inicio* de
     cada ronda, para que se vea mientras se debate.
   - `consenso`, `aceptado_directo`, `validado`, `rechazado`: solo transición.
   - `arbitrado`: arbitraje del Crítico. `formalizado`: Modelador + LEL.
2. **El único nodo que no es estado es `humano`**, el actor externo (también es
   un `Nodo` del sobre de mensajes). Ahí está el `interrupt`. Va separado de
   `pendiente_validacion` porque LangGraph reejecuta el nodo interrumpido desde
   el inicio al reanudar: así la `solicitud_validacion` se emite una sola vez y el
   mensaje `validacion` se emite solo después de recibir la respuesta. El valor de
   reanudación se valida con `interrupt(..., response_schema=Validacion)`.
3. **Errores:** cualquier excepción de un nodo (incluido `FalloEstructurado`
   tras el reintento) se registra como mensaje `error` con las salidas crudas y
   la arista lleva al nodo `error`. Las señales internas de LangGraph
   (`GraphBubbleUp`, que incluye `interrupt`) no se capturan.
4. **Varios términos por requisito.** La divergencia se mide por término. El
   requisito va a `en_debate` si algún término queda bajo el umbral; solo esos
   términos se debaten. Va a `consenso` cuando todos los debatidos lo alcanzan,
   y a `arbitrado` si se agotan las rondas con alguno pendiente (solo esos se
   arbitran).
5. **"Queda una sola interpretación válida"** = queda una sola interpretación
   vigente después de que el Clasificador refina o retira. Las versiones
   refinadas se vuelven a evaluar en la ronda siguiente, no en la misma.
6. **Sin objeciones no se consulta al Clasificador** en esa ronda: se registra un
   `refinamiento` del sistema con las mismas interpretaciones y una nota. El
   protocolo se sigue literal: si la similitud no cambia, se abre otra ronda
   hasta `MAX_DEBATE_ROUNDS` y luego se arbitra.
7. **Propuesta al humano:** aceptado directo → la primera interpretación;
   consenso → la primera vigente; arbitraje → la elegida por el Crítico. El
   humano puede aprobar, rechazar, elegir otra interpretación (incluso una
   retirada) o reescribirla; la traza distingue `ninguno | eleccion | edicion`.
8. **Sin interpretaciones** (sin candidatos o todos unívocos): el requisito pasa
   por `interpretado` → `aceptado_directo` con un mensaje `similitud` cuyo valor
   es `null` y `motivo: sin_interpretaciones`, y sigue hasta `pendiente_validacion`.
9. **Estado del grafo en JSON plano** (dicts y listas), no objetos Pydantic: el
   checkpointer lo serializa sin depender de clases y se puede inspeccionar.
10. **Checkpointer `SqliteSaver`** en `data/checkpoints.sqlite` (fuera de git),
    `thread_id = req_id`. Un requisito pausado se puede validar después de
    reiniciar el servidor (hay prueba de ello).

## Alternativas consideradas

- **Un nodo por agente** (extractor, clasificador, crítico…): el grafo dejaría de
  mostrar la máquina de estados y el estado viviría en un campo aparte.
- **`interrupt` dentro de `pendiente_validacion`:** duplica la solicitud al reanudar.
- **`interrupt_before` estático:** la documentación lo reserva para depuración;
  la fase pide `interrupt`.
- **`InMemorySaver`:** se pierde la pausa al reiniciar; se usa solo en pruebas.

## Consecuencias

- El ruteo se prueba sin Ollama con LLMs y embeddings falsos.
- Un requisito interrumpido a la mitad por una caída del servidor (no en la
  pausa humana) queda en su último estado; reanudarlo queda fuera de esta fase.
