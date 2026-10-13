# Cambios

## 2.0.0 — 2026-10-13

De la entrevista a los requisitos (ADR 0024).

- **Entrada nueva: la entrevista.** Texto pegado, PDF con texto o .txt, leída por turnos y
  hablantes, con vista previa antes de enviarla. Varias entrevistas por proyecto.
- **LEL interactivo.** Un grafo nuevo procesa la entrevista completa: el Revisor la anota,
  el Extractor separa los términos, los filtros los cruzan con la memoria del proyecto, el
  Clasificador propone la intención de cada uno, la divergencia y el Crítico debaten las
  que divergen y el Modelador escribe el LEL. La persona experta valida, corrige, elige otra
  intención, descarta o agrega términos.
- **El sistema aprende.** Lo que la persona corrige, confirma entre varias intenciones o
  descarta queda como acuerdo del proyecto: resuelve el término en las entrevistas
  siguientes y lo reciben los agentes en todas las fases. Se puede olvidar.
- **Mapa conceptual con propósito**, editable sobre el propio mapa (React Flow) y validable
  por componente; se exporta como Mermaid, PNG o SVG.
- **Metas en tres niveles**: de la organización, estratégicas y específicas.
- **Requisitos** funcionales y no funcionales con trazabilidad a metas, LEL y entrevista,
  avisos de lo que conviene revisar y la especificación completa en Markdown.
- **Fases con compuertas**: cada una se abre cuando la anterior quedó validada; si cambia lo
  de atrás, lo de adelante se marca para volver a generar o conservar.
- **Las esferas** en cada fase: reciben la entrevista, la procesan en escena, absorben lo que
  la persona valida y dicen qué aprendió el sistema.
- La versión 1 (requisitos escritos, uno por uno) se conserva en `/proyectos/:id/v1` y en «Más».
